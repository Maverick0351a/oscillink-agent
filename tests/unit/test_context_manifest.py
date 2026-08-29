import json

from oscillink_agent.domain.context import ContextManifest


def test_v1_context_item_without_display_metadata_remains_readable() -> None:
    item = {
        "record_id": "mem_A37PTXSESJE0P4NFJTD7E7RRAH",
        "content_hash": "sha256:" + "b" * 64,
        "inclusion_reason": "approved historical evidence",
        "trust_class": "human_verified",
        "status": "approved",
        "token_count": 8,
        "source_refs": ["mem_A37PTXSESJE0P4NFJTD7E7RRAH"],
        "retrieval_rank": 1,
        "retrieval_score": 4,
    }
    manifest = ContextManifest.model_validate_json(
        json.dumps(
            {
                "id": "ctx_01ARZ3NDEKTSV4RRFFQ69G5FC1",
                "schema_version": 1,
                "task_id": "tsk_01ARZ3NDEKTSV4RRFFQ69G5FC1",
                "compiled_at": "2026-08-29T00:00:01Z",
                "token_budget": 2048,
                "total_token_count": 8,
                "policy_hash": "sha256:" + "c" * 64,
                "items": [item],
            }
        )
    )

    projection = manifest.model_dump(mode="json")["items"][0]
    assert projection["title"] is None
    assert projection["category"] is None
    assert projection["domains"] == []
