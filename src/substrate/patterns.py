# Pattern detection from decision history using SQL aggregation.

from __future__ import annotations

from dataclasses import dataclass

from .ledger import DecisionLedger
from .models import MemoryEntry, MemoryType, MemoryScope
from .store import MemoryStore


@dataclass(frozen=True)
class PatternInsight:
    pattern_type: str
    description: str
    confidence: float
    sample_size: int
    details: dict

    def to_memory(self, project: str = "") -> MemoryEntry:
        return MemoryEntry(
            type=MemoryType.PATTERN,
            scope=MemoryScope.PRIVATE,
            content=self.description,
            context=f"{self.pattern_type} | {self.confidence:.0%} confidence | {self.sample_size} samples",
            project=project,
            tags=(self.pattern_type, "auto-discovered"),
        )


class PatternAnalyzer:
    MIN_SAMPLES = 5
    SIGNIFICANT_RATIO = 1.5

    def __init__(self, ledger: DecisionLedger, store: MemoryStore):
        self.ledger = ledger
        self.store = store

    def analyze_all(self, project: str = "") -> list[PatternInsight]:
        insights: list[PatternInsight] = []
        insights.extend(self._detect_time_patterns(project))
        insights.extend(self._detect_tool_patterns(project))
        return insights

    def _detect_time_patterns(self, project: str = "") -> list[PatternInsight]:
        where = "WHERE outcome_success IS NOT NULL"
        params: list = []
        if project:
            where += " AND project = ?"
            params.append(project)

        sql = f"""
            SELECT 
                CASE 
                    WHEN CAST(strftime('%H', timestamp) AS INTEGER) < 12 THEN 'morning'
                    WHEN CAST(strftime('%H', timestamp) AS INTEGER) < 18 THEN 'afternoon'
                    ELSE 'evening'
                END as period,
                COUNT(*) as total,
                SUM(CASE WHEN outcome_success = 0 THEN 1 ELSE 0 END) as failures
            FROM decisions {where}
            GROUP BY period
            HAVING total >= ?
        """
        params.append(self.MIN_SAMPLES)

        with self.ledger._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        if len(rows) < 2:
            return []

        # Build period stats
        periods = {}
        total_decisions = 0
        for period, total, failures in rows:
            periods[period] = {
                "total": total,
                "failures": failures,
                "rate": failures / total,
            }
            total_decisions += total

        # Find best and worst
        sorted_periods = sorted(periods.items(), key=lambda x: x[1]["rate"])
        best_period, best_data = sorted_periods[0]
        worst_period, worst_data = sorted_periods[-1]

        # Need meaningful difference
        if worst_data["rate"] == best_data["rate"]:
            return []

        # Calculate ratio (handle zero best rate)
        if best_data["rate"] == 0:
            ratio = float("inf") if worst_data["rate"] > 0 else 1.0
        else:
            ratio = worst_data["rate"] / best_data["rate"]

        if ratio < self.SIGNIFICANT_RATIO:
            return []

        # Cap ratio for display
        display_ratio = min(ratio, 10.0)
        confidence = min(1.0, total_decisions / 50)

        return [
            PatternInsight(
                pattern_type="time_of_day",
                description=f"You fail {display_ratio:.1f}x more in {worst_period} vs {best_period}",
                confidence=confidence,
                sample_size=total_decisions,
                details={
                    "best": best_period,
                    "worst": worst_period,
                    "ratio": display_ratio,
                    "periods": periods,
                },
            )
        ]

    def _detect_tool_patterns(self, project: str = "") -> list[PatternInsight]:
        where = "WHERE outcome_success IS NOT NULL AND tool_used != ''"
        params: list = []
        if project:
            where += " AND project = ?"
            params.append(project)

        sql = f"""
            SELECT tool_used, COUNT(*) as total,
                   SUM(CASE WHEN outcome_success = 0 THEN 1 ELSE 0 END) as failures
            FROM decisions {where}
            GROUP BY tool_used
            HAVING total >= ?
        """
        params.append(self.MIN_SAMPLES)

        with self.ledger._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        if not rows:
            return []

        # Baseline failure rate
        total_all = sum(r[1] for r in rows)
        failures_all = sum(r[2] for r in rows)
        baseline = failures_all / total_all if total_all > 0 else 0

        insights = []
        for tool, total, failures in rows:
            rate = failures / total

            # High failure tool
            if rate > 0.2 and rate >= baseline * self.SIGNIFICANT_RATIO:
                insights.append(
                    PatternInsight(
                        pattern_type="tool_failure",
                        description=f"{tool} fails {rate:.0%} (baseline {baseline:.0%})",
                        confidence=min(1.0, total / 20),
                        sample_size=total,
                        details={"tool": tool, "rate": rate, "baseline": baseline},
                    )
                )

            # Reliable tool
            elif rate < 0.1 and total >= 10 and baseline > 0.15:
                insights.append(
                    PatternInsight(
                        pattern_type="tool_success",
                        description=f"{tool} succeeds {1 - rate:.0%}",
                        confidence=min(1.0, total / 20),
                        sample_size=total,
                        details={"tool": tool, "rate": 1 - rate},
                    )
                )

        return insights

    def save_patterns(self, insights: list[PatternInsight], project: str = "") -> int:
        if not insights:
            return 0
        memories = [i.to_memory(project) for i in insights]
        return self.store.save_many(memories)

    def run_analysis(self, project: str = "") -> list[PatternInsight]:
        insights = self.analyze_all(project)
        if insights:
            self.save_patterns(insights, project)
        return insights

    def get_stats(self, project: str = "") -> dict:
        where = "WHERE project = ?" if project else ""
        params = [project] if project else []

        with self.ledger._connect() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) FROM decisions {where}", params
            ).fetchone()[0]

            outcome_where = "WHERE outcome_success IS NOT NULL"
            if project:
                outcome_where += " AND project = ?"
            with_outcomes = conn.execute(
                f"SELECT COUNT(*) FROM decisions {outcome_where}", params
            ).fetchone()[0]

            tools = conn.execute(
                f"SELECT COUNT(DISTINCT tool_used) FROM decisions {where}", params
            ).fetchone()[0]

            dates = conn.execute(
                f"SELECT MIN(timestamp), MAX(timestamp) FROM decisions {where}", params
            ).fetchone()

        return {
            "total": total,
            "with_outcomes": with_outcomes,
            "outcome_rate": with_outcomes / total if total > 0 else 0,
            "tools": tools,
            "first": dates[0],
            "last": dates[1],
            "ready": with_outcomes >= self.MIN_SAMPLES,
        }
