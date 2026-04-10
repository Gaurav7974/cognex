import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from substrate_mcp.tools import (
    ledger_find_similar,
    ledger_outcome,
    ledger_record,
    memory_add,
    memory_decay,
    memory_get_context,
    memory_search,
    substrate_end_session,
    substrate_process_transcript,
    substrate_report,
    substrate_start_session,
    swarm_compile_intent,
    teleport_create_bundle,
    teleport_rehydrate,
    trust_check,
    trust_get,
    trust_record,
    trust_summary,
)

REPORT = []
DECISION_ID = None
BUNDLE_JSON = None


def log(phase, tool, status, notes=""):
    REPORT.append(
        {"phase": phase, "tool": tool, "status": status, "notes": str(notes)[:200]}
    )
    icon = "[PASS]" if status else "[FAIL]"
    print(f"  {icon} {tool}: {notes[:100]}")


async def run_phase1():
    print("phase 1")
    try:
        r = await substrate_start_session(
            session_id="stress-test-001", project="stress-test"
        )
        log(1, "substrate_start_session", True, f"session={r['session_id']}")
    except Exception as e:
        log(1, "substrate_start_session", False, str(e))

    try:
        r = await memory_add(
            content="I prefer TypeScript over JavaScript",
            memory_type="preference",
            project="stress-test",
        )
        log(1, "memory_add (1)", True, f"id={r['id'][:8]}")
    except Exception as e:
        log(1, "memory_add (1)", False, str(e))

    try:
        r = await memory_add(
            content="Always use async/await not callbacks",
            memory_type="preference",
        )
        log(1, "memory_add (2)", True, f"id={r['id'][:8]}")
    except Exception as e:
        log(1, "memory_add (2)", False, str(e))

    try:
        r = await memory_add(
            content="Project uses PostgreSQL 15",
            memory_type="fact",
            project="stress-test",
        )
        log(1, "memory_add (3)", True, f"id={r['id'][:8]}")
    except Exception as e:
        log(1, "memory_add (3)", False, str(e))

    try:
        r = await memory_search(query="TypeScript", project="stress-test")
        log(1, "memory_search", r["count"] > 0, f"found {r['count']}")
    except Exception as e:
        log(1, "memory_search", False, str(e))

    try:
        r = await memory_get_context(query="coding style preferences")
        log(1, "memory_get_context", True, f"found {r['count']}")
    except Exception as e:
        log(1, "memory_get_context", False, str(e))

    try:
        r = await trust_check(tool_name="delete_files", operation="rm -rf")
        log(1, "trust_check", True, f"requires_approval={r['requires_approval']}")
    except Exception as e:
        log(1, "trust_check", False, str(e))

    try:
        r = await trust_record(
            action="approval", tool_name="delete_files", operation="rm -rf"
        )
        log(1, "trust_record", True, f"id={r['id']}")
    except Exception as e:
        log(1, "trust_record", False, str(e))

    try:
        r = await trust_get(tool_name="delete_files")
        log(1, "trust_get", True, f"trust_score={r['trust_score']}")
    except Exception as e:
        log(1, "trust_get", False, str(e))

    try:
        r = await trust_summary(project="stress-test")
        log(1, "trust_summary", True, f"count={r['count']}")
    except Exception as e:
        log(1, "trust_summary", False, str(e))

    try:
        r = await ledger_record(
            tool_used="PostgreSQL",
            reasoning="better than MySQL for our use case",
            project="stress-test",
            session_id="stress-test-001",
        )
        global DECISION_ID
        DECISION_ID = r["id"]
        log(1, "ledger_record", True, f"id={r['id']}")
    except Exception as e:
        log(1, "ledger_record", False, str(e))

    try:
        r = await ledger_outcome(
            decision_id=DECISION_ID, outcome="worked great", success=True
        )
        log(1, "ledger_outcome", True, f"success={r['outcome_success']}")
    except Exception as e:
        log(1, "ledger_outcome", False, str(e))

    try:
        r = await ledger_find_similar(query="better MySQL", project="stress-test")
        log(1, "ledger_find_similar", r["count"] > 0, f"found {r['count']}")
    except Exception as e:
        log(1, "ledger_find_similar", False, str(e))

    try:
        r = await teleport_create_bundle(
            source_host="machine-1", target_host="machine-2"
        )
        global BUNDLE_JSON
        BUNDLE_JSON = r["serialized"]
        log(1, "teleport_create_bundle", True, f"bundle_id={r['bundle_id']}")
    except Exception as e:
        log(1, "teleport_create_bundle", False, str(e))

    try:
        r = await substrate_process_transcript(
            transcript="User decided to use FastAPI. User prefers async code."
        )
        log(
            1, "substrate_process_transcript", True, f"extracted {r['extracted_count']}"
        )
    except Exception as e:
        log(1, "substrate_process_transcript", False, str(e))

    try:
        r = await substrate_report()
        log(1, "substrate_report", True, f"memories={r['total_memories']}")
    except Exception as e:
        log(1, "substrate_report", False, str(e))

    try:
        r = await memory_decay(factor=0.95)
        log(1, "memory_decay", True, f"removed={r['memories_removed']}")
    except Exception as e:
        log(1, "memory_decay", False, str(e))

    try:
        r = await substrate_end_session(summary="Stress test phase 1 complete")
        log(1, "substrate_end_session", True, f"session={r['session_id']}")
    except Exception as e:
        log(1, "substrate_end_session", False, str(e))


async def run_phase2():
    print("phase 2")

    try:
        await memory_add(content="")
        log(
            2, "memory_add empty content", False, "Should have raised error but didn't!"
        )
    except ValueError:
        log(2, "memory_add empty content", True, "Correctly raised ValueError")
    except Exception as e:
        log(2, "memory_add empty content", False, f"Wrong error: {e}")

    try:
        r = await memory_search(query="")
        log(2, "memory_search empty query", True, f"returned {r['count']} (graceful)")
    except Exception as e:
        log(2, "memory_search empty query", False, str(e))

    try:
        await ledger_record(tool_used="")
        log(
            2,
            "ledger_record empty tool_used",
            False,
            "Should have raised error but didn't!",
        )
    except ValueError:
        log(2, "ledger_record empty tool_used", True, "Correctly raised ValueError")
    except Exception as e:
        log(2, "ledger_record empty tool_used", False, f"Wrong error: {e}")

    try:
        await substrate_start_session(session_id="")
        log(
            2,
            "substrate_start_session empty id",
            False,
            "Should have raised error but didn't!",
        )
    except ValueError:
        log(2, "substrate_start_session empty id", True, "Correctly raised ValueError")
    except Exception as e:
        log(2, "substrate_start_session empty id", False, f"Wrong error: {e}")

    try:
        await memory_add()
        log(2, "memory_add no args", False, "Should have raised error but didn't!")
    except (ValueError, KeyError, TypeError):
        log(2, "memory_add no args", True, "Correctly raised error")
    except Exception as e:
        log(2, "memory_add no args", False, f"Wrong error: {type(e).__name__}: {e}")

    try:
        await ledger_outcome()
        log(2, "ledger_outcome no args", False, "Should have raised error but didn't!")
    except (ValueError, KeyError, TypeError):
        log(2, "ledger_outcome no args", True, "Correctly raised error")
    except Exception as e:
        log(2, "ledger_outcome no args", False, f"Wrong error: {type(e).__name__}: {e}")

    try:
        await teleport_rehydrate()
        log(
            2,
            "teleport_rehydrate no args",
            False,
            "Should have raised error but didn't!",
        )
    except (ValueError, KeyError, TypeError):
        log(2, "teleport_rehydrate no args", True, "Correctly raised error")
    except Exception as e:
        log(
            2,
            "teleport_rehydrate no args",
            False,
            f"Wrong error: {type(e).__name__}: {e}",
        )

    try:
        for i in range(10):
            await memory_add(content="DUPLICATE MEMORY TEST", memory_type="fact")
        r = await memory_search(query="DUPLICATE MEMORY TEST")
        log(2, "memory_add x10 duplicates", True, f"stored {r['count']} duplicates")
    except Exception as e:
        log(2, "memory_add x10 duplicates", False, str(e))

    try:
        await substrate_start_session(session_id="dup-session", project="dup-test")
        await substrate_start_session(session_id="dup-session", project="dup-test")
        log(
            2,
            "substrate_start_session x2 same id",
            True,
            "No crash on duplicate session",
        )
    except Exception as e:
        log(2, "substrate_start_session x2 same id", False, str(e))

    try:
        for i in range(5):
            await trust_record(action="approval", tool_name="duplicate_tool")
        r = await trust_get(tool_name="duplicate_tool")
        log(
            2,
            "trust_record x5 same tool",
            True,
            f"approval_count={r['approval_count']}",
        )
    except Exception as e:
        log(2, "trust_record x5 same tool", False, str(e))

    try:
        big = "X" * 10000
        r = await memory_add(content=big, memory_type="fact")
        log(2, "memory_add 10k chars", True, f"id={r['id'][:8]}")
    except Exception as e:
        log(2, "memory_add 10k chars", False, str(e))

    try:
        big = "Y" * 5000
        r = await ledger_record(tool_used="big-tool", reasoning=big)
        log(2, "ledger_record 5k reasoning", True, f"id={r['id']}")
    except Exception as e:
        log(2, "ledger_record 5k reasoning", False, str(e))

    try:
        big = "User said: " + "Z" * 20000
        r = await substrate_process_transcript(transcript=big)
        log(
            2, "process_transcript 20k chars", True, f"extracted {r['extracted_count']}"
        )
    except Exception as e:
        log(2, "process_transcript 20k chars", False, str(e))

    try:
        r = await memory_add(
            content="Test with émojis 🧠💾🔥 and ünïcödé", memory_type="fact"
        )
        log(2, "memory_add unicode+emoji", True, f"id={r['id'][:8]}")
    except Exception as e:
        log(2, "memory_add unicode+emoji", False, str(e))

    try:
        r = await memory_add(content="'; DROP TABLE memories; --", memory_type="fact")
        log(2, "memory_add sql injection", True, "stored safely (parametrized)")
    except Exception as e:
        log(2, "memory_add sql injection", False, str(e))

    try:
        r = await memory_add(
            content='{"key": "value", "nested": {"a": 1}}', memory_type="fact"
        )
        log(2, "memory_add JSON content", True, f"id={r['id'][:8]}")
    except Exception as e:
        log(2, "memory_add JSON content", False, str(e))

    try:
        r = await memory_add(content="line1\nline2\ttabbed\nline3", memory_type="fact")
        log(2, "memory_add newlines+tabs", True, f"id={r['id'][:8]}")
    except Exception as e:
        log(2, "memory_add newlines+tabs", False, str(e))

    try:
        r = await memory_add(content="bad type test", memory_type="invalid_type_xyz")
        log(2, "memory_add invalid memory_type", True, f"defaulted to {r['type']}")
    except Exception as e:
        log(2, "memory_add invalid memory_type", False, str(e))

    try:
        await trust_record(action="invalid_action", tool_name="test_tool")
        log(
            2,
            "trust_record invalid action",
            False,
            "Should have raised error but didn't!",
        )
    except ValueError:
        log(2, "trust_record invalid action", True, "Correctly raised ValueError")
    except Exception as e:
        log(2, "trust_record invalid action", False, f"Wrong error: {e}")

    try:
        r = await memory_decay(factor=999)
        log(
            2,
            "memory_decay factor=999",
            False,
            f"Should have raised ValueError but got {r}",
        )
    except ValueError as e:
        log(2, "memory_decay factor=999", True, f"Correctly raised ValueError: {e}")
    except Exception as e:
        log(
            2,
            "memory_decay factor=999",
            False,
            f"Wrong error type: {type(e).__name__}: {e}",
        )

    try:
        r = await memory_decay(factor=-1)
        log(
            2,
            "memory_decay factor=-1",
            False,
            f"Should have raised ValueError but got {r}",
        )
    except ValueError as e:
        log(2, "memory_decay factor=-1", True, f"Correctly raised ValueError: {e}")
    except Exception as e:
        log(
            2,
            "memory_decay factor=-1",
            False,
            f"Wrong error type: {type(e).__name__}: {e}",
        )

    try:
        r = await memory_decay(factor="not_a_number")
        log(
            2,
            "memory_decay factor=string",
            False,
            f"Should have raised ValueError but got {r}",
        )
    except ValueError as e:
        log(2, "memory_decay factor=string", True, f"Correctly raised ValueError: {e}")
    except Exception as e:
        log(
            2,
            "memory_decay factor=string",
            False,
            f"Wrong error type: {type(e).__name__}: {e}",
        )

    try:
        tasks = [
            memory_add(content=f"Concurrent memory {i}", memory_type="fact")
            for i in range(5)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        successes = sum(1 for r in results if not isinstance(r, Exception))
        log(2, "memory_add x5 concurrent", successes == 5, f"{successes}/5 succeeded")
    except Exception as e:
        log(2, "memory_add x5 concurrent", False, str(e))

    try:
        tasks = [trust_check(tool_name=f"concurrent_tool_{i}") for i in range(3)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        successes = sum(1 for r in results if not isinstance(r, Exception))
        log(2, "trust_check x3 concurrent", successes == 3, f"{successes}/3 succeeded")
    except Exception as e:
        log(2, "trust_check x3 concurrent", False, str(e))


async def run_phase3():
    print("phase 3")
    try:
        await memory_add(
            content="Project A secret", project="project-alpha", memory_type="fact"
        )
        await memory_add(
            content="Project B secret", project="project-beta", memory_type="fact"
        )

        r_a = await memory_search(query="Project A secret", project="project-alpha")
        r_b = await memory_search(query="Project B secret", project="project-beta")

        a_has_a = any("Project A secret" in m["content"] for m in r_a["memories"])
        a_has_b = any("Project B secret" in m["content"] for m in r_a["memories"])
        b_has_b = any("Project B secret" in m["content"] for m in r_b["memories"])
        b_has_a = any("Project A secret" in m["content"] for m in r_b["memories"])

        if a_has_a and not a_has_b and b_has_b and not b_has_a:
            log(
                3,
                "project isolation",
                True,
                "A does not leak to B, B does not leak to A - no leakage",
            )
        else:
            log(
                3,
                "project isolation",
                False,
                f"A got A={a_has_a}, A got B={a_has_b}, B got B={b_has_b}, B got A={b_has_a}",
            )
    except Exception as e:
        log(3, "project isolation", False, str(e))

    try:
        r = await memory_search(query="secret")
        has_both = any(
            "Project A secret" in m["content"] for m in r["memories"]
        ) and any("Project B secret" in m["content"] for m in r["memories"])
        log(
            3,
            "search no filter returns all",
            has_both,
            f"found {r['count']} (should include both projects)",
        )
    except Exception as e:
        log(3, "search no filter returns all", False, str(e))


async def run_phase4():
    print("phase 4")
    try:
        for i in range(5):
            await memory_add(
                content=f"Teleport memory {i}: test data",
                memory_type=["fact", "preference", "pattern"][i % 3],
                project="teleport-test",
            )

        await ledger_record(
            tool_used="teleport-tool-1",
            reasoning="testing teleport",
            project="teleport-test",
        )
        await ledger_record(
            tool_used="teleport-tool-2",
            reasoning="testing teleport again",
            project="teleport-test",
        )
        await ledger_record(
            tool_used="teleport-tool-3",
            reasoning="third decision",
            project="teleport-test",
        )

        await trust_record(
            action="approval", tool_name="teleport-trust-1", project="teleport-test"
        )
        await trust_record(
            action="approval", tool_name="teleport-trust-2", project="teleport-test"
        )
        await trust_record(
            action="denial", tool_name="teleport-trust-3", project="teleport-test"
        )

        bundle = await teleport_create_bundle(
            source_host="machine-A", target_host="machine-B"
        )
        bundle_json = bundle["serialized"]

        result = await teleport_rehydrate(bundle_json=bundle_json)
        log(
            4,
            "teleport round-trip",
            result["memories_restored"] > 0,
            f"memories={result['memories_restored']}, sessions={result['sessions_restored']}, trust={result['trust_restored']}",
        )
    except Exception as e:
        log(4, "teleport round-trip", False, f"{type(e).__name__}: {e}")

    try:
        r = await memory_search(query="teleport", project="teleport-test")
        log(
            4,
            "verify teleport memories",
            r["count"] > 0,
            f"found {r['count']} teleport memories",
        )
    except Exception as e:
        log(4, "verify teleport memories", False, str(e))


async def run_phase5():
    print("phase 5")
    try:
        await substrate_start_session(session_id="lifecycle-001")
        await memory_add(content="Lifecycle memory 1", project="lifecycle-test")
        await memory_add(content="Lifecycle memory 2", project="lifecycle-test")
        await memory_add(content="Lifecycle memory 3", project="lifecycle-test")

        await ledger_record(
            tool_used="lifecycle-tool",
            reasoning="testing lifecycle",
            project="lifecycle-test",
            session_id="lifecycle-001",
        )
        await ledger_record(
            tool_used="lifecycle-tool-2",
            reasoning="second decision",
            project="lifecycle-test",
            session_id="lifecycle-001",
        )

        await substrate_process_transcript(
            transcript="User: I want to build a REST API with FastAPI.\nAI: Great choice! FastAPI has excellent async support.\nUser: Yes, and I prefer type hints everywhere.",
            session_id="lifecycle-001",
            project="lifecycle-test",
        )

        r = await substrate_end_session(
            summary="Lifecycle test session complete",
            key_decisions=["Chose FastAPI", "Used type hints"],
            tools_used=[
                "memory_add",
                "ledger_record",
                "substrate_process_transcript",
            ],
            input_tokens=1500,
            output_tokens=800,
        )
        log(
            5,
            "end session 001",
            True,
            f"session={r['session_id']}, tokens_in={r['input_tokens']}",
        )
    except Exception as e:
        log(5, "end session 001", False, str(e))

    try:
        await substrate_start_session(session_id="lifecycle-002")
        r = await memory_get_context(query="lifecycle test", project="lifecycle-test")
        log(
            5,
            "memories persist across sessions",
            r["count"] > 0,
            f"found {r['count']} memories",
        )
    except Exception as e:
        log(5, "memories persist across sessions", False, str(e))

    try:
        r = await substrate_report()
        log(
            5,
            "session count increased",
            r["total_sessions"] >= 2,
            f"total_sessions={r['total_sessions']}",
        )
    except Exception as e:
        log(5, "session count increased", False, str(e))


async def main():
    print("cognex stress test")

    start = time.time()

    await run_phase1()
    await run_phase2()
    await run_phase3()
    await run_phase4()
    await run_phase5()

    elapsed = time.time() - start

    print(f"total tests: {len(REPORT)}")
    print(f"passed: {sum(1 for r in REPORT if r['status'])}")
    print(f"failed: {sum(1 for r in REPORT if not r['status'])}")
    print(f"time: {elapsed:.2f}s")

    for phase_num in range(1, 6):
        phase_tests = [r for r in REPORT if r["phase"] == phase_num]
        if phase_tests:
            passed = sum(1 for r in phase_tests if r["status"])
            total = len(phase_tests)
            print(f"phase {phase_num}: {passed}/{total} passed")
            for r in phase_tests:
                icon = "[PASS]" if r["status"] else "[FAIL]"
                print(f"  {icon} {r['tool']}: {r['notes'][:100]}")

    failures = [r for r in REPORT if not r["status"]]
    if failures:
        print("bugs found")
        for i, f in enumerate(failures, 1):
            print(f"bug #{i}:")
            print(f"tool: {f['tool']}")
            print(f"phase: {f['phase']}")
            print(f"issue: {f['notes']}")
    else:
        print("no bugs found")

    verdict = (
        "Ready to publish"
        if len(failures) == 0
        else f"Not ready - {len(failures)} test(s) failed"
    )
    print(f"overall verdict: {verdict}")


if __name__ == "__main__":
    asyncio.run(main())
