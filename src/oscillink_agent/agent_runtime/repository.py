"""Persistence and restart-safe reconstruction for governed chat runs."""

from collections.abc import Iterable
from pathlib import Path

from pydantic import ValidationError

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
from oscillink_agent.domain.events import ActorType, Event, EventType, RunId, SessionId
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
        model_call = next(
            (event for event in run_events if event.event_type is EventType.MODEL_CALL),
            None,
        )
        if model_call is None or len(model_call.artifact_refs) != 1:
            raise ChatRunIncompleteError
        context_manifest = ContextManifest.model_validate_json(
            self._artifacts.get(model_call.artifact_refs[0])
        )
        return ChatRunInspectionResponse(
            session_id=session_id,
            run_id=run_id,
            events=run_events,
            context_manifest=context_manifest,
        )

    @staticmethod
    def response_from_run(run: ChatRunInspectionResponse) -> ChatMessageResponse:
        model_call = next(
            event for event in run.events if event.event_type is EventType.MODEL_CALL
        )
        response_event = next(
            event
            for event in run.events
            if event.event_type is EventType.MESSAGE
            and event.actor.type is ActorType.MODEL
        )
        citations_value = response_event.payload.get("citations")
        if not isinstance(citations_value, (list, tuple)):
            raise ChatRunIncompleteError
        citations = tuple(
            ChatCitation.model_validate(dict(value)) for value in citations_value
        )
        answer = response_event.payload.get("answer")
        provider_kind = model_call.payload.get("provider_kind")
        provider_model = model_call.payload.get("provider_model")
        if type(answer) is not str:
            raise ChatRunIncompleteError
        try:
            provider = ChatProviderProjection.model_validate(
                {"kind": provider_kind, "model": provider_model}
            )
        except ValidationError as error:
            raise ChatRunIncompleteError from error
        return ChatMessageResponse(
            session_id=run.session_id,
            run_id=run.run_id,
            task_id=model_call.task_id,
            provider=provider,
            answer=answer,
            citations=citations,
            context_manifest=run.context_manifest,
        )
