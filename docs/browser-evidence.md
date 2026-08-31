# Browser evidence and recovery operations

The authenticated **Evidence** workspace exposes two bounded surfaces:

1. read-only evaluation evidence from one precomputed server-managed report; and
2. human-controlled workspace export and restore operations.

The browser does not run evaluation, reveal hidden labels, initiate training, promote memory,
or accept arbitrary report/export paths.

## Publish the latest evaluation report

Generate the report before launching the private pilot:

```bash
PYTHONPATH= .venv/Scripts/python.exe scripts/run_public_evaluation.py \
  --output /path/to/data-root/evaluations/latest.json \
  --overwrite
```

Set `OSCILLINK_AGENT_CODE_REVISION` to the deployed Git revision when launching the app. The
read-only `GET /api/v1/evaluations/latest` route reads only
`<data-root>/evaluations/latest.json`, rejects oversized, malformed, and out-of-root reports,
and never executes evaluation.

The response distinguishes:

- `unavailable`: no valid server-managed report exists;
- `unknown`: a valid report exists but no deployed revision was configured;
- `stale`: the report came from a dirty worktree or a different configured revision; and
- `current`: the report revision matches and the evaluation worktree was clean.

The browser displays the exact condition, provider/model/configuration identity, code and
fixture revisions, equal context/output/time budget, per-condition metrics and failures, and
exact JSON. It does not invent an aggregate truth, confidence, autonomy, hallucination, AGI,
or consciousness score.

## Verified export and restore

The Evidence workspace also uses the authenticated workspace routes:

- `GET /api/v1/workspace/exports/latest` revalidates the newest server-managed bundle;
- `POST /api/v1/workspace/exports` creates a content-hashed canonical export; and
- `POST /api/v1/workspace/restores` verifies and atomically restores one exact export ID.

Latest-export inspection rechecks portable paths, file hashes, SQLite integrity/schema
versions, and artifact content addressing. Out-of-root or invalid bundles are unavailable.
The browser shows the exact manifest and entry hashes.

Restore remains a human action. The button stays disabled until the user types
`RESTORE <exact-export-id>`. The browser cannot select an arbitrary host path, and model or
retrieved text cannot authorize restore.

## Verified states

Automated tests cover locked, loading, unavailable, stale/current, success, failure, exact
manifest, and exact restore-confirmation states. Live browser-harness acceptance against the
real built frontend and FastAPI server additionally verified:

- the Evidence view is independently navigable;
- stale dirty-worktree evidence is visibly labeled;
- the view owns bounded scrolling at desktop height;
- a verified export renders its exact ID and manifest;
- mismatched/empty confirmation keeps restore disabled; and
- exact confirmation completes restore and displays `RESTORE COMPLETED`.
