"""Backend-neutral durable storage protocols."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import BinaryIO, Protocol, runtime_checkable

from oscillink_agent.domain.events import Event, SessionId


class ArtifactStoreError(Exception):
    """An artifact could not be resolved and verified by its backend."""


@dataclass(frozen=True, slots=True)
class ArtifactPublication:
    """Storage accounting returned by one atomic artifact publication."""

    reference: str
    byte_count: int
    deduplicated: bool


@runtime_checkable
class ArtifactStore(Protocol):
    """Store and verify immutable content-addressed bytes."""

    def put(self, content: bytes) -> str: ...

    def put_stream(
        self,
        stream: BinaryIO,
        *,
        max_bytes: int,
        chunk_bytes: int,
        expected_bytes: int | None = None,
    ) -> ArtifactPublication: ...

    def get(self, reference: str) -> bytes: ...

    def verify(self, reference: str) -> None: ...


@runtime_checkable
class EventStore(Protocol):
    """Append and replay immutable execution events."""

    def append(self, event: Event, *, idempotency_key: str) -> str: ...

    def append_many(self, entries: Iterable[tuple[Event, str]]) -> tuple[str, ...]: ...

    def stream(self, session_id: SessionId) -> Iterator[Event]: ...

    def get_by_idempotency(self, idempotency_key: str) -> Event | None: ...

    def close(self) -> None: ...
