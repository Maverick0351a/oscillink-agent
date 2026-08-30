# Workspace export, restore, rollback, and deletion

Oscillink workspace recovery treats canonical databases and immutable artifacts differently from rebuildable views and host configuration.

## Canonical export contents

A version 1 export includes only:

- `events.sqlite3` when initialized;
- `memory.sqlite3` when initialized;
- `capabilities.sqlite3` when initialized;
- content-addressed files under `artifacts/`; and
- `manifest.json`, which records the event, memory, capability, and proposal schema versions plus the SHA-256 digest and byte count of every included file.

Credentials, workspace launch tokens, environment variables, source roots, caches, frontend build output, SQLite WAL/SHM files, FTS indexes, and other derived projections are not selected for export. API responses identify a server-managed export by portable `exp_…` identity and never return its host path.

## Export procedure

`POST /api/v1/workspace/exports` requires the authenticated local human principal. The server:

1. creates a private staging directory outside the active data root;
2. uses SQLite's backup API to produce consistent database snapshots;
3. verifies database integrity and explicit `PRAGMA user_version` values;
4. verifies every artifact against its content address;
5. writes the manifest; and
6. publishes the complete staged directory as one server-managed export.

Unknown files in the active data root are excluded rather than silently treated as canonical.

## Restore and rollback

`POST /api/v1/workspace/restores` accepts only a previously issued portable export ID and requires the authenticated local human principal. Restore is intended for a single-process private deployment during a maintenance window.

Before changing the active workspace, the server:

1. validates the manifest with strict extra-field rejection and portable relative paths;
2. rejects missing, extra, linked, traversing, length-mismatched, or hash-mismatched entries;
3. copies all entries into an isolated sibling staging directory;
4. verifies SQLite integrity/schema versions and artifact content addresses again; and
5. only then renames the active directory to a temporary rollback location and publishes the staged directory.

If publication fails, the previous active directory is renamed back. A malformed or corrupt bundle never partially replaces the active workspace. The temporary rollback directory is deleted only after successful publication.

Derived indexes and projections are intentionally absent from the bundle. Current projections are rebuilt from canonical databases and artifacts when the application reopens them; future derived stores must remain disposable and version-independent.

## Deletion semantics

Administrative workspace deletion is deliberately **not** exposed by the current API. Until a separately reviewed deletion operation exists:

- deleting an export does not delete the active workspace;
- replacing the active workspace does not delete server-managed exports;
- source-system deletion remains governed by that source's own contract;
- immutable lineage, retractions, and corrections must not be rewritten as if they never existed; and
- operators must stop the private deployment and use an explicit, separately authorized administrative procedure for physical media deletion.

A future deletion operation must enumerate canonical data, exports, backups, provider-side copies, and retention obligations before removing anything.
