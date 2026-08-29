from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from oscillink_agent.capabilities import broker as broker_module
from oscillink_agent.domain.capabilities import (
    CapabilityConstraints,
    CapabilityGrant,
    FileResource,
)
from oscillink_agent.domain.events import (
    Actor,
    ActorType,
    Event,
    EventType,
    Sensitivity,
    TrustClass,
    canonical_payload_hash,
)
from oscillink_agent.storage.sqlite import SQLiteEventStore


def persist_authorization(data_root: Path, event: Event) -> None:
    store = SQLiteEventStore(data_root / "events.sqlite3")
    try:
        store.append(event, idempotency_key=f"authorize-{event.id}")
    finally:
        store.close()


def authorization_event(grant_id: str, issued_at: datetime) -> Event:
    payload = {"grant_id": grant_id, "decision": "approved"}
    return Event(
        id="evt_01J0000000000000000000000G",
        schema_version=1,
        session_id="ses_01J0000000000000000000000G",
        run_id="run_01J0000000000000000000000G",
        task_id="tsk_01J0000000000000000000000G",
        actor=Actor(id="human_maverick", type=ActorType.HUMAN),
        event_type=EventType.APPROVAL,
        observed_at=issued_at,
        recorded_at=issued_at,
        payload_hash=canonical_payload_hash(payload),
        artifact_refs=(),
        causal_parent_ids=(),
        trust_class=TrustClass.HUMAN_VERIFIED,
        sensitivity=Sensitivity.INTERNAL,
        payload=payload,
    )


def grant(
    issued_at: datetime,
    *,
    target: str = "docs/allowed.txt",
    grant_id: str = "grt_01J0000000000000000000000G",
) -> CapabilityGrant:
    return CapabilityGrant(
        id=grant_id,
        schema_version=1,
        subject_actor_id="model_qwen3_14b",
        capability="file.read",
        resource=FileResource(scope_id="workspace_a", target=target),
        issued_at=issued_at,
        valid_for_seconds=60,
        issued_by="human_maverick",
        authorization_event_id="evt_01J0000000000000000000000G",
        max_uses=1,
        constraints=CapabilityConstraints(
            max_bytes=128,
            allowed_extensions=(".txt",),
            network_allowed=False,
        ),
    )


def test_bounded_read_is_restart_safe_and_consumed_exactly_once(tmp_path: Path) -> None:
    broker_type = getattr(broker_module, "CapabilityBroker", None)
    assert broker_type is not None
    issued_at = datetime(2026, 8, 29, 9, 0, tzinfo=UTC)
    root = tmp_path / "workspace-a"
    target = root / "docs" / "allowed.txt"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"approved evidence\n")
    authority = grant(issued_at)
    broker = broker_type(
        data_root=tmp_path / "runtime",
        scope_roots={"workspace_a": root},
    )
    persist_authorization(
        tmp_path / "runtime", authorization_event(authority.id, issued_at)
    )
    broker.register_grant(authority)

    result = broker.execute_file_read(
        authority.id,
        subject_actor_id="model_qwen3_14b",
        now=issued_at + timedelta(seconds=1),
    )

    assert result.model_dump(mode="json") == {
        "schema_version": 1,
        "grant_id": authority.id,
        "scope_id": "workspace_a",
        "target": "docs/allowed.txt",
        "byte_count": 18,
        "content_hash": "sha256:707d635f4f9218777f7d48c16cf92eb6a4d4a877e9bf3c2b926d4d82306e51da",
        "content": "approved evidence\n",
        "trust_class": "external_untrusted",
        "network_used": False,
    }

    restarted = broker_type(
        data_root=tmp_path / "runtime",
        scope_roots={"workspace_a": root},
    )
    with pytest.raises(broker_module.CapabilityDeniedError) as reused:
        restarted.execute_file_read(
            authority.id,
            subject_actor_id="model_qwen3_14b",
            now=issued_at + timedelta(seconds=2),
        )
    assert reused.value.code == "grant_consumed"


def test_expired_and_actor_mismatched_grants_fail_closed(tmp_path: Path) -> None:
    issued_at = datetime(2026, 8, 29, 9, 0, tzinfo=UTC)
    root = tmp_path / "workspace-a"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "allowed.txt").write_text("bounded", encoding="utf-8")
    broker = broker_module.CapabilityBroker(
        data_root=tmp_path / "runtime",
        scope_roots={"workspace_a": root},
    )
    first = grant(issued_at)
    persist_authorization(
        tmp_path / "runtime", authorization_event(first.id, issued_at)
    )
    broker.register_grant(first)
    with pytest.raises(broker_module.CapabilityDeniedError) as actor_error:
        broker.execute_file_read(
            first.id,
            subject_actor_id="model_other",
            now=issued_at + timedelta(seconds=1),
        )
    assert actor_error.value.code == "subject_mismatch"

    second = grant(
        issued_at,
        grant_id="grt_01J0000000000000000000000H",
    )
    second_event = authorization_event(second.id, issued_at).model_copy(
        update={
            "id": "evt_01J0000000000000000000000H",
            "payload": {"grant_id": second.id, "decision": "approved"},
            "payload_hash": canonical_payload_hash(
                {"grant_id": second.id, "decision": "approved"}
            ),
        }
    )
    second = second.model_copy(update={"authorization_event_id": second_event.id})
    persist_authorization(tmp_path / "runtime", second_event)
    broker.register_grant(second)
    with pytest.raises(broker_module.CapabilityDeniedError) as expired:
        broker.execute_file_read(
            second.id,
            subject_actor_id="model_qwen3_14b",
            now=issued_at + timedelta(seconds=61),
        )
    assert expired.value.code == "grant_expired"


def test_read_cannot_escape_scope_or_widen_registered_grant(tmp_path: Path) -> None:
    issued_at = datetime(2026, 8, 29, 9, 0, tzinfo=UTC)
    root = tmp_path / "workspace-a"
    external = tmp_path / "external.txt"
    external.write_text("secret outside scope", encoding="utf-8")
    linked = root / "docs" / "allowed.txt"
    linked.parent.mkdir(parents=True)
    try:
        linked.symlink_to(external)
    except OSError as error:
        pytest.skip(f"symlink creation is unavailable: {error}")
    broker = broker_module.CapabilityBroker(
        data_root=tmp_path / "runtime",
        scope_roots={"workspace_a": root},
    )
    authority = grant(issued_at)
    persist_authorization(
        tmp_path / "runtime", authorization_event(authority.id, issued_at)
    )
    broker.register_grant(authority)

    with pytest.raises(broker_module.CapabilityDeniedError) as escaped:
        broker.execute_file_read(
            authority.id,
            subject_actor_id="model_qwen3_14b",
            now=issued_at + timedelta(seconds=1),
        )
    assert escaped.value.code == "scope_escape"

    widened = authority.model_copy(
        update={"resource": FileResource(scope_id="workspace_a", target="external.txt")}
    )
    with pytest.raises(broker_module.CapabilityDeniedError) as conflict:
        broker.register_grant(widened)
    assert conflict.value.code == "grant_conflict"


def test_extension_size_utf8_and_authorization_boundaries_are_enforced(
    tmp_path: Path,
) -> None:
    issued_at = datetime(2026, 8, 29, 9, 0, tzinfo=UTC)
    root = tmp_path / "workspace-a"
    (root / "docs").mkdir(parents=True)
    broker = broker_module.CapabilityBroker(
        data_root=tmp_path / "runtime",
        scope_roots={"workspace_a": root},
    )

    bad_event_grant = grant(issued_at)
    bad_event = authorization_event(bad_event_grant.id, issued_at).model_copy(
        update={
            "payload": {"grant_id": bad_event_grant.id, "decision": "denied"},
            "payload_hash": canonical_payload_hash(
                {"grant_id": bad_event_grant.id, "decision": "denied"}
            ),
        }
    )
    persist_authorization(tmp_path / "runtime", bad_event)
    with pytest.raises(broker_module.CapabilityDeniedError) as unauthorized:
        broker.register_grant(bad_event_grant)
    assert unauthorized.value.code == "authorization_invalid"

    cases = (
        ("docs/blocked.md", b"blocked", "extension_denied"),
        ("docs/large.txt", b"x" * 129, "size_exceeded"),
        ("docs/binary.txt", b"\xff\xfe", "encoding_denied"),
    )
    for index, (target_name, content, code) in enumerate(cases):
        (root / target_name).write_bytes(content)
        suffix = "JKM"[index]
        current = grant(
            issued_at,
            target=target_name,
            grant_id=f"grt_01J0000000000000000000000{suffix}",
        )
        event = authorization_event(current.id, issued_at).model_copy(
            update={
                "id": f"evt_01J0000000000000000000000{suffix}",
                "payload": {"grant_id": current.id, "decision": "approved"},
                "payload_hash": canonical_payload_hash(
                    {"grant_id": current.id, "decision": "approved"}
                ),
            }
        )
        current = current.model_copy(update={"authorization_event_id": event.id})
        persist_authorization(tmp_path / "runtime", event)
        broker.register_grant(current)
        with pytest.raises(broker_module.CapabilityDeniedError) as denied:
            broker.execute_file_read(
                current.id,
                subject_actor_id="model_qwen3_14b",
                now=issued_at + timedelta(seconds=1),
            )
        assert denied.value.code == code
