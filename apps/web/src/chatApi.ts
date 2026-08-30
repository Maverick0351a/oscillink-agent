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
  provider: { kind: 'fake' | 'ollama' | 'openai_compatible'; model: string }
  answer: string
  citations: ChatCitation[]
  context_manifest: ContextManifestProjection
}

export interface FileReadToolRequest {
  schema_version: 1
  operation: 'file.read'
  scope_id: string
  target: string
  max_bytes: number
}

export interface PendingToolRequestResponse {
  schema_version: 1
  state: 'awaiting_approval'
  session_id: string
  run_id: string
  task_id: string
  provider: ChatMessageResponse['provider']
  subject_actor_id: string
  tool_request_event_id: string
  request: FileReadToolRequest
  valid_for_seconds: number
  allowed_extensions: string[]
  network_allowed: false
}

export interface DeniedCapabilityDecisionResponse {
  schema_version: 1
  state: 'denied'
  session_id: string
  run_id: string
  tool_request_event_id: string
}

export type ChatTurnResponse = ChatMessageResponse | PendingToolRequestResponse
export type CapabilityDecisionResponse =
  | ChatMessageResponse
  | DeniedCapabilityDecisionResponse

export function isPendingToolRequest(
  response: ChatTurnResponse,
): response is PendingToolRequestResponse {
  return 'state' in response && response.state === 'awaiting_approval'
}

export function isDeniedCapabilityDecision(
  response: CapabilityDecisionResponse,
): response is DeniedCapabilityDecisionResponse {
  return 'state' in response && response.state === 'denied'
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

export type RunStepKind =
  | 'request_recorded'
  | 'context_compiled'
  | 'model_call_pending'
  | 'model_call_succeeded'
  | 'model_call_failed'
  | 'model_call_interrupted'
  | 'tool_requested'
  | 'grant_approved'
  | 'grant_denied'
  | 'tool_call_claimed'
  | 'observation'
  | 'tool_failed'
  | 'final_response'

export interface RunReconstructionProjection {
  schema_version: 1
  session_id: string
  run_id: string
  task_id: string
  state: 'in_progress' | 'awaiting_approval' | 'completed' | 'failed' | 'interrupted'
  pending_action:
    | 'context_compilation'
    | 'provider_dispatch'
    | 'provider_result'
    | 'model_continuation'
    | 'human_approval'
    | 'tool_execution'
    | 'tool_result'
    | 'provider_follow_up'
    | null
  steps: Array<{
    sequence: number
    event_id: string
    kind: RunStepKind
    event_type: string
    causal_parent_ids: string[]
  }>
  context_manifest_ref: string | null
  final_response_event_id: string | null
  model_call_count: number
  tool_call_count: number
}

export interface ChatRunInspectionResponse {
  schema_version: number
  session_id: string
  run_id: string
  events: RunEventProjection[]
  context_manifest: ContextManifestProjection
  reconstruction: RunReconstructionProjection
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
): Promise<ChatTurnResponse> {
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
  return response.json() as Promise<ChatTurnResponse>
}

export async function inspectChatRun(
  sessionId: string,
  runId: string,
  signal?: AbortSignal,
): Promise<ChatRunInspectionResponse> {
  const response = await fetch(
    `/api/v1/chat/sessions/${encodeURIComponent(sessionId)}/runs/${encodeURIComponent(runId)}`,
    { headers: workspaceAuthorizationHeaders(), signal },
  )
  if (!response.ok) {
    throw new Error(`run inspection failed: ${response.status}`)
  }
  return response.json() as Promise<ChatRunInspectionResponse>
}

export async function decideCapabilityRequest(
  pending: PendingToolRequestResponse,
  decision: 'approved' | 'denied',
  signal?: AbortSignal,
): Promise<CapabilityDecisionResponse> {
  const requestId = contractId('evt')
  const response = await fetch(
    `/api/v1/capabilities/sessions/${encodeURIComponent(pending.session_id)}`
      + `/runs/${encodeURIComponent(pending.run_id)}`
      + `/requests/${encodeURIComponent(pending.tool_request_event_id)}/decision`,
    {
      method: 'POST',
      signal,
      headers: {
        ...workspaceAuthorizationHeaders(),
        'Content-Type': 'application/json',
        'Idempotency-Key': `capability-${requestId}`,
      },
      body: JSON.stringify({
        schema_version: 1,
        request_id: requestId,
        decision,
      }),
    },
  )
  if (!response.ok) {
    throw new Error(`capability decision failed: ${response.status}`)
  }
  return response.json() as Promise<CapabilityDecisionResponse>
}
