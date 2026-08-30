import { workspaceAuthorizationHeaders } from './workspaceAuth'

export type MemoryProposalState = 'pending_review' | 'approved' | 'rejected'

export interface MemoryProposal {
  proposal_id: string
  state: MemoryProposalState
  target_record_id: string
  artifact_ref: string
  source_name: string
  created_at: string
  decision_event_id: string | null
  decided_at: string | null
  decided_by: string | null
}

export interface MemoryProposalCollection {
  schema_version: 1
  count: number
  proposals: MemoryProposal[]
}

const eventId = (): string => {
  const alphabet = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'
  const bytes = new Uint8Array(26)
  crypto.getRandomValues(bytes)
  return `evt_${Array.from(bytes, (value) => alphabet[value % alphabet.length]).join('')}`
}

export const loadMemoryProposals = async (
  signal?: AbortSignal,
): Promise<MemoryProposalCollection> => {
  const response = await fetch('/api/v1/memory-proposals', {
    headers: workspaceAuthorizationHeaders(),
    signal,
  })
  if (!response.ok) throw new Error(`memory proposals failed: ${response.status}`)
  return response.json() as Promise<MemoryProposalCollection>
}

export const decideMemoryProposal = async (
  proposalId: string,
  decision: 'approved' | 'rejected',
): Promise<MemoryProposal> => {
  const requestId = eventId()
  const response = await fetch(`/api/v1/memory-proposals/${proposalId}/decisions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': `proposal-decision-${requestId}`,
      ...workspaceAuthorizationHeaders(),
    },
    body: JSON.stringify({
      schema_version: 1,
      request_id: requestId,
      observed_at: new Date().toISOString(),
      decision,
    }),
  })
  if (!response.ok) throw new Error(`proposal decision failed: ${response.status}`)
  return response.json() as Promise<MemoryProposal>
}
