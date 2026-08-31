import { workspaceAuthorizationHeaders } from './workspaceAuth'

export interface WorkspaceExportEntry {
  path: string
  kind: 'database' | 'artifact'
  byte_count: number
  content_hash: string
}

export interface WorkspaceExportManifest {
  schema_version: 1
  store_versions: {
    events: 1
    memory: 1
    capabilities: 1
    proposals: 1
  }
  entries: WorkspaceExportEntry[]
}

export interface WorkspaceExportResponse {
  schema_version: 1
  export_id: string
  manifest: WorkspaceExportManifest
}

export interface WorkspaceExportView {
  schema_version: 1
  state: 'available' | 'unavailable'
  reason: 'export_missing' | 'export_invalid' | null
  export: WorkspaceExportResponse | null
}

export interface WorkspaceRestoreResponse extends WorkspaceExportResponse {
  state: 'restored'
}

const CROCKFORD = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'

function eventId() {
  const bytes = crypto.getRandomValues(new Uint8Array(26))
  return `evt_${Array.from(bytes, (value) => CROCKFORD[value % CROCKFORD.length]).join('')}`
}

export async function loadLatestWorkspaceExport(
  signal?: AbortSignal,
): Promise<WorkspaceExportView> {
  const response = await fetch('/api/v1/workspace/exports/latest', {
    headers: workspaceAuthorizationHeaders(),
    signal,
  })
  if (!response.ok) throw new Error(`latest workspace export failed: ${response.status}`)
  return response.json() as Promise<WorkspaceExportView>
}

export async function createWorkspaceExport(
  signal?: AbortSignal,
): Promise<WorkspaceExportResponse> {
  const requestId = eventId()
  const response = await fetch('/api/v1/workspace/exports', {
    method: 'POST',
    signal,
    headers: {
      ...workspaceAuthorizationHeaders(),
      'Content-Type': 'application/json',
      'Idempotency-Key': `workspace-export-${requestId}`,
    },
    body: JSON.stringify({ schema_version: 1, request_id: requestId }),
  })
  if (!response.ok) throw new Error(`workspace export failed: ${response.status}`)
  return response.json() as Promise<WorkspaceExportResponse>
}

export async function restoreWorkspaceExport(
  exportId: string,
  signal?: AbortSignal,
): Promise<WorkspaceRestoreResponse> {
  const response = await fetch('/api/v1/workspace/restores', {
    method: 'POST',
    signal,
    headers: {
      ...workspaceAuthorizationHeaders(),
      'Content-Type': 'application/json',
      'Idempotency-Key': `workspace-restore-${eventId()}`,
    },
    body: JSON.stringify({ schema_version: 1, export_id: exportId }),
  })
  if (!response.ok) throw new Error(`workspace restore failed: ${response.status}`)
  return response.json() as Promise<WorkspaceRestoreResponse>
}
