import { workspaceAuthorizationHeaders } from './workspaceAuth'

export interface ArtifactImportTarget {
  target: string
  source_name: string
  logical_bytes: number
}

export interface ArtifactImportScope {
  scope_id: string
  state: 'configured' | 'unavailable'
  targets: ArtifactImportTarget[]
}

export interface ArtifactImportSourceCollection {
  schema_version: 1
  count: number
  scopes: ArtifactImportScope[]
}

export interface ArtifactImportResponse {
  schema_version: 1
  state: 'imported'
  event_id: string
  artifact: {
    artifact_ref: string
    source_scope_id: string
    source_name: string
    media_type: string
    logical_bytes: number
    unique_physical_bytes: number
    deduplicated: boolean
  }
  association:
    | { state: 'unattached' }
    | {
        state: 'candidate'
        review_state: 'pending_review'
        target_record_id: string
        event_id: string
      }
}

const eventId = (): string => {
  const alphabet = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'
  const bytes = new Uint8Array(26)
  crypto.getRandomValues(bytes)
  return `evt_${Array.from(bytes, (value) => alphabet[value % alphabet.length]).join('')}`
}

export const loadArtifactImportSources = async (
  signal?: AbortSignal,
): Promise<ArtifactImportSourceCollection> => {
  const response = await fetch('/api/v1/artifact-imports/sources', {
    headers: workspaceAuthorizationHeaders(),
    signal,
  })
  if (!response.ok) throw new Error(`artifact import sources failed: ${response.status}`)
  return response.json() as Promise<ArtifactImportSourceCollection>
}

export const importArtifact = async (input: {
  scopeId: string
  target: string
  targetRecordId: string
}): Promise<ArtifactImportResponse> => {
  const requestId = eventId()
  const response = await fetch('/api/v1/artifact-imports', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': `artifact-import-${requestId}`,
      ...workspaceAuthorizationHeaders(),
    },
    body: JSON.stringify({
      schema_version: 1,
      request_id: requestId,
      observed_at: new Date().toISOString(),
      scope_id: input.scopeId,
      target: input.target,
      target_record_id: input.targetRecordId,
    }),
  })
  if (!response.ok) throw new Error(`artifact import failed: ${response.status}`)
  return response.json() as Promise<ArtifactImportResponse>
}
