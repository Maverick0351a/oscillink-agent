"""Side-effect-free deployment health projection."""

import sqlite3
from pathlib import Path
from typing import Literal

from oscillink_agent.health.contracts import (
    ApiHealth,
    CapabilityBrokerHealth,
    ProviderHealth,
    ReadinessResponse,
    WorkspaceStoresHealth,
)
from oscillink_agent.providers.base import ChatProvider, ProviderRequestError
from oscillink_agent.status.service import inspect_artifacts, inspect_ledger, inspect_memory


def inspect_provider(provider: ChatProvider) -> ProviderHealth:
    """Project known provider readiness without generating a chat completion."""

    state: Literal["ready", "unavailable"]
    identity = provider.execution_identity
    probe = getattr(provider, "probe_readiness", None)
    if identity.kind == "fake":
        state = "ready"
    elif not callable(probe):
        state = "unavailable"
    else:
        try:
            probe()
        except ProviderRequestError:
            state = "unavailable"
        else:
            state = "ready"
    return ProviderHealth(
        state=state,
        kind=identity.kind,
        model=identity.model,
    )


def inspect_capability_broker(
    database: Path,
    *,
    configured_scope_count: int,
) -> CapabilityBrokerHealth:
    state: Literal["ready", "error"]
    if not database.is_file():
        return CapabilityBrokerHealth(
            state="ready",
            configured_scope_count=configured_scope_count,
        )
    try:
        connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
        try:
            version = connection.execute("PRAGMA user_version").fetchone()
            table = connection.execute(
                "SELECT name FROM sqlite_schema "
                "WHERE type = 'table' AND name = 'capability_grants'"
            ).fetchone()
        finally:
            connection.close()
    except sqlite3.Error:
        state = "error"
    else:
        state = "ready" if version == (1,) and table is not None else "error"
    return CapabilityBrokerHealth(
        state=state,
        configured_scope_count=configured_scope_count,
    )


def inspect_readiness(
    data_root: Path,
    *,
    provider: ChatProvider,
    configured_scope_count: int,
) -> ReadinessResponse:
    stores = WorkspaceStoresHealth(
        ledger=inspect_ledger(data_root / "events.sqlite3"),
        artifacts=inspect_artifacts(data_root / "artifacts"),
        memory=inspect_memory(data_root / "memory.sqlite3"),
    )
    provider_health = inspect_provider(provider)
    broker_health = inspect_capability_broker(
        data_root / "capabilities.sqlite3",
        configured_scope_count=configured_scope_count,
    )
    has_store_error = any(
        component.state == "error"
        for component in (stores.ledger, stores.artifacts, stores.memory)
    )
    return ReadinessResponse(
        state=(
            "degraded"
            if (
                has_store_error
                or provider_health.state == "unavailable"
                or broker_health.state == "error"
            )
            else "ready"
        ),
        api=ApiHealth(),
        stores=stores,
        provider=provider_health,
        capability_broker=broker_health,
    )
