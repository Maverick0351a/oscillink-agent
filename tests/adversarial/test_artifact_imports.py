from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest


def test_selected_file_import_streams_to_artifact_store_with_sanitized_result(
    tmp_path: Path,
) -> None:
    from oscillink_agent.domain.imports import FileImportPolicy, FileImportSelection
    from oscillink_agent.storage.artifacts import LocalArtifactStore
    from oscillink_agent.storage.imports import GovernedFileImporter

    source_root = tmp_path / "selected"
    source_root.mkdir()
    content = b"governed evidence" * 1024
    (source_root / "evidence.txt").write_bytes(content)
    artifacts = LocalArtifactStore(tmp_path / "artifacts")
    importer = GovernedFileImporter(
        artifacts=artifacts,
        scopes={"user_selection": source_root},
        policy=FileImportPolicy.model_validate(
            {
                "schema_version": 1,
                "max_bytes": len(content) + 1,
                "chunk_bytes": 257,
                "allowed_extensions": (".txt",),
            }
        ),
    )

    result = importer.import_selected(
        FileImportSelection.model_validate(
            {
                "schema_version": 1,
                "scope_id": "user_selection",
                "target": "evidence.txt",
            }
        )
    )

    expected_reference = "sha256:" + hashlib.sha256(content).hexdigest()
    assert result.artifact_ref == expected_reference
    assert result.source_scope_id == "user_selection"
    assert result.source_name == "evidence.txt"
    assert result.media_type == "text/plain"
    assert result.logical_bytes == len(content)
    assert result.unique_physical_bytes == len(content)
    assert result.deduplicated is False
    assert artifacts.get(expected_reference) == content
    assert (source_root / "evidence.txt").read_bytes() == content
    assert "absolute" not in result.model_dump()
    assert str(source_root) not in result.model_dump_json()


def test_importer_rejects_subclassed_policy(tmp_path: Path) -> None:
    from oscillink_agent.domain.imports import FileImportPolicy
    from oscillink_agent.storage.artifacts import LocalArtifactStore
    from oscillink_agent.storage.imports import GovernedFileImporter

    class PolicySubclass(FileImportPolicy):
        pass

    source_root = tmp_path / "selected"
    source_root.mkdir()
    policy = PolicySubclass.model_validate(
        {
            "schema_version": 1,
            "max_bytes": 1024,
            "chunk_bytes": 64,
            "allowed_extensions": (".txt",),
        }
    )

    with pytest.raises(TypeError, match="exact FileImportPolicy"):
        GovernedFileImporter(
            artifacts=LocalArtifactStore(tmp_path / "artifacts"),
            scopes={"user_selection": source_root},
            policy=policy,
        )


def test_oversized_selection_publishes_no_artifact(tmp_path: Path) -> None:
    from oscillink_agent.domain.imports import FileImportPolicy, FileImportSelection
    from oscillink_agent.storage.artifacts import LocalArtifactStore
    from oscillink_agent.storage.imports import (
        GovernedFileImporter,
        ImportSourceTooLargeError,
    )

    source_root = tmp_path / "selected"
    source_root.mkdir()
    (source_root / "large.txt").write_bytes(b"12345")
    artifact_root = tmp_path / "artifacts"
    importer = GovernedFileImporter(
        artifacts=LocalArtifactStore(artifact_root),
        scopes={"user_selection": source_root},
        policy=FileImportPolicy.model_validate(
            {
                "schema_version": 1,
                "max_bytes": 4,
                "chunk_bytes": 2,
                "allowed_extensions": (".txt",),
            }
        ),
    )

    with pytest.raises(ImportSourceTooLargeError):
        importer.import_selected(
            FileImportSelection.model_validate(
                {
                    "schema_version": 1,
                    "scope_id": "user_selection",
                    "target": "large.txt",
                }
            )
        )

    assert [path for path in artifact_root.rglob("*") if path.is_file()] == []


def test_disallowed_extension_publishes_no_artifact(tmp_path: Path) -> None:
    from oscillink_agent.domain.imports import FileImportPolicy, FileImportSelection
    from oscillink_agent.storage.artifacts import LocalArtifactStore
    from oscillink_agent.storage.imports import (
        GovernedFileImporter,
        ImportExtensionNotAllowedError,
    )

    source_root = tmp_path / "selected"
    source_root.mkdir()
    (source_root / "payload.py").write_text("raise SystemExit", encoding="utf-8")
    artifact_root = tmp_path / "artifacts"
    importer = GovernedFileImporter(
        artifacts=LocalArtifactStore(artifact_root),
        scopes={"user_selection": source_root},
        policy=FileImportPolicy.model_validate(
            {
                "schema_version": 1,
                "max_bytes": 1024,
                "chunk_bytes": 64,
                "allowed_extensions": (".txt",),
            }
        ),
    )

    with pytest.raises(ImportExtensionNotAllowedError):
        importer.import_selected(
            FileImportSelection.model_validate(
                {
                    "schema_version": 1,
                    "scope_id": "user_selection",
                    "target": "payload.py",
                }
            )
        )

    assert [path for path in artifact_root.rglob("*") if path.is_file()] == []


def test_repeated_selection_reuses_physical_artifact(tmp_path: Path) -> None:
    from oscillink_agent.domain.imports import FileImportPolicy, FileImportSelection
    from oscillink_agent.storage.artifacts import LocalArtifactStore
    from oscillink_agent.storage.imports import GovernedFileImporter

    source_root = tmp_path / "selected"
    source_root.mkdir()
    (source_root / "evidence.txt").write_bytes(b"same immutable bytes")
    artifact_root = tmp_path / "artifacts"
    importer = GovernedFileImporter(
        artifacts=LocalArtifactStore(artifact_root),
        scopes={"user_selection": source_root},
        policy=FileImportPolicy.model_validate(
            {
                "schema_version": 1,
                "max_bytes": 1024,
                "chunk_bytes": 7,
                "allowed_extensions": (".txt",),
            }
        ),
    )
    selection = FileImportSelection.model_validate(
        {
            "schema_version": 1,
            "scope_id": "user_selection",
            "target": "evidence.txt",
        }
    )

    first = importer.import_selected(selection)
    second = importer.import_selected(selection)

    assert first.deduplicated is False
    assert first.unique_physical_bytes == first.logical_bytes
    assert second.deduplicated is True
    assert second.unique_physical_bytes == 0
    assert second.artifact_ref == first.artifact_ref
    assert len([path for path in artifact_root.rglob("*") if path.is_file()]) == 1


def test_symlink_selection_publishes_no_artifact(tmp_path: Path) -> None:
    from oscillink_agent.domain.imports import FileImportPolicy, FileImportSelection
    from oscillink_agent.storage.artifacts import LocalArtifactStore
    from oscillink_agent.storage.imports import GovernedFileImporter, ImportPathEscapeError

    source_root = tmp_path / "selected"
    source_root.mkdir()
    external = tmp_path / "external.txt"
    external.write_text("outside scope", encoding="utf-8")
    linked = source_root / "linked.txt"
    try:
        linked.symlink_to(external)
    except OSError as error:
        pytest.skip(f"symlink creation is unavailable: {error}")
    artifact_root = tmp_path / "artifacts"
    importer = GovernedFileImporter(
        artifacts=LocalArtifactStore(artifact_root),
        scopes={"user_selection": source_root},
        policy=FileImportPolicy.model_validate(
            {
                "schema_version": 1,
                "max_bytes": 1024,
                "chunk_bytes": 64,
                "allowed_extensions": (".txt",),
            }
        ),
    )

    with pytest.raises(ImportPathEscapeError):
        importer.import_selected(
            FileImportSelection.model_validate(
                {
                    "schema_version": 1,
                    "scope_id": "user_selection",
                    "target": "linked.txt",
                }
            )
        )

    assert [path for path in artifact_root.rglob("*") if path.is_file()] == []


def test_interrupted_stream_publishes_no_artifact(tmp_path: Path) -> None:
    from oscillink_agent.storage.artifacts import LocalArtifactStore

    class InterruptedStream(io.BytesIO):
        def read(self, size: int = -1) -> bytes:
            if self.tell() > 0:
                raise OSError("simulated disconnect")
            return super().read(min(size, 3))

    artifact_root = tmp_path / "artifacts"
    store = LocalArtifactStore(artifact_root)

    with pytest.raises(OSError, match="simulated disconnect"):
        store.put_stream(
            InterruptedStream(b"partial source"),
            max_bytes=1024,
            chunk_bytes=8,
            expected_bytes=len(b"partial source"),
        )

    assert [path for path in artifact_root.rglob("*") if path.is_file()] == []


def test_changed_source_length_publishes_no_artifact(tmp_path: Path) -> None:
    from oscillink_agent.storage.artifacts import (
        ArtifactLengthMismatchError,
        LocalArtifactStore,
    )

    artifact_root = tmp_path / "artifacts"
    store = LocalArtifactStore(artifact_root)

    with pytest.raises(ArtifactLengthMismatchError, match="changed"):
        store.put_stream(
            io.BytesIO(b"short"),
            max_bytes=1024,
            chunk_bytes=2,
            expected_bytes=6,
        )

    assert [path for path in artifact_root.rglob("*") if path.is_file()] == []


def test_failed_import_appends_sanitized_ledger_event(tmp_path: Path) -> None:
    from oscillink_agent.domain.imports import (
        FileImportAuditContext,
        FileImportPolicy,
        FileImportSelection,
    )
    from oscillink_agent.storage.artifacts import LocalArtifactStore
    from oscillink_agent.storage.imports import (
        GovernedFileImporter,
        ImportSourceUnavailableError,
    )
    from oscillink_agent.storage.sqlite import SQLiteEventStore

    source_root = tmp_path / "selected"
    source_root.mkdir()
    artifacts = LocalArtifactStore(tmp_path / "artifacts")
    events = SQLiteEventStore(tmp_path / "events.sqlite3", artifacts=artifacts)
    importer = GovernedFileImporter(
        artifacts=artifacts,
        scopes={"user_selection": source_root},
        policy=FileImportPolicy.model_validate(
            {
                "schema_version": 1,
                "max_bytes": 1024,
                "chunk_bytes": 64,
                "allowed_extensions": (".txt",),
            }
        ),
    )
    selection = FileImportSelection.model_validate(
        {
            "schema_version": 1,
            "scope_id": "user_selection",
            "target": "missing.txt",
        }
    )
    audit = FileImportAuditContext.model_validate_json(
        json.dumps(
            {
            "schema_version": 1,
            "event_id": "evt_01J00000000000000000000010",
            "session_id": "ses_01J00000000000000000000000",
            "run_id": "run_01J00000000000000000000000",
            "task_id": "tsk_01J00000000000000000000000",
            "actor": {"id": "human_maverick", "type": "human"},
            "observed_at": "2026-08-28T18:00:00Z",
            "recorded_at": "2026-08-28T18:00:01Z",
            "trust_class": "external_untrusted",
            "sensitivity": "private",
            }
        )
    )

    with pytest.raises(ImportSourceUnavailableError):
        importer.import_and_record(
            selection,
            audit=audit,
            events=events,
            idempotency_key="import_missing-file",
        )

    replayed = list(events.stream(audit.session_id))
    events.close()
    assert len(replayed) == 1
    assert replayed[0].artifact_refs == ()
    assert replayed[0].payload["operation"] == "artifact_import"
    assert replayed[0].payload["status"] == "failed"
    assert replayed[0].payload["error_code"] == "source_unavailable"
    assert replayed[0].payload["source_scope_id"] == "user_selection"
    assert replayed[0].payload["source_name"] == "missing.txt"
    assert str(source_root) not in replayed[0].model_dump_json()
