"""Full demo: All 5 layers of the Cognitive Substrate working together."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from substrate import (
    CognitiveSubstrate,
    TrustGradientEngine, TrustLevel,
    DecisionLedger,
    TeleportProtocol, TeleportBundle,
    IntentCompiler, AgentRole,
)


def main():
    base = Path(__file__).parent / "demo_full.db"
    # Clean start
    for f in base.parent.glob("demo_full*"):
        f.unlink(missing_ok=True)

    substrate = CognitiveSubstrate(db_path=base)
    trust = TrustGradientEngine(db_path=base.with_suffix(".trust.db"))
    ledger = DecisionLedger(db_path=base.with_suffix(".ledger.db"))
    teleport = TeleportProtocol()
    compiler = IntentCompiler()

    # ================================================================
    # LAYER 1: MEMORY — The AI that remembers
    # ================================================================
    print("=" * 70)
    print("LAYER 1: MEMORY — The AI That Remembers")
    print("=" * 70)

    print("\n--- Session 1: First time meeting the AI ---")
    memories = substrate.start_session("session-1", project="ecommerce-api")
    print(f"AI: 'Hello! I have no memories of you yet. What are we building?'")

    transcript_1 = """
User: We're building an e-commerce REST API.
User: I prefer FastAPI over Flask — it's faster and has async.
User: We use PostgreSQL and Redis for caching.
User: I always use pytest, never unittest.
User: We chose Stripe for payments because their docs are better.
User: Last time we deployed to AWS ECS, staging had memory limit issues.
"""
    result = substrate.process_transcript(transcript_1, session_id="session-1", project="ecommerce-api")
    print(f"\nAI processed the conversation and extracted {result.count} memories:")
    for m in result.memories:
        print(f"  [{m.type.value:12s}] {m.content[:70]}")

    substrate.end_session(summary="Set up e-commerce API project")

    print("\n--- Session 2: The AI remembers ---")
    memories = substrate.start_session("session-2", project="ecommerce-api")
    print(f"AI: 'Welcome back. I remember {len(memories)} things about this project.'")
    for m in memories[:4]:
        print(f"  - {m.content[:70]}")

    # ================================================================
    # LAYER 2: TRUST — The permission system that learns
    # ================================================================
    print("\n" + "=" * 70)
    print("LAYER 2: TRUST — The Permission System That Learns")
    print("=" * 70)

    print("\n--- First time using each tool ---")
    tools = ["FileReadTool", "BashTool", "WebFetchTool", "FileEditTool"]
    for tool in tools:
        needs = trust.requires_approval(tool, project="ecommerce-api")
        status = "ASK" if needs else "AUTO"
        print(f"  {tool:20s} -> {status} (trust: {trust.get_trust(tool, project='ecommerce-api').trust_level.name})")

    print("\n--- After 5 approvals of FileReadTool ---")
    for i in range(5):
        trust.record_approval("FileReadTool", f"read file {i}", project="ecommerce-api")
    needs = trust.requires_approval("FileReadTool", project="ecommerce-api")
    status = "ASK" if needs else "AUTO"
    record = trust.get_trust("FileReadTool", project="ecommerce-api")
    print(f"  FileReadTool         -> {status} (trust: {record.trust_level.name}, approvals: {record.approval_count})")

    print("\n--- After a violation ---")
    trust.record_violation("BashTool", "deleted wrong file", project="ecommerce-api")
    record = trust.get_trust("BashTool", project="ecommerce-api")
    print(f"  BashTool             -> ASK (trust: {record.trust_level.name}, violations: {record.violation_count})")

    print(f"\n  Overall approval rate: {trust.approval_rate(project='ecommerce-api'):.0%}")

    # ================================================================
    # LAYER 3: DECISION LEDGER — Why did the AI choose that?
    # ================================================================
    print("\n" + "=" * 70)
    print("LAYER 3: DECISION LEDGER — Why Did The AI Choose That?")
    print("=" * 70)

    print("\n--- Recording decisions ---")
    d1 = ledger.record(
        tool_used="BashTool",
        alternatives=["FileEditTool", "PluginTool"],
        reasoning="BashTool is 40% faster for bulk file operations",
        context="Migrating 50 config files",
        project="ecommerce-api",
        session_id="session-1",
    )
    print(f"  Decision: Use BashTool instead of FileEditTool")
    print(f"  Why: {d1.reasoning}")

    ledger.record_outcome(d1.id, "All 50 files migrated successfully", success=True)

    d2 = ledger.record(
        tool_used="WebFetchTool",
        alternatives=["cached docs"],
        reasoning="Needed latest Stripe API docs, cache was stale",
        context="Setting up payment integration",
        project="ecommerce-api",
        session_id="session-2",
    )
    ledger.record_outcome(d2.id, "Got updated docs, integration worked", success=True)
    print(f"  Decision: Use WebFetchTool instead of cached docs")
    print(f"  Why: {d2.reasoning}")

    print("\n--- Asking: 'What did I decide about file migration?' ---")
    similar = ledger.find_similar("file migration config", project="ecommerce-api")
    for d in similar:
        print(f"  {d.as_narrative()}")

    print("\n--- Successful decisions ---")
    for d in ledger.get_successful(project="ecommerce-api"):
        print(f"  [OK] {d.tool_used} -> {d.outcome[:60]}")

    # ================================================================
    # LAYER 4: TELEPORT — Move the AI's brain between machines
    # ================================================================
    print("\n" + "=" * 70)
    print("LAYER 4: TELEPORT — Move The AI's Brain Between Machines")
    print("=" * 70)

    print("\n--- Creating teleport bundle from laptop ---")
    bundle = teleport.create_bundle(
        substrate=substrate,
        source_host="laptop",
        target_host="production-server",
        pending_tasks=("finish payment integration", "add rate limiting"),
        last_action="reading Stripe API docs",
        model_name="claude-sonnet-4",
    )
    print(f"  Bundle ID: {bundle.bundle_id}")
    print(f"  Session: {bundle.session_id}")
    print(f"  Project: {bundle.project}")
    print(f"  Memories: {len(bundle.memory_ids)} entries")
    print(f"  Pending tasks: {len(bundle.pending_tasks)}")
    print(f"  Signature valid: {bundle.verify()}")

    # Save and "transfer"
    bundle_path = base.parent / "teleport.json"
    bundle.save_to_file(bundle_path)
    print(f"\n  Saved to: {bundle_path}")

    # Rehydrate on "target machine"
    print("\n--- Rehydrating on production server ---")
    target_substrate = CognitiveSubstrate(db_path=base.with_suffix(".target.db"))
    loaded = TeleportBundle.load_from_file(bundle_path)
    report = teleport.rehydrate(loaded, target_substrate)
    print(f"  Status: {report['status']}")
    print(f"  Restored: {', '.join(report['restored'])}")
    print(f"  Ready for: {report['ready_for']}")

    # ================================================================
    # LAYER 5: SWARM — "Just tell it what you want"
    # ================================================================
    print("\n" + "=" * 70)
    print("LAYER 5: SWARM — 'Just Tell It What You Want'")
    print("=" * 70)

    intents = [
        "Build a REST API with authentication",
        "Migrate from Flask to FastAPI",
        "Fix the database connection error",
        "Deploy to production",
    ]

    for intent in intents:
        print(f"\n--- User says: '{intent}' ---")
        plan = compiler.compile(intent, project="ecommerce-api")
        print(plan.as_text())
        print()

    # ================================================================
    # FINAL: All layers together
    # ================================================================
    print("=" * 70)
    print("ALL LAYERS TOGETHER — What a real session looks like")
    print("=" * 70)

    print("""
User: "Build the payment endpoint for our e-commerce API"

What happens behind the scenes:

1. MEMORY loads context:
   - "User prefers FastAPI"
   - "Uses Stripe for payments"
   - "PostgreSQL + Redis setup"
   - "AWS ECS deployment"

2. TRUST checks permissions:
   - FileReadTool: AUTO (trusted, 5+ approvals)
   - BashTool: ASK (violation history)
   - WebFetchTool: AUTO (trusted for Stripe docs)

3. LEDGER checks past decisions:
   - "Last time you set up payments, you chose Stripe"
   - "That decision succeeded — integration worked"

4. SWARM decomposes the task:
   - Explorer: Map existing codebase
   - Planner: Design payment endpoint structure
   - Builder: Implement endpoints (2 parallel)
   - Verifier: Test payment flows
   - Fixer: Address any issues

5. TELEPORT can move this work to any machine:
   - Serialize state -> transfer -> resume

The user just said what they wanted. The system handled the rest.
""")

    # Cleanup — close connections first
    substrate.store.close()
    trust.close()
    ledger.close()
    teleport.close()
    import gc; gc.collect()
    import time; time.sleep(0.3)
    for f in base.parent.glob("demo_full*"):
        try:
            f.unlink()
        except PermissionError:
            pass
    bundle_path.unlink(missing_ok=True)
    print("Demo complete. All files cleaned up.")


if __name__ == "__main__":
    main()
