# Private-pilot deployment runbook

This runbook starts one bounded Oscillink Agent process that serves the built browser application and API from the same explicit address. It is intended for a single-user private pilot, not an internet-facing or multi-tenant deployment.

## Security boundary

- The launcher binds to `127.0.0.1` unless a non-loopback IP and `--allow-network-bind` are both supplied.
- It generates a new workspace credential for every launch and writes it to a separate credential file. The credential is never placed in command-line arguments or application logs.
- The credential file must remain outside the canonical workspace data directory, so it cannot enter workspace exports.
- The browser keeps the pasted credential only in memory. Refreshing the page locks governed operations again.
- Non-loopback HTTP is unencrypted. Use only a trusted private network and host firewall. Do not expose this launcher directly to the public internet.
- Capability grants, memory approval, restore, and provider authority remain governed by their existing typed contracts. Deployment convenience does not widen them.

## Prerequisites

From the repository root in Git Bash on Windows:

```bash
uv sync --locked --dev
npm --prefix apps/web ci
npm --prefix apps/web run build
```

The launcher uses Python 3.11 from the project virtual environment and requires `apps/web/dist/index.html`.

## Start a loopback pilot

Choose separate canonical-data and credential locations:

```bash
DATA_DIR="$HOME/AppData/Local/oscillink-agent-private/workspace"
CREDENTIAL_FILE="$HOME/AppData/Local/oscillink-agent-private-runtime/workspace.credential"

PYTHONPATH= .venv/Scripts/python.exe scripts/launch_private_pilot.py \
  --host 127.0.0.1 \
  --port 8765 \
  --data-dir "$DATA_DIR" \
  --credential-file "$CREDENTIAL_FILE" \
  --frontend-dist apps/web/dist
```

The launcher prints only the browser URL and credential-file path. Open `http://127.0.0.1:8765`, read the credential directly from the named file, paste it into **Local workspace credential**, and select **Unlock workspace**.

Git Bash normally converts `/c/...` arguments for the Windows Python executable. The launcher also normalizes that form when `MSYS2_ARG_CONV_EXCL='*'` disables conversion; native forward-slash paths such as `C:/Users/Maverick/AppData/Local/...` are accepted as well.

The browser now presents one plain-language **Next action**:

1. unlock the workspace;
2. add and approve trusted memory; then
3. ask a question and inspect its evidence.

A pending capability request replaces that guidance with **Review requested access** and keeps the agent paused until the exact request is approved once or denied.

## Configure a provider

The deterministic fake provider is the safe default. For local Ollama, set non-secret configuration before launching:

```bash
export OSCILLINK_CHAT_PROVIDER=ollama
export OSCILLINK_CHAT_BASE_URL=http://127.0.0.1:11434/v1
export OSCILLINK_CHAT_MODEL=qwen3:14b
```

For another OpenAI-compatible endpoint:

```bash
export OSCILLINK_CHAT_PROVIDER=openai_compatible
export OSCILLINK_CHAT_BASE_URL=https://provider.example/v1
export OSCILLINK_CHAT_MODEL=reviewed-model-id
read -rsp 'Provider API key: ' OSCILLINK_CHAT_API_KEY
printf '\n'
export OSCILLINK_CHAT_API_KEY
```

Provider secrets remain environment-only. Never place them in launcher arguments, source files, exported workspaces, screenshots, or support logs.

## Health checks

Liveness is minimal and does not initialize storage or contact the provider:

```bash
curl -fsS http://127.0.0.1:8765/api/v1/health/live
```

Expected state: `alive`.

Readiness inspects each canonical store read-only, checks the capability database, and performs one bounded non-generating provider `/models` probe:

```bash
curl -fsS http://127.0.0.1:8765/api/v1/health/ready
```

The response reports separate states for:

- API;
- ledger, artifacts, and memory stores;
- provider kind, model, and reachability; and
- capability broker plus configured scope count.

`not_initialized` stores are valid for a new workspace. `degraded` means a store is corrupt, the capability database is invalid, or the configured provider is unreachable. Readiness never fabricates a successful provider result.

## Trusted private-network binding

A non-loopback bind is rejected unless explicitly authorized. Supply the exact private IP and browser origin:

```bash
PYTHONPATH= .venv/Scripts/python.exe scripts/launch_private_pilot.py \
  --host 192.168.1.50 \
  --allow-network-bind \
  --trusted-host 192.168.1.50 \
  --allowed-origin http://192.168.1.50:8765 \
  --port 8765 \
  --data-dir "$DATA_DIR" \
  --credential-file "$CREDENTIAL_FILE" \
  --frontend-dist apps/web/dist
```

Do not use `0.0.0.0` unless every accepted Host value, origin, firewall rule, and client network is reviewed. This launcher does not terminate TLS.

## Stop and restart

Use `Ctrl+C` in the launch terminal. On Windows, the launcher also handles the process-group break signal used by supervised shutdown. It stops the one in-process Uvicorn server without a child frontend process.

Restart with the same `--data-dir`. The launcher preserves canonical workspace data, atomically rotates the credential file, and invalidates the previous browser credential. Paste the newly generated credential after restart.

If shutdown does not complete within eight seconds, record the process ID and logs before terminating that exact process tree. Never kill every Python or Node process on the host.

## Logs and credential rotation

- Standard output contains the URL and credential-file path only.
- Uvicorn access logs are disabled for the bounded launcher.
- Standard error contains sanitized startup or configuration failures.
- Rotate the workspace credential by stopping and starting the launcher.
- Delete an obsolete credential file only after the process using it has stopped and a replacement launch has succeeded.

## Provider outage

If the provider is unavailable:

1. liveness remains `alive` while the API process is running;
2. readiness becomes `degraded` and provider state becomes `unavailable`;
3. no chat completion is invented;
4. provider intent and terminal failure remain governed by the append-only run contract; and
5. recovery requires restoring provider reachability and starting a new user-directed run, not silently redispatching an uncertain run.

## Backup, restore, and recovery

Use the authenticated workspace export and restore APIs described in [`workspace-recovery.md`](workspace-recovery.md). Exports contain canonical databases and immutable artifacts, not credentials, provider keys, frontend files, host paths, or derived indexes.

Before restore:

1. create and verify an export;
2. stop active user work and enter a maintenance window;
3. retain the current data directory until verification succeeds; and
4. submit only a server-managed `exp_…` identifier through the authenticated restore route.

A rejected or corrupt restore leaves the active workspace unchanged. Administrative physical deletion remains deliberately outside the current API.

## Failure triage

| Symptom | Check | Action |
|---|---|---|
| Browser does not load | `/api/v1/health/live` | Verify explicit host/port and that `apps/web/dist/index.html` existed at launch |
| Unlock is rejected | Credential file timestamp | Paste the credential generated by the current launch; refreshes and restarts invalidate browser state |
| Readiness is degraded | Component states in `/health/ready` | Repair the reported provider/store boundary; do not delete canonical data |
| Provider unavailable | Provider `/models`, URL, model, timeout, key | Restore provider access, then initiate a new run |
| Capability broker error | `capabilities.sqlite3` readiness | Stop and recover from a verified export; do not recreate the database in place |
| Port already in use | Exact listener PID | Choose another port or stop only the verified stale pilot process |
| Restore rejected | Export manifest and server response | Keep the active workspace and investigate the staged export; never bypass verification |
