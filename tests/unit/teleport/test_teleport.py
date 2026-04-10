from __future__ import annotations

from substrate import CognitiveSubstrate, TeleportBundle, TeleportProtocol


class TestTeleportBundle:
    def test_serialize_deserialize(self):
        bundle = TeleportBundle(
            session_id="s1",
            project="api",
            memory_ids=("m1", "m2", "m3"),
            pending_tasks=("task1", "task2"),
            last_action="running tests",
        )
        serialized = bundle.serialize()
        restored = TeleportBundle.deserialize(serialized)
        assert restored.session_id == bundle.session_id
        assert restored.memory_ids == bundle.memory_ids
        assert restored.pending_tasks == bundle.pending_tasks

    def test_sign_and_verify(self):
        bundle = TeleportBundle(session_id="s1", project="api").sign()
        assert bundle.verify() is True

    def test_tampered_bundle_fails_verify(self):
        bundle = TeleportBundle(session_id="s1", project="api").sign()
        tampered = TeleportBundle(
            bundle_id=bundle.bundle_id,
            version=bundle.version,
            created_at=bundle.created_at,
            source_host=bundle.source_host,
            target_host=bundle.target_host,
            session_id="TAMPERED",
            project=bundle.project,
            memory_ids=bundle.memory_ids,
            session_summary=bundle.session_summary,
            trust_records=bundle.trust_records,
            decision_ids=bundle.decision_ids,
            workspace_context=bundle.workspace_context,
            pending_tasks=bundle.pending_tasks,
            last_action=bundle.last_action,
            model_name=bundle.model_name,
            tool_claims=bundle.tool_claims,
            signature=bundle.signature,
        )
        assert tampered.verify() is False

    def test_unsigned_bundle_fails_verify(self):
        bundle = TeleportBundle(session_id="s1")
        assert bundle.verify() is False

    def test_save_and_load_file(self, tmp_path):
        bundle = TeleportBundle(session_id="s1", project="api").sign()
        path = bundle.save_to_file(tmp_path / "teleport.json")
        loaded = TeleportBundle.load_from_file(path)
        assert loaded.session_id == bundle.session_id
        assert loaded.verify() is True


class TestTeleportProtocol:
    def test_create_bundle(self, tmp_path):
        substrate = CognitiveSubstrate(db_path=tmp_path / "sub.db")
        substrate.start_session("s1", project="api")
        substrate.process_transcript("I prefer FastAPI", project="api")

        protocol = TeleportProtocol()
        bundle = protocol.create_bundle(
            substrate=substrate,
            source_host="laptop",
            target_host="server",
            pending_tasks=("finish API", "add tests"),
            last_action="reading config",
        )
        assert bundle.session_id == "s1"
        assert bundle.project == "api"
        assert len(bundle.memory_ids) > 0
        assert bundle.verify() is True

    def test_rehydrate_success(self, tmp_path):
        substrate = CognitiveSubstrate(db_path=tmp_path / "sub.db")
        substrate.start_session("s1", project="api")

        protocol = TeleportProtocol()
        bundle = protocol.create_bundle(
            substrate=substrate,
            source_host="laptop",
            target_host="server",
        )
        target_substrate = CognitiveSubstrate(db_path=tmp_path / "target.db")
        report = protocol.rehydrate(bundle, target_substrate)
        assert report["status"] == "success"
        assert report["bundle_id"] == bundle.bundle_id

    def test_rehydrate_invalid_bundle(self, tmp_path):
        substrate = CognitiveSubstrate(db_path=tmp_path / "sub.db")
        protocol = TeleportProtocol()
        bundle = TeleportBundle(session_id="s1")
        report = protocol.rehydrate(bundle, substrate)
        assert report["status"] == "failed"
