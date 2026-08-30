"""Minimal liveness and truthful private-deployment readiness routes."""

from pathlib import Path

from fastapi import APIRouter

from oscillink_agent.health.contracts import LivenessResponse, ReadinessResponse
from oscillink_agent.health.service import inspect_readiness
from oscillink_agent.providers.base import ChatProvider


def build_health_router(
    data_root: Path,
    *,
    provider: ChatProvider,
    configured_scope_count: int,
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/v1/health/live", response_model=LivenessResponse)
    def liveness() -> LivenessResponse:
        return LivenessResponse()

    @router.get("/api/v1/health/ready", response_model=ReadinessResponse)
    def readiness() -> ReadinessResponse:
        return inspect_readiness(
            data_root,
            provider=provider,
            configured_scope_count=configured_scope_count,
        )

    return router
