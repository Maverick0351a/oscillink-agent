"""Authenticated read-only evaluation evidence routes."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import ValidationError

from oscillink_agent.evaluation.contracts import (
    EvaluationReport,
    EvaluationReportFreshness,
    EvaluationReportReason,
    EvaluationReportView,
)
from oscillink_agent.workspaces.contracts import LocalWorkspacePrincipal
from oscillink_agent.workspaces.service import LocalWorkspaceAuth

_MAX_REPORT_BYTES = 16 * 1024 * 1024


def _unavailable(reason: EvaluationReportReason) -> EvaluationReportView:
    return EvaluationReportView.model_validate(
        {
            "schema_version": 1,
            "state": "unavailable",
            "freshness": "unknown",
            "reason": reason,
            "report": None,
        }
    )


def _load_report(data_root: Path) -> EvaluationReport | None:
    report_path = data_root / "evaluations" / "latest.json"
    if not report_path.is_file():
        return None
    try:
        resolved = report_path.resolve(strict=True)
        if not resolved.is_relative_to(data_root.resolve()):
            return None
        if resolved.stat().st_size > _MAX_REPORT_BYTES:
            return None
        return EvaluationReport.model_validate_json(resolved.read_bytes())
    except (OSError, ValidationError):
        return None


def build_evaluation_router(
    data_root: Path,
    workspace_auth: LocalWorkspaceAuth,
    *,
    code_revision: str | None,
) -> APIRouter:
    """Serve a fixed precomputed report without executing an evaluation."""

    router = APIRouter()

    @router.get("/api/v1/evaluations/latest", response_model=EvaluationReportView)
    def latest_evaluation(
        _principal: Annotated[
            LocalWorkspacePrincipal,
            Depends(workspace_auth.require_principal),
        ],
    ) -> EvaluationReportView:
        report_path = data_root / "evaluations" / "latest.json"
        report = _load_report(data_root)
        if report is None:
            unavailable_reason: EvaluationReportReason = (
                "report_missing" if not report_path.exists() else "report_invalid"
            )
            return _unavailable(unavailable_reason)
        freshness: EvaluationReportFreshness
        reason: EvaluationReportReason | None
        if report.worktree_dirty:
            freshness = "stale"
            reason = "dirty_worktree"
        elif code_revision is None:
            freshness = "unknown"
            reason = None
        elif report.code_revision != code_revision:
            freshness = "stale"
            reason = "code_revision_mismatch"
        else:
            freshness = "current"
            reason = None
        return EvaluationReportView(
            state="available",
            freshness=freshness,
            reason=reason,
            report=report,
        )

    return router