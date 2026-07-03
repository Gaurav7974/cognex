
from typing import Any

from cognex_mcp.context import CognexContext


async def swarm_compile_intent(
    intent: str,
    project: str | None = None,
) -> dict[str, Any]:
    ctx = CognexContext.get_instance()

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
