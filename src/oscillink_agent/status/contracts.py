"""Transport contracts for local service readiness."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

ComponentState = Literal["not_initialized", "ready", "error"]
FeatureState = Literal["planned", "preview", "ready"]


class StorageComponentStatus(BaseModel):
    """Read-only status for one durable storage component."""

    model_config = ConfigDict(frozen=True)

    state: ComponentState
    record_count: int


class ServiceStatus(BaseModel):
    """Truthful readiness snapshot consumed by the local frontend."""

    model_config = ConfigDict(frozen=True)

    service: Literal["oscillink-agent"] = "oscillink-agent"
    version: str
    api_state: Literal["online"] = "online"
    storage: dict[str, StorageComponentStatus]
    features: dict[str, FeatureState]
