import json

import pytest
from pydantic import TypeAdapter, ValidationError

from oscillink_agent.integrations.mcp.contracts import (
    CandidateResponse,
    CorrectionResponse,
    CorrectRequest,
    ExplainRequest,
    ExplainResponse,
    FailureResponse,
    ProjectMemoryProblem,
    ProjectMemoryTool,
    RecallRequest,
    RecallResponse,
    RememberRequest,
    UnavailableResponse,
)
from oscillink_agent.memory.obsidian import MemoryCategory, MemoryDomain


def test_project_memory_mcp_exposes_only_four_initial_tools() -> None:
    assert tuple(ProjectMemoryTool) == (
        ProjectMemoryTool.REMEMBER,
        ProjectMemoryTool.RECALL,
        ProjectMemoryTool.CORRECT,
        ProjectMemoryTool.EXPLAIN,
    )
    assert tuple(tool.value for tool in ProjectMemoryTool) == (
        "remember",
        "recall",
        "correct",
        "explain",
    )


def test_recall_request_requires_a_bounded_query_and_explicit_budget() -> None:
    request = RecallRequest.model_validate(
        {
            "schema_version": 1,
            "request_id": "evt_01J00000000000000000000000",
            "query": "Which deployment approach did the project approve?",
            "token_budget": 2048,
        },
        strict=True,
    )

    assert request.token_budget == 2048
    for invalid in (
        {**request.model_dump(), "query": ""},
        {**request.model_dump(), "query": "x" * 16_385},
        {**request.model_dump(), "token_budget": True},
        {**request.model_dump(), "token_budget": 32_769},
        {**request.model_dump(), "workspace_id": "ws_untrusted"},
    ):
        with pytest.raises(ValidationError):
            RecallRequest.model_validate(invalid, strict=True)


def test_remember_request_is_provenance_bearing_and_cannot_self_approve() -> None:
    request = RememberRequest.model_validate(
        {
            "schema_version": 1,
            "request_id": "evt_01J00000000000000000000000",
            "title": "Approved deployment approach",
            "content": "Deploy only after immutable local verification.",
            "category": MemoryCategory.GOVERNANCE,
            "domains": (MemoryDomain.SOFTWARE,),
            "topics": ("deployment", "verification"),
            "source_refs": ("evt_01J00000000000000000000001",),
        },
        strict=True,
    )

    assert request.source_refs == ("evt_01J00000000000000000000001",)
    for invalid in (
        {**request.model_dump(), "source_refs": ()},
        {**request.model_dump(), "source_refs": request.source_refs * 2},
        {**request.model_dump(), "approval_state": "approved"},
        {**request.model_dump(), "content": "x" * 65_537},
    ):
        with pytest.raises(ValidationError):
            RememberRequest.model_validate(invalid, strict=True)


def test_correct_request_binds_target_revision_and_preserves_lineage() -> None:
    target_id = "mem_01J00000000000000000000000"
    request = CorrectRequest.model_validate(
        {
            "schema_version": 1,
            "request_id": "evt_01J00000000000000000000002",
            "target_record_id": target_id,
            "expected_content_hash": "sha256:" + "a" * 64,
            "reason": "The deployment gate omitted immutable-range verification.",
            "title": "Corrected deployment approach",
            "content": "Verify the immutable local range before deployment.",
            "category": MemoryCategory.GOVERNANCE,
            "domains": (MemoryDomain.SOFTWARE,),
            "topics": ("deployment", "verification"),
            "source_refs": (target_id, "evt_01J00000000000000000000001"),
        },
        strict=True,
    )

    assert request.target_record_id in request.source_refs
    for invalid in (
        {**request.model_dump(), "expected_content_hash": "sha256:" + "0" * 63},
        {**request.model_dump(), "reason": ""},
        {
            **request.model_dump(),
            "source_refs": ("evt_01J00000000000000000000001",),
        },
        {**request.model_dump(), "decision": "superseded"},
    ):
        with pytest.raises(ValidationError):
            CorrectRequest.model_validate(invalid, strict=True)


def test_explain_request_is_bound_to_one_exact_revision() -> None:
    request = ExplainRequest.model_validate(
        {
            "schema_version": 1,
            "request_id": "evt_01J00000000000000000000003",
            "record_id": "mem_01J00000000000000000000000",
            "content_hash": "sha256:" + "a" * 64,
        },
        strict=True,
    )

    assert request.record_id == "mem_01J00000000000000000000000"
    for invalid in (
        {key: value for key, value in request.model_dump().items() if key != "content_hash"},
        {**request.model_dump(), "record_id": "../memory"},
        {**request.model_dump(), "include_history": False},
    ):
        with pytest.raises(ValidationError):
            ExplainRequest.model_validate(invalid, strict=True)


def test_problem_responses_are_typed_and_cannot_leak_raw_exceptions() -> None:
    adapter = TypeAdapter(ProjectMemoryProblem)
    unavailable = adapter.validate_json(
        json.dumps(
            {
            "schema_version": 1,
            "state": "unavailable",
            "operation": "recall",
            "reason": "empty_workspace",
            "retryable": False,
            }
        )
    )
    failure = adapter.validate_json(
        json.dumps(
            {
            "schema_version": 1,
            "state": "failure",
            "operation": "correct",
            "code": "revision_conflict",
            "retryable": False,
            }
        )
    )

    assert isinstance(unavailable, UnavailableResponse)
    assert isinstance(failure, FailureResponse)
    with pytest.raises(ValidationError):
        adapter.validate_json(
            json.dumps(
                {
                    **failure.model_dump(mode="json"),
                    "raw_exception": "sqlite3.OperationalError: C:/private/path",
                }
            )
        )


def test_recall_response_binds_untrusted_content_to_the_exact_manifest_revision() -> None:
    record_id = "mem_01J00000000000000000000000"
    content_hash = "sha256:" + "a" * 64
    payload = {
        "schema_version": 1,
        "state": "available",
        "operation": "recall",
        "request_id": "evt_01J00000000000000000000004",
        "context_manifest": {
            "id": "ctx_01J00000000000000000000000",
            "schema_version": 1,
            "task_id": "tsk_01J00000000000000000000000",
            "compiled_at": "2026-08-30T15:00:00Z",
            "token_budget": 8,
            "total_token_count": 4,
            "policy_hash": "sha256:" + "b" * 64,
            "items": [
                {
                    "record_id": record_id,
                    "content_hash": content_hash,
                    "title": "Deployment gate",
                    "category": "governance",
                    "domains": ["software"],
                    "inclusion_reason": "approved lexical evidence rank=1 score=2",
                    "trust_class": "human_verified",
                    "status": "approved",
                    "token_count": 4,
                    "source_refs": [record_id],
                    "retrieval_rank": 1,
                    "retrieval_score": 2,
                }
            ],
            "omissions": [],
            "exclusion_summary": {},
        },
        "records": [
            {
                "record_id": record_id,
                "content_hash": content_hash,
                "title": "Deployment gate",
                "content": "Deploy only after verification.",
                "source_refs": [record_id],
                "content_treatment": "untrusted_data",
            }
        ],
    }

    response = RecallResponse.model_validate_json(json.dumps(payload))

    assert response.records[0].content_treatment == "untrusted_data"
    payload["records"][0]["content_hash"] = "sha256:" + "c" * 64  # type: ignore[index]
    with pytest.raises(ValidationError, match="match the context manifest"):
        RecallResponse.model_validate_json(json.dumps(payload))


def test_write_successes_remain_candidates_and_explain_preserves_lineage() -> None:
    target_id = "mem_01J00000000000000000000000"
    replacement_id = "mem_01J00000000000000000000001"
    target_hash = "sha256:" + "a" * 64
    replacement_hash = "sha256:" + "b" * 64
    candidate = CandidateResponse.model_validate_json(
        json.dumps(
            {
                "schema_version": 1,
                "state": "candidate",
                "operation": "remember",
                "request_id": "evt_01J00000000000000000000005",
                "record_id": target_id,
                "content_hash": target_hash,
                "approval_required": True,
            }
        )
    )
    correction = CorrectionResponse.model_validate_json(
        json.dumps(
            {
                "schema_version": 1,
                "state": "candidate",
                "operation": "correct",
                "request_id": "evt_01J00000000000000000000006",
                "target_record_id": target_id,
                "expected_content_hash": target_hash,
                "replacement_record_id": replacement_id,
                "replacement_content_hash": replacement_hash,
                "approval_required": True,
            }
        )
    )
    explanation = ExplainResponse.model_validate_json(
        json.dumps(
            {
                "schema_version": 1,
                "state": "available",
                "operation": "explain",
                "request_id": "evt_01J00000000000000000000007",
                "record_id": target_id,
                "content_hash": target_hash,
                "authority_state": "superseded",
                "reasons": ["superseded"],
                "lineage": [
                    {
                        "record_id": target_id,
                        "content_hash": target_hash,
                        "authority_state": "superseded",
                        "relationship": "requested",
                    },
                    {
                        "record_id": replacement_id,
                        "content_hash": replacement_hash,
                        "authority_state": "approved",
                        "relationship": "superseded_by",
                    },
                ],
            }
        )
    )

    assert candidate.approval_required is True
    assert correction.approval_required is True
    assert explanation.lineage[0].record_id == explanation.record_id
    with pytest.raises(ValidationError):
        CandidateResponse.model_validate_json(
            json.dumps({**candidate.model_dump(mode="json"), "approval_required": False})
        )
    with pytest.raises(ValidationError, match="requested revision"):
        ExplainResponse.model_validate_json(
            json.dumps(
                {
                    **explanation.model_dump(mode="json"),
                    "lineage": explanation.model_dump(mode="json")["lineage"][1:],
                }
            )
        )
