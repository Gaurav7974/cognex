import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from cognex import CognexEngine, MemoryType


def main():
    db = Path(__file__).parent / "demo_memory.db"
    db.unlink(missing_ok=True)
    engine = CognexEngine(db_path=db)
    print("=" * 60)
    print("SESSION 1: Setting up the project")
    print("=" * 60)
    memories = engine.start_session("session-1", project="my-api")
    print(
        f"Starting session. Loaded {len(memories)} memories (expected: 0 — first time)"
    )
    transcript_1 = "\nUser: I'm building a REST API for our e-commerce platform.\nUser: I prefer FastAPI over Flask — it's faster and has better async support.\nUser: We use PostgreSQL for the database and Redis for caching.\nUser: The API runs on port 8000 and uses JWT authentication.\nUser: I always use pytest for testing, never unittest.\nUser: I don't like using ORM mappers — I prefer raw SQL with asyncpg.\nAssistant: Got it. I'll remember your preferences.\nUser: We chose Stripe for payments instead of PayPal because of better API docs.\nAssistant: Noted. What's the deployment target?\nUser: We deploy to AWS ECS. The staging environment had issues with memory limits last time.\n"
    result = engine.process_transcript(
        transcript_1, session_id="session-1", project="my-api"
    )
    print(f"Extracted {result.count} memories from session 1:")
    for m in result.memories:
        print(f"  [{m.type.value}] {m.content[:80]}")
    engine.end_session(
        summary="Set up e-commerce API project. User prefers FastAPI, pytest, raw SQL.",
        key_decisions=(
            "Chose FastAPI over Flask",
            "Chose Stripe over PayPal",
            "Chose raw SQL over ORM",
        ),
        tools_used=("FileReadTool", "BashTool"),
        errors="staging memory limit exceeded",
    )
    print("\n" + "=" * 60)
    print("SESSION 2: User returns — the AI remembers")
    print("=" * 60)
    memories = engine.start_session("session-2", project="my-api")
    print(f"Starting session. Loaded {len(memories)} relevant memories:")
    for m in memories:
        print(f"  [{m.type.value}] {m.content[:80]}")
    print("\nAI would say:")
    print("  'Welcome back to the my-api project. I remember you prefer FastAPI,")
    print("   use PostgreSQL with raw SQL, and deploy to AWS ECS.'")
    transcript_2 = "\nUser: Let's add a new endpoint for the product catalog.\nUser: Actually, I changed my mind about the ORM — let's try SQLAlchemy this time.\nUser: Also, we're switching from AWS ECS to Google Cloud Run.\nAssistant: Interesting — you previously had issues with memory limits on staging.\nUser: Yeah, that's why we're moving. Cloud Run handles scaling better.\n"
    result = engine.process_transcript(
        transcript_2, session_id="session-2", project="my-api"
    )
    print(f"\nExtracted {result.count} new memories:")
    for m in result.memories:
        print(f"  [{m.type.value}] {m.content[:80]}")
    print("\n" + "=" * 60)
    print("SESSION 3: Decision history — 'What did we decide before?'")
    print("=" * 60)
    engine.start_session("session-3", project="my-api")
    similar = engine.find_similar_decisions("choosing between frameworks")
    print(f"Found {len(similar)} past decisions about frameworks:")
    for m in similar:
        print(f"  [{m.type.value}] {m.content[:80]}")
    print("\n" + "=" * 60)
    print("COGNEX ENGINE REPORT")
    print("=" * 60)
    report = engine.report()
    print(report.as_text())
    engine.store.close()
    import gc

    gc.collect()
    import time

    time.sleep(0.2)
    db.unlink(missing_ok=True)
    print("\nDemo complete. Memory database cleaned up.")


if __name__ == "__main__":
    main()
