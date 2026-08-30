"""Persistence and restart-safe reconstruction for governed chat runs."""

from collections.abc import Iterable
from pathlib import Path

from pydantic import ValidationError

from oscillink_agent.agent_runtime.contracts import (
    RunReconstructionError,
    reconstruct_run,
)
from oscillink_agent.agent_runtime.errors import (
    ChatRunIncompleteError,
    ChatRunNotFoundError,
)
from oscillink_agent.chat.contracts import (
    ChatCitation,
    ChatMessageResponse,
    ChatProviderProjection,
    ChatRunInspectionResponse,
)
from oscillink_agent.domain.context import ContextManifest
from oscillink_agent.domain.events import Event, RunId, SessionId
from oscillink_agent.storage.artifacts import LocalArtifactStore
from oscillink_agent.storage.sqlite import SQLiteEventStore


class SQLiteChatRunRepository:
    """Persist and reconstruct governed run trajectories under one data root."""

    def __init__(self, data_root: Path) -> None:
        self._data_root = data_root
        self._artifacts = LocalArtifactStore(data_root / "artifacts")

    def get_by_idempotency(self, idempotency_key: str) -> Event | None:
        store = SQLiteEventStore(
            self._data_root / "events.sqlite3", artifacts=self._artifacts
        )
        try:
            return store.get_by_idempotency(idempotency_key)
        finally:
            store.close()

    def put_context_manifest(self, manifest: ContextManifest) -> str:
        return self._artifacts.put(manifest.model_dump_json().encode("utf-8"))

    def append_many(self, entries: Iterable[tuple[Event, str]]) -> tuple[str, ...]:
        store = SQLiteEventStore(
            self._data_root / "events.sqlite3", artifacts=self._artifacts
        )
        try:
            return store.append_many(entries)
        finally:
            store.close()

    def inspect(
        self,
        session_id: SessionId,
        run_id: RunId,
    ) -> ChatRunInspectionResponse:
        database = self._data_root / "events.sqlite3"
        if not database.is_file():
            raise ChatRunNotFoundError
        event_store = SQLiteEventStore(database)
        try:
            run_events = tuple(
                event for event in event_store.stream(session_id) if event.run_id == run_id
            )
        finally:
            event_store.close()
        if not run_events:
            raise ChatRunNotFoundError
        try:
            reconstruction = reconstruct_run(run_events)
        except RunReconstructionError as error:
            raise ChatRunIncompleteError from error
        if reconstruction.context_manifest_ref is None:
            raise ChatRunIncompleteError
        context_manifest = ContextManifest.model_validate_json(
            self._artifacts.get(reconstruction.context_manifest_ref)
        )
        if context_manifest.task_id != reconstruction.task_id:
            raise ChatRunIncompleteError
        return ChatRunInspectionResponse(
            session_id=session_id,
            run_id=run_id,
            events=run_events,
            context_manifest=context_manifest,
            reconstruction=reconstruction,
        )

    @staticmethod
    def response_from_run(run: ChatRunInspectionResponse) -> ChatMessageResponse:
        final_response_event_id = run.reconstruction.final_response_event_id
        if final_response_event_id is None:
            raise ChatRunIncompleteError
        response_event = next(
            event for event in run.events if event.id == final_response_event_id
        )
        citations_value = response_event.payload.get("citations")
        if not isinstance(citations_value, (list, tuple)):
            raise ChatRunIncompleteError
        citations = tuple(
            ChatCitation.model_validate(dict(value)) for value in citations_value
        )
        answer = response_event.payload.get("answer")
        if type(answer) is not str or response_event.model is None:
            raise ChatRunIncompleteError
        try:
            provider = ChatProviderProjection.model_validate(
                {
                    "kind": response_event.model.provider,
                    "model": response_event.model.name,
                }
            )
        except ValidationError as error:
            raise ChatRunIncompleteError from error
        return ChatMessageResponse(
            session_id=run.session_id,
            run_id=run.run_id,
            task_id=run.reconstruction.task_id,
            provider=provider,
            answer=answer,
            citations=citations,
            context_manifest=run.context_manifest,
        )
