"""Typed liveness and deployment-readiness projections."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from oscillink_agent.providers.base import ProviderKind
from oscillink_agent.status.contracts import StorageComponentStatus


class ApiHealth(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    state: Literal["ready"] = "ready"


class ProviderHealth(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    state: Literal["ready", "unavailable"]
    kind: ProviderKind
    model: str


class CapabilityBrokerHealth(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    state: Literal["ready", "error"]
    configured_scope_count: int = Field(ge=0)


class WorkspaceStoresHealth(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    ledger: StorageComponentStatus
    artifacts: StorageComponentStatus
    memory: StorageComponentStatus


class LivenessResponse(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: Literal[1] = 1
    service: Literal["oscillink-agent"] = "oscillink-agent"
    state: Literal["alive"] = "alive"


class ReadinessResponse(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: Literal[1] = 1
    service: Literal["oscillink-agent"] = "oscillink-agent"
    state: Literal["ready", "degraded"]
    api: ApiHealth
    stores: WorkspaceStoresHealth
    provider: ProviderHealth
    capability_broker: CapabilityBrokerHealth
