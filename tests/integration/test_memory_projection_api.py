from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
from fastapi import FastAPI

from oscillink_agent.api import create_app


def write_note(vault: Path, relative_path: str, content: str) -> None:
    path = vault / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def request(app: FastAPI, path: str) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get(path)

    return asyncio.run(send())


def build_test_vault(vault: Path) -> None:
    write_note(
        vault,
        "20 Projects/Oscillink.md",
        """---
type: project
status: active
area: AI Research
topics: [world models, electromagnetic systems]
---
# Oscillink

See [[30 Notes/Research/Field Trial]].
""",
    )
    write_note(
        vault,
        "30 Notes/Research/Field Trial.md",
        """---
type: research-note
status: active
category: experiment
domains: [science, mathematics, rf_em]
topics: [field inference, calibration]
---
# Field Trial
""",
    )


def test_index_summary_exposes_typed_legends_without_absolute_paths(tmp_path: Path) -> None:
    vault = tmp_path / "private-vault"
    build_test_vault(vault)
    app = create_app(data_root=tmp_path / "runtime", vault_root=vault)

    response = request(app, "/api/v1/memory/index")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == 1
    assert payload["state"] == "ready"
    assert payload["reason"] is None
    assert payload["index_hash"].startswith("sha256:")
    assert payload["node_count"] == 2
    assert payload["issue_count"] == 0
    assert payload["issues"] == []
    assert {entry["category"]: entry for entry in payload["categories"]}["project"] == {
        "category": "project",
        "label": "Projects",
        "color": "#ff4fd8",
        "symbol": "P",
    }
    assert {entry["domain"]: entry["label"] for entry in payload["domains"]}[
        "mathematics"
    ] == "Mathematics"
    assert str(vault) not in response.text


def test_node_collection_filters_by_category_and_domain(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    build_test_vault(vault)
    app = create_app(data_root=tmp_path / "runtime", vault_root=vault)

    response = request(
        app,
        "/api/v1/memory/nodes?category=experiment&domain=mathematics",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "ready"
    assert payload["count"] == 1
    assert payload["applied_filters"] == {
        "category": "experiment",
        "domain": "mathematics",
    }
    assert payload["nodes"] == [
        {
            "id": payload["nodes"][0]["id"],
            "title": "Field Trial",
            "source_path": "30 Notes/Research/Field Trial.md",
            "source_status": "active",
            "authority_state": "curated",
            "source_kind": "obsidian",
            "category": "experiment",
            "domains": ["rf_em", "science", "mathematics"],
            "topics": ["field inference", "calibration"],
            "content_hash": payload["nodes"][0]["content_hash"],
            "wikilink_count": 0,
            "architecture_node_ids": [],
        }
    ]
    assert payload["nodes"][0]["id"].startswith("doc_")
    assert payload["nodes"][0]["content_hash"].startswith("sha256:")
    assert str(vault) not in response.text


def test_focused_node_lookup_exposes_inspector_metadata_and_typed_not_found(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    build_test_vault(vault)
    app = create_app(data_root=tmp_path / "runtime", vault_root=vault)
    collection = request(app, "/api/v1/memory/nodes?category=project").json()
    node_id = collection["nodes"][0]["id"]

    response = request(app, f"/api/v1/memory/nodes/{node_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "ready"
    assert payload["node"]["title"] == "Oscillink"
    assert payload["node"]["frontmatter_type"] == "project"
    assert payload["node"]["wikilinks"] == ["30 Notes/Research/Field Trial"]
    assert payload["node"]["classification_basis"][0] == "frontmatter:type=project"
    assert str(vault) not in response.text

    missing = request(app, "/api/v1/memory/nodes/doc_00000000000000000000000000")
    assert missing.status_code == 404
    assert missing.json() == {
        "detail": {
            "code": "node_not_found",
            "message": "Memory node was not found.",
        }
    }


def test_memory_projection_is_honestly_unavailable_without_configured_vault(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "runtime"
    app = create_app(data_root=data_root, vault_root=None)

    summary = request(app, "/api/v1/memory/index")
    collection = request(app, "/api/v1/memory/nodes")
    detail = request(app, "/api/v1/memory/nodes/doc_00000000000000000000000000")

    assert summary.status_code == 200
    assert summary.json()["state"] == "unavailable"
    assert summary.json()["reason"] == "vault_not_configured"
    assert summary.json()["node_count"] == 0
    assert collection.status_code == 200
    assert collection.json()["state"] == "unavailable"
    assert collection.json()["nodes"] == []
    assert detail.status_code == 503
    assert detail.json() == {
        "detail": {
            "code": "memory_unavailable",
            "message": "Reviewed memory is not configured.",
        }
    }
    assert not data_root.exists()


def test_index_reports_degraded_state_for_invalid_source(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    build_test_vault(vault)
    write_note(
        vault,
        "30 Notes/Invalid.md",
        """---
type: unknown-type
---
# Invalid
""",
    )
    app = create_app(data_root=tmp_path / "runtime", vault_root=vault)

    response = request(app, "/api/v1/memory/index")

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "degraded"
    assert payload["node_count"] == 2
    assert payload["issue_count"] == 1
    assert payload["issues"] == [
        {
            "source_path": "30 Notes/Invalid.md",
            "code": "unsupported_type",
            "message": "unsupported frontmatter type: unknown-type",
        }
    ]
    assert str(vault) not in response.text


def test_rejects_malformed_node_ids_and_unknown_filter_labels(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    build_test_vault(vault)
    app = create_app(data_root=tmp_path / "runtime", vault_root=vault)

    malformed_id = request(app, "/api/v1/memory/nodes/not-a-document-id")
    unknown_category = request(app, "/api/v1/memory/nodes?category=unknown")
    unknown_domain = request(app, "/api/v1/memory/nodes?domain=unknown")

    assert malformed_id.status_code == 422
    assert unknown_category.status_code == 422
    assert unknown_domain.status_code == 422
