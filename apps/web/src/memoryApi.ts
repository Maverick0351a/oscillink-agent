export type MemoryProjectionState = 'ready' | 'degraded' | 'unavailable'
export type MemoryAuthorityState =
  | 'curated'
  | 'candidate'
  | 'approved'
  | 'rejected'
  | 'superseded'
  | 'contradicted'
  | 'retracted'
export type MemorySourceKind = 'native' | 'obsidian'
export type ArchitectureNodeId =
  | 'identity-role'
  | 'goals-commitments'
  | 'projects-work'
  | 'knowledge-research'
  | 'people-relationships'
  | 'decisions-lessons'
  | 'preferences-context'
export type MemoryUnavailableReason =
  | 'vault_not_configured'
  | 'vault_not_found'
  | 'index_build_failed'

export type MemoryCategory =
  | 'research'
  | 'tooling'
  | 'project'
  | 'experiment'
  | 'governance'
  | 'reference'
  | 'note'

export type MemoryDomain =
  | 'ai_ml'
  | 'rf_em'
  | 'science'
  | 'mathematics'
  | 'engineering'
  | 'software'
  | 'business'
  | 'general'

export interface CategoryLegendEntry {
  category: MemoryCategory
  label: string
  color: string
  symbol: string
}

export interface DomainLegendEntry {
  domain: MemoryDomain
  label: string
}

export interface MemoryIndexIssue {
  source_path: string
  code: string
  message: string
}

export interface MemoryIndexProjection {
  schema_version: 1
  state: MemoryProjectionState
  reason: MemoryUnavailableReason | null
  index_hash: string | null
  node_count: number
  issue_count: number
  categories: CategoryLegendEntry[]
  domains: DomainLegendEntry[]
  issues: MemoryIndexIssue[]
}

export interface MemoryNodeSummary {
  id: string
  title: string
  source_path: string | null
  source_status: string | null
  authority_state: MemoryAuthorityState
  source_kind: MemorySourceKind
  category: MemoryCategory
  domains: MemoryDomain[]
  topics: string[]
  content_hash: string
  wikilink_count: number
  architecture_node_ids: ArchitectureNodeId[]
}

export interface MemoryNodeCollection {
  schema_version: 1
  state: MemoryProjectionState
  reason: MemoryUnavailableReason | null
  index_hash: string | null
  count: number
  applied_filters: {
    category: MemoryCategory | null
    domain: MemoryDomain | null
  }
  nodes: MemoryNodeSummary[]
}

export interface MemoryNodeDetail extends MemoryNodeSummary {
  frontmatter_type: string
  wikilinks: string[]
  classification_basis: string[]
}

export interface MemoryNodeDetailResponse {
  schema_version: 1
  state: 'ready'
  node: MemoryNodeDetail
}

export interface MemoryProjection {
  index: MemoryIndexProjection
  collection: MemoryNodeCollection
}

async function requestJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal })
  if (!response.ok) throw new Error(`memory request failed: ${response.status}`)
  return response.json() as Promise<T>
}

const crockfordAlphabet = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'

function createEventId(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(26))
  const suffix = Array.from(bytes, (value) => crockfordAlphabet[value % 32]).join('')
  return `evt_${suffix}`
}

async function loadMemoryProjectionSnapshot(signal?: AbortSignal): Promise<MemoryProjection> {
  const [index, collection] = await Promise.all([
    requestJson<MemoryIndexProjection>('/api/v1/memory/index', signal),
    requestJson<MemoryNodeCollection>('/api/v1/memory/nodes', signal),
  ])
  return { index, collection }
}

export async function loadMemoryProjection(signal?: AbortSignal): Promise<MemoryProjection> {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const projection = await loadMemoryProjectionSnapshot(signal)
    if (projection.index.index_hash === projection.collection.index_hash) return projection
  }
  throw new Error('memory projection changed while loading')
}

export function loadMemoryNode(
  nodeId: string,
  signal?: AbortSignal,
): Promise<MemoryNodeDetailResponse> {
  return requestJson<MemoryNodeDetailResponse>(
    `/api/v1/memory/nodes/${encodeURIComponent(nodeId)}`,
    signal,
  )
}

export async function reviewMemoryNode(
  nodeId: string,
  decision: 'approved' | 'rejected',
): Promise<MemoryNodeDetailResponse> {
  const requestId = createEventId()
  const response = await fetch(
    `/api/v1/memory/nodes/${encodeURIComponent(nodeId)}/reviews`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Idempotency-Key': `memory-review-${requestId}`,
      },
      body: JSON.stringify({
        schema_version: 1,
        request_id: requestId,
        decision,
      }),
    },
  )
  if (!response.ok) throw new Error(`memory review failed: ${response.status}`)
  return response.json() as Promise<MemoryNodeDetailResponse>
}
