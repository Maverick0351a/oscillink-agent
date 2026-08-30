CREATE TABLE IF NOT EXISTS events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    idempotency_key TEXT NOT NULL UNIQUE,
    session_id TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    event_json TEXT NOT NULL,
    event_sha256 TEXT NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS events_session_sequence
    ON events (session_id, sequence);

CREATE UNIQUE INDEX IF NOT EXISTS events_one_artifact_association_review
    ON events (
        CASE
            WHEN json_valid(event_json)
            THEN json_extract(event_json, '$.payload.proposal_id')
        END
    )
    WHERE json_valid(event_json)
      AND json_extract(event_json, '$.payload.operation') = 'artifact_association_review';

CREATE TRIGGER IF NOT EXISTS events_reject_update
BEFORE UPDATE ON events
BEGIN
    SELECT RAISE(ABORT, 'events are append-only');
END;

CREATE TRIGGER IF NOT EXISTS events_reject_delete
BEFORE DELETE ON events
BEGIN
    SELECT RAISE(ABORT, 'events are append-only');
END;

PRAGMA user_version = 1;
