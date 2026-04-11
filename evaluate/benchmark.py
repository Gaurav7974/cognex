import sys
import asyncio
import statistics

sys.path.insert(0, "src")


def estimate_tokens(text: str) -> int:
    return len(text) // 4


async def run_benchmark():
    from substrate_mcp.tools import (
        handle_tool_call,
        substrate_start_session,
        substrate_end_session,
    )

    await substrate_start_session(session_id="benchmark-run", project="benchmark")

    production_memories = [
        {
            "content": "Always validate JWT expiry before processing protected request",
            "memory_type": "preference",
        },
        {
            "content": "Never commit .env files - use .env.example instead",
            "memory_type": "preference",
        },
        {
            "content": "Add tags to routers for OpenAPI grouping",
            "memory_type": "preference",
        },
        {"content": "Use snake_case for all field names", "memory_type": "preference"},
        {
            "content": "Add response_model to every endpoint",
            "memory_type": "preference",
        },
        {
            "content": "Use async def for route handlers - never def",
            "memory_type": "preference",
        },
        {
            "content": "Router prefix should start with /api/v1",
            "memory_type": "preference",
        },
        {
            "content": "Database is PostgreSQL 15 with asyncpg driver",
            "memory_type": "fact",
        },
        {"content": "Redis used for session caching only", "memory_type": "fact"},
        {"content": "Alembic used for all database migrations", "memory_type": "fact"},
        {
            "content": "Rate limiting via slowapi at 100 req/min per IP",
            "memory_type": "fact",
        },
        {
            "content": "Pydantic v2 used for request/response validation",
            "memory_type": "fact",
        },
        {
            "content": "API versioning via URL prefix not headers",
            "memory_type": "decision",
        },
        {
            "content": "Dependency injection via Depends() is preferred",
            "memory_type": "decision",
        },
        {
            "content": "Repository pattern used for all database operations",
            "memory_type": "pattern",
        },
        {
            "content": "Error responses use standard HTTPException",
            "memory_type": "pattern",
        },
        {
            "content": "JWT tokens stored in httpOnly cookies not localStorage",
            "memory_type": "pattern",
        },
        {
            "content": "All passwords hashed with bcrypt cost factor 12",
            "memory_type": "pattern",
        },
        {
            "content": "Settings loaded via pydantic BaseSettings from .env",
            "memory_type": "pattern",
        },
        {
            "content": "All endpoints return schemas not ORM models directly",
            "memory_type": "pattern",
        },
        {
            "content": "422 errors mean Pydantic validation failed check schema",
            "memory_type": "lesson",
        },
        {
            "content": "SQLAlchemy sessions must be closed in finally block",
            "memory_type": "lesson",
        },
        {
            "content": "Background tasks run after response is sent not before",
            "memory_type": "lesson",
        },
        {
            "content": "CORS middleware must be added before routing middleware",
            "memory_type": "lesson",
        },
        {
            "content": "Use lifespan context manager - on_startup deprecated",
            "memory_type": "lesson",
        },
    ]

    for mem in production_memories:
        await handle_tool_call(
            "memory_add",
            {
                "content": mem["content"],
                "memory_type": mem["memory_type"],
                "project": "benchmark",
            },
        )

    test_queries = [
        "preferences",
        "database decisions",
        "security patterns",
        "lessons learned",
        "API design",
    ]

    results = []
    for query in test_queries:
        manual_context = "\n".join([f"- {m['content']}" for m in production_memories])
        manual_tokens = estimate_tokens(manual_context)

        cognex_result = await handle_tool_call(
            "memory_get_context",
            {"query": query, "project": "benchmark", "format": "minimal", "limit": 5},
        )
        cognex_tokens = estimate_tokens(str(cognex_result))

        saving = (
            ((manual_tokens - cognex_tokens) / manual_tokens * 100)
            if manual_tokens > 0
            else 0
        )
        results.append(
            {
                "query": query,
                "manual": manual_tokens,
                "cognex": cognex_tokens,
                "saving": saving,
            }
        )

    avg_saving = statistics.mean([r["saving"] for r in results])
    avg_cognex_tokens = statistics.mean([r["cognex"] for r in results])
    avg_manual_tokens = statistics.mean([r["manual"] for r in results])

    print("Query                     Manual   Cognex   Saving")
    print("-" * 50)
    for r in results:
        print(
            f"{r['query']:<25} {r['manual']:>7} {r['cognex']:>7} {r['saving']:>6.0f}%"
        )
    print("-" * 50)
    print(
        f"Average                   {int(avg_manual_tokens):>7} {int(avg_cognex_tokens):>7} {avg_saving:>6.0f}%"
    )
    print(f"Token reduction: {avg_saving:.0f}%")
    print(f"Per query savings: ~{int(avg_manual_tokens - avg_cognex_tokens)} tokens")

    await substrate_end_session(
        session_id="benchmark-run", project="benchmark", summary="Benchmark completed"
    )

    return {
        "avg_saving": avg_saving,
        "avg_manual_tokens": int(avg_manual_tokens),
        "avg_cognex_tokens": int(avg_cognex_tokens),
    }


if __name__ == "__main__":
    results = asyncio.run(run_benchmark())
    print(f"Done. Avg saving: {results['avg_saving']:.1f}%")
