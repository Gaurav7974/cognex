"""Demo: Watch the Cognitive Substrate remember things across sessions."""

from pathlib import Path
import sys

# Add src to path for demo
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from substrate import CognitiveSubstrate, MemoryType


def main():
    db = Path(__file__).parent / "demo_memory.db"
    db.unlink(missing_ok=True)  # Clean start

    substrate = CognitiveSubstrate(db_path=db)

    # ── Session 1: User sets up a project ─────────────────────
    print("=" * 60)
    print("SESSION 1: Setting up the project")
    print("=" * 60)

    memories = substrate.start_session("session-1", project="my-api")
    print(f"Starting session. Loaded {len(memories)} memories (expected: 0 — first time)")

    transcript_1 = """
User: I'm building a REST API for our e-commerce platform.
User: I prefer FastAPI over Flask — it's faster and has better async support.
User: We use PostgreSQL for the database and Redis for caching.
User: The API runs on port 8000 and uses JWT authentication.
User: I always use pytest for testing, never unittest.
User: I don't like using ORM mappers — I prefer raw SQL with asyncpg.
Assistant: Got it. I'll remember your preferences.
User: We chose Stripe for payments instead of PayPal because of better API docs.
Assistant: Noted. What's the deployment target?
User: We deploy to AWS ECS. The staging environment had issues with memory limits last time.
"""

    result = substrate.process_transcript(transcript_1, session_id="session-1", project="my-api")
    print(f"Extracted {result.count} memories from session 1:")
    for m in result.memories:
        print(f"  [{m.type.value}] {m.content[:80]}")

    substrate.end_session(
        summary="Set up e-commerce API project. User prefers FastAPI, pytest, raw SQL.",
        key_decisions=("Chose FastAPI over Flask", "Chose Stripe over PayPal", "Chose raw SQL over ORM"),
        tools_used=("FileReadTool", "BashTool"),
        errors=("staging memory limit exceeded"),
    )

    # ── Session 2: User returns days later ────────────────────
    print("\n" + "=" * 60)
    print("SESSION 2: User returns — the AI remembers")
    print("=" * 60)

    memories = substrate.start_session("session-2", project="my-api")
    print(f"Starting session. Loaded {len(memories)} relevant memories:")
    for m in memories:
        print(f"  [{m.type.value}] {m.content[:80]}")

    # The AI can now reference what it knows
    print("\nAI would say:")
    print("  'Welcome back to the my-api project. I remember you prefer FastAPI,")
    print("   use PostgreSQL with raw SQL, and deploy to AWS ECS.'")

    transcript_2 = """
User: Let's add a new endpoint for the product catalog.
User: Actually, I changed my mind about the ORM — let's try SQLAlchemy this time.
User: Also, we're switching from AWS ECS to Google Cloud Run.
Assistant: Interesting — you previously had issues with memory limits on staging.
User: Yeah, that's why we're moving. Cloud Run handles scaling better.
"""

    result = substrate.process_transcript(transcript_2, session_id="session-2", project="my-api")
    print(f"\nExtracted {result.count} new memories:")
    for m in result.memories:
        print(f"  [{m.type.value}] {m.content[:80]}")

    # ── Session 3: Show decision history ──────────────────────
    print("\n" + "=" * 60)
    print("SESSION 3: Decision history — 'What did we decide before?'")
    print("=" * 60)

    substrate.start_session("session-3", project="my-api")

    similar = substrate.find_similar_decisions("choosing between frameworks")
    print(f"Found {len(similar)} past decisions about frameworks:")
    for m in similar:
        print(f"  [{m.type.value}] {m.content[:80]}")

    # ── Report ────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("SUBSTRATE REPORT")
    print("=" * 60)
    report = substrate.report()
    print(report.as_text())

    # Cleanup — close connections first
    substrate.store.close()
    import gc; gc.collect()  # Force cleanup of any lingering refs
    import time; time.sleep(0.2)  # Let SQLite release locks
    db.unlink(missing_ok=True)
    print("\nDemo complete. Memory database cleaned up.")


if __name__ == "__main__":
    main()
