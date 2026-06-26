"""Consolidator tools - exposes the memory consolidation MCP tool."""

from typing import Any

from cognex_mcp.context import CognexContext
from cognex_mcp.sanitizer import sanitize_project
from cognex_mcp.tools.dispatcher import run_in_thread


async def memory_consolidate(
    project: str = "",
    min_cluster_size: int = 5,
) -> dict[str, Any]:
    """Consolidate episodic memories into clusters and promote stable ones to schemas."""
    project = sanitize_project(project)
    min_cluster_size = int(min_cluster_size)

    ctx = CognexContext.get_instance()
    from cognex.consolidator import MemoryConsolidator

    clusters = await run_in_thread(
        MemoryConsolidator.consolidate,
        ctx.engine.store,
        project=project,
        min_cluster_size=min_cluster_size,
    )

    # Automatically check and promote any stable clusters to schemas
    def find_and_promote() -> list[dict[str, Any]]:
        promoted = []
        with ctx.engine.store._connect() as conn:
            try:
                rows = conn.execute("SELECT cluster_id FROM memory_clusters").fetchall()
                cluster_ids = [r["cluster_id"] for r in rows]
            except Exception:
                cluster_ids = []

        for cid in cluster_ids:
            # promote_cluster_to_schema handles the 30-day stability check internally
            schema = MemoryConsolidator.promote_cluster_to_schema(
                cid, ctx.engine.store
            )
            if schema:
                promoted.append(schema)
        return promoted

    promoted = await run_in_thread(find_and_promote)

    return {
        "status": "success",
        "clusters_created": len(clusters),
        "clusters": [
            {
                "cluster_id": c["cluster_id"],
                "project": c["project"],
                "theme": c["theme"],
                "summary": c["summary"],
                "count": len(c["source_memory_ids"]),
            }
            for c in clusters
        ],
        "schemas_promoted": len(promoted),
        "schemas": promoted,
    }
