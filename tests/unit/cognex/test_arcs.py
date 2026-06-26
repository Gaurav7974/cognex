import pytest
from datetime import datetime, timezone, timedelta
import json
from cognex import SessionSnapshot
from cognex.arcs import SessionArcManager


def test_session_arc_lifecycle(engine):
    # 1. Start a session to create the first arc
    arc = SessionArcManager.get_or_create_arc("s1", "project-x", engine.store)
    assert arc["arc_id"] is not None
    assert arc["project"] == "project-x"
    assert arc["session_ids"] == ["s1"]
    assert arc["status"] == "active"

    # 2. Get active arc
    active_arc = SessionArcManager.get_active_arc("project-x", engine.store)
    assert active_arc is not None
    assert active_arc["arc_id"] == arc["arc_id"]

    # 3. Create another session within 7 days -> should join the same arc
    arc2 = SessionArcManager.get_or_create_arc("s2", "project-x", engine.store)
    assert arc2["arc_id"] == arc["arc_id"]
    assert arc2["session_ids"] == ["s1", "s2"]

    # 4. Mock a session snapshot with summary and save it to test summarize_arc
    snapshot = SessionSnapshot(
        session_id="s1",
        project="project-x",
        summary="Designed the database schema.",
        started_at=datetime.now(timezone.utc),
    )
    engine.store.save_session(snapshot)

    snapshot2 = SessionSnapshot(
        session_id="s2",
        project="project-x",
        summary="Implemented the backend server.",
        started_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    engine.store.save_session(snapshot2)

    # 5. Summarize the arc
    summary = SessionArcManager.summarize_arc(arc["arc_id"], engine.store)
    assert "Designed the database schema" in summary
    assert "Implemented the backend server" in summary

    # 6. Close the arc
    success = SessionArcManager.close_arc(arc["arc_id"], engine.store)
    assert success is True

    # 7. Verify it is closed
    active_arc = SessionArcManager.get_active_arc("project-x", engine.store)
    assert active_arc is None

    # 8. Start a new session -> should create a new arc because the old one is closed
    arc3 = SessionArcManager.get_or_create_arc("s3", "project-x", engine.store)
    assert arc3["arc_id"] != arc["arc_id"]
    assert arc3["session_ids"] == ["s3"]
