import { workspaceAuthorizationHeaders } from './workspaceAuth'

export interface ChatCitation {
  record_id: string
  content_hash: string
  title: string
  retrieval_rank: number
  retrieval_score: number
}

export interface ContextManifestProjection {
  id: string
  schema_version: number
  task_id: string
  compiled_at: string
  token_budget: number
  total_token_count: number
  policy_hash: string
  items: Array<{
    record_id: string
    content_hash: string
    title: string | null
    category: string | null
    domains: string[]
    trust_class: 'human_verified' | 'tool_verified' | 'model_generated' | 'external_untrusted' | 'system'
    status: string
    inclusion_reason: string
    token_count: number
    source_refs: string[]
    retrieval_rank: number
    retrieval_score: number
  }>
  omissions: Array<{
    record_id: string
    content_hash: string
    reason: 'token_budget' | 'no_query_match'
    retrieval_rank: number | null
    retrieval_score: number | null
  }>
  exclusion_summary: {
    not_approved_count: number
    missing_source_count: number
    superseded_count: number
    conflict_count: number
  }
}

export interface ChatMessageResponse {
  schema_version: 1
  session_id: string
  run_id: string
  task_id: string
  provider: { kind: 'fake' | 'openai_compatible'; model: string }
  answer: string
  citations: ChatCitation[]
  context_manifest: ContextManifestProjection
}

export interface RunEventProjection {
  id: string
  event_type: string
  observed_at: string
  actor: { id: string; type: 'human' | 'model' | 'tool' | 'system' }
  artifact_refs: string[]
  causal_parent_ids: string[]
  payload: Record<string, unknown>
  model?: {
    provider: string
    name: string
    configuration_hash: string
  } | null
}

export interface ChatRunInspectionResponse {
  schema_version: number
  session_id: string
  run_id: string
  events: RunEventProjection[]
  context_manifest: ContextManifestProjection
}

const CROCKFORD = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'

function contractId(prefix: 'evt' | 'ses') {
  const bytes = crypto.getRandomValues(new Uint8Array(26))
  const suffix = Array.from(bytes, (value) => CROCKFORD[value % CROCKFORD.length]).join('')
  return `${prefix}_${suffix}`
}

export function createChatSessionId() {
  return contractId('ses')
}

export async function sendChatMessage(
  sessionId: string,
  message: string,
  signal?: AbortSignal,
): Promise<ChatMessageResponse> {
  const requestId = contractId('evt')
  const response = await fetch('/api/v1/chat/messages', {
    method: 'POST',
    signal,
    headers: {
      ...workspaceAuthorizationHeaders(),
      'Content-Type': 'application/json',
      'Idempotency-Key': `chat-${requestId}`,
    },
    body: JSON.stringify({
      schema_version: 1,
      request_id: requestId,
      session_id: sessionId,
      message,
      token_budget: 2048,
    }),
  })
  if (!response.ok) throw new Error(`chat request failed: ${response.status}`)
  return response.json() as Promise<ChatMessageResponse>
}

export async function inspectChatRun(
  sessionId: string,
  runId: string,
): Promise<ChatRunInspectionResponse> {
  const response = await fetch(
    `/api/v1/chat/sessions/${encodeURIComponent(sessionId)}/runs/${encodeURIComponent(runId)}`,
  )
  if (!response.ok) {
    throw new Error(`run inspection failed: ${response.status}`)
  }
  return response.json() as Promise<ChatRunInspectionResponse>
}
