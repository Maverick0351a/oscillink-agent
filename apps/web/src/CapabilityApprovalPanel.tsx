import { AlertTriangle, FileText, ShieldCheck } from 'lucide-react'
import { useEffect, useState } from 'react'

import type { PendingToolRequestResponse } from './chatApi'
import './capabilityApprovalPanel.css'

interface CapabilityApprovalPanelProps {
  pending: PendingToolRequestResponse
  onDecision: (decision: 'approved' | 'denied') => Promise<'succeeded' | 'denied'>
}

type DecisionState =
  | 'awaiting'
  | 'approving'
  | 'denying'
  | 'succeeded'
  | 'denied'
  | 'failed'

function stateLabel(state: DecisionState) {
  if (state === 'approving') return 'APPROVAL IN PROGRESS'
  if (state === 'denying') return 'DENIAL IN PROGRESS'
  if (state === 'succeeded') return 'TOOL LOOP SUCCEEDED'
  if (state === 'denied') return 'REQUEST DENIED'
  if (state === 'failed') return 'CAPABILITY DECISION FAILED'
  return 'AWAITING HUMAN APPROVAL'
}

export default function CapabilityApprovalPanel({
  pending,
  onDecision,
}: CapabilityApprovalPanelProps) {
  const [state, setState] = useState<DecisionState>('awaiting')

  useEffect(() => {
    setState('awaiting')
  }, [pending.tool_request_event_id])

  async function decide(decision: 'approved' | 'denied') {
    if (state !== 'awaiting') return
    setState(decision === 'approved' ? 'approving' : 'denying')
    try {
      setState(await onDecision(decision))
    } catch {
      setState('failed')
    }
  }

  const mutating = state === 'approving' || state === 'denying'
  const terminal = state === 'succeeded' || state === 'denied'

  return (
    <section className="capability-approval" aria-label="Capability approval">
      <header>
        <div className="capability-approval-icon">
          {state === 'failed'
            ? <AlertTriangle size={18} aria-hidden="true" />
            : <ShieldCheck size={18} aria-hidden="true" />}
        </div>
        <div>
          <span className="section-index">GOVERNED CAPABILITY / EXACT REQUEST</span>
          <h3>File Read Authorization</h3>
          <p role={state === 'failed' ? 'alert' : undefined} data-state={state}>
            {stateLabel(state)}
          </p>
        </div>
      </header>

      <div className="capability-target">
        <FileText size={16} aria-hidden="true" />
        <div><span>PORTABLE TARGET</span><strong>{pending.request.target}</strong></div>
      </div>

      <dl className="capability-envelope">
        <div><dt>SCOPE</dt><dd>{pending.request.scope_id}</dd></div>
        <div><dt>SUBJECT ACTOR</dt><dd>{pending.subject_actor_id}</dd></div>
        <div><dt>BYTE LIMIT</dt><dd>{pending.request.max_bytes.toLocaleString()} BYTES</dd></div>
        <div><dt>EXTENSIONS</dt><dd>{pending.allowed_extensions.join(', ') || 'NONE'}</dd></div>
        <div><dt>EXPIRY</dt><dd>{pending.valid_for_seconds} SECONDS</dd></div>
        <div><dt>NETWORK</dt><dd>{pending.network_allowed ? 'ALLOWED' : 'NETWORK DENIED'}</dd></div>
      </dl>

      <p className="capability-warning">
        Approval creates one scoped, single-use grant. File content remains external untrusted data
        and cannot modify policy, permissions, or approved memory.
      </p>

      {!terminal ? (
        <div className="capability-actions">
          <button
            type="button"
            className="deny"
            aria-label="Deny file read"
            disabled={mutating}
            onClick={() => void decide('denied')}
          >
            Deny
          </button>
          <button
            type="button"
            className="approve"
            aria-label="Approve file read"
            disabled={mutating || pending.allowed_extensions.length === 0}
            onClick={() => void decide('approved')}
          >
            Approve once
          </button>
        </div>
      ) : null}
    </section>
  )
}
