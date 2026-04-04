"""
Swarm tools - intent compilation and swarm planning.
"""

from typing import Any

from substrate_mcp.context import SubstrateContext


async def swarm_compile_intent(
    intent: str,
    project: str | None = None,
) -> dict[str, Any]:
    """Compile natural language intent into a swarm plan."""
    ctx = SubstrateContext.get_instance()

    plan = ctx.swarm.compile(intent=intent, project=project or "")

    return {
        "intent": intent,
        "project": project or "",
        "total_tasks": len(plan.subtasks),
        "is_complete": plan.is_complete,
        "has_failures": plan.has_failures,
        "progress": plan.progress,
        "subtasks": [
            {
                "id": task.id,
                "description": task.description,
                "role": task.role.value if task.role else None,
                "status": task.status.value,
                "depends_on": list(task.depends_on),
                "result": task.result,
                "error": task.error,
            }
            for task in plan.subtasks
        ],
        "text": plan.as_text(),
    }
