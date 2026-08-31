"""Public acceptance contract for the five-minute Project Memory demo."""

import json
from hashlib import sha256
from pathlib import Path

import anyio
import pytest
from scripts.run_project_memory_demo import DemoFixtureError, run_demo

DEMO_FIXTURE = (
    Path(__file__).parents[2]
    / "examples"
    / "project-memory-demo"
    / "project-fixture"
    / "scenario.json"
)
DEMO_MANIFEST = DEMO_FIXTURE.parents[1] / "manifest.json"


def test_public_demo_fixture_is_pinned_input_without_agent_readable_labels(
    tmp_path: Path,
) -> None:
    fixture_bytes = DEMO_FIXTURE.read_bytes()
    fixture = json.loads(fixture_bytes)
    manifest = json.loads(DEMO_MANIFEST.read_text(encoding="utf-8"))

    assert fixture["schema_version"] == 1
    assert len(fixture["memories"]) == 4
    assert "expected" not in fixture
    assert "answer" not in fixture
    assert "labels" not in fixture
    assert manifest["fixture_sha256"] == sha256(fixture_bytes).hexdigest()
    assert manifest["claims"]["two_independent_client_processes"] is True
    assert manifest["claims"]["two_branded_agent_integrations"] is False

    report = anyio.run(run_demo, tmp_path / "workspace", DEMO_FIXTURE)

    assert report["fixture_hash"] == "sha256:" + sha256(fixture_bytes).hexdigest()


def test_unknown_correction_target_fails_before_workspace_creation(tmp_path: Path) -> None:
    fixture = json.loads(DEMO_FIXTURE.read_text(encoding="utf-8"))
    fixture["correction"]["target_key"] = "missing-memory"
    fixture_path = tmp_path / "invalid.json"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")
    data_root = tmp_path / "workspace"

    with pytest.raises(DemoFixtureError, match="correction target"):
        anyio.run(run_demo, data_root, fixture_path)

    assert not data_root.exists()


def test_two_fresh_clients_continue_from_corrected_memory_without_transcript(
    tmp_path: Path,
) -> None:
    first = anyio.run(run_demo, tmp_path / "first")
    second = anyio.run(run_demo, tmp_path / "second")

    assert first["schema_version"] == 1
    assert first["transport"] == "stdio"
    assert first["protocol_client"] == "official-python-mcp-sdk"
    assert first["account_required"] is False
    assert first["transcript_replayed"] is False
    agent_a, agent_b = first["client_sessions"]
    governance = first["governance_session"]
    assert agent_a["name"] == "agent-a"
    assert agent_b["name"] == "agent-b"
    assert governance["purpose"] == "propose-correction-after-compaction"
    assert agent_a["fresh_server_process"] is True
    assert agent_b["fresh_server_process"] is True
    assert governance["fresh_server_process"] is True
    assert agent_a["client_process_id"] != agent_b["client_process_id"]
    assert governance["client_process_id"] not in {
        agent_a["client_process_id"],
        agent_b["client_process_id"],
    }
    assert first["learned_record_count"] == 4
    assert first["agent_b"]["current_titles"] == [
        "Build verification",
        "Failed migration approach",
        "Project memory authority",
        "Release channel",
    ]
    assert first["agent_b"]["current_contents"] == [
        "Run immutable Windows, Buildbox Linux, and hosted CI gates before release.",
        "Do not retry transcript-only continuity; it lost corrections after compaction.",
        "Only externally approved memory is eligible for agent context.",
        "Publish alpha builds to the preview channel before stable promotion.",
    ]
    assert "Run CI before release." not in first["agent_b"]["current_contents"]
    assert first["agent_b"]["context_manifest"] == second["agent_b"][
        "context_manifest"
    ]
    assert first["agent_b"]["lineage"] == {
        "old_authority_state": "superseded",
        "old_content": "Run CI before release.",
        "replacement_content": (
            "Run immutable Windows, Buildbox Linux, and hosted CI gates before release."
        ),
        "relationship": "supersedes",
    }
    assert first["elapsed_seconds"] < 300
