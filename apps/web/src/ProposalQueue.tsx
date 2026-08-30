import { ClipboardCheck } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import {
  decideMemoryProposal,
  loadMemoryProposals,
  type MemoryProposal,
} from './proposalApi'

interface ProposalQueueProps {
  enabled: boolean
  refreshKey: number
  onReviewed: (proposal: MemoryProposal) => void | Promise<void>
}

type PendingDecision = {
  proposal: MemoryProposal
  decision: 'approved' | 'rejected'
}

export default function ProposalQueue({ enabled, refreshKey, onReviewed }: ProposalQueueProps) {
  const [proposals, setProposals] = useState<MemoryProposal[]>([])
  const [loading, setLoading] = useState(false)
  const [loadFailed, setLoadFailed] = useState(false)
  const [pendingDecision, setPendingDecision] = useState<PendingDecision | null>(null)
  const [deciding, setDeciding] = useState(false)
  const [decisionFailed, setDecisionFailed] = useState(false)
  const [refreshFailed, setRefreshFailed] = useState(false)
  const requestVersion = useRef(0)

  useEffect(() => {
    const version = ++requestVersion.current
    if (!enabled) {
      setProposals([])
      return
    }
    const controller = new AbortController()
    setLoading(true)
    setLoadFailed(false)
    void loadMemoryProposals(controller.signal)
      .then((response) => {
        if (requestVersion.current === version) {
          setProposals(Array.isArray(response.proposals) ? response.proposals : [])
        }
      })
      .catch((error: unknown) => {
        if (
          requestVersion.current === version
          && !(error instanceof DOMException && error.name === 'AbortError')
        ) setLoadFailed(true)
      })
      .finally(() => {
        if (requestVersion.current === version) setLoading(false)
      })
    return () => controller.abort()
  }, [enabled, refreshKey])

  const confirmDecision = async () => {
    if (!enabled || pendingDecision === null || deciding) return
    setDeciding(true)
    setDecisionFailed(false)
    setRefreshFailed(false)
    try {
      const resolved = await decideMemoryProposal(
        pendingDecision.proposal.proposal_id,
        pendingDecision.decision,
      )
      setProposals((current) =>
        current.map((proposal) =>
          proposal.proposal_id === resolved.proposal_id ? resolved : proposal,
        ),
      )
      setPendingDecision(null)
      try {
        await onReviewed(resolved)
      } catch {
        setRefreshFailed(true)
      }
    } catch {
      setDecisionFailed(true)
    } finally {
      setDeciding(false)
    }
  }

  return (
    <section className="proposal-queue" aria-label="Memory proposal queue">
      <div className="proposal-queue-heading">
        <ClipboardCheck size={15} aria-hidden="true" />
        <div>
          <strong>Evidence proposals</strong>
          <span>{enabled ? (loading ? 'LOADING PROPOSALS' : `${proposals.length} DURABLE`) : 'PROPOSALS LOCKED'}</span>
        </div>
      </div>
      {enabled && !loading && proposals.length === 0 && !loadFailed ? (
        <p className="hint">No evidence proposals.</p>
      ) : null}
      <div className="proposal-list">
        {proposals.map((proposal) => (
          <article key={proposal.proposal_id} className="proposal-card" data-state={proposal.state}>
            <div>
              <strong>{proposal.source_name}</strong>
              <span>{proposal.artifact_ref.slice(0, 19)}…</span>
            </div>
            <span className="proposal-state">{proposal.state.replace('_', ' ').toUpperCase()}</span>
            {proposal.state === 'pending_review' ? (
              <div className="proposal-actions">
                <button
                  type="button"
                  className="primary-action"
                  disabled={!enabled || deciding}
                  aria-label={`Approve ${proposal.source_name}`}
                  onClick={() => setPendingDecision({ proposal, decision: 'approved' })}
                >
                  Approve
                </button>
                <button
                  type="button"
                  className="ghost-action"
                  disabled={!enabled || deciding}
                  aria-label={`Reject ${proposal.source_name}`}
                  onClick={() => setPendingDecision({ proposal, decision: 'rejected' })}
                >
                  Reject
                </button>
              </div>
            ) : null}
          </article>
        ))}
      </div>
      {pendingDecision !== null ? (
        <div className="proposal-confirmation" role="group" aria-label="Confirm proposal decision">
          <p>
            {pendingDecision.decision === 'approved' ? 'Approve' : 'Reject'} this untrusted evidence relationship?
          </p>
          <button type="button" className="primary-action" disabled={deciding} onClick={() => void confirmDecision()}>
            {deciding
              ? 'Recording…'
              : pendingDecision.decision === 'approved'
                ? 'Confirm approval'
                : 'Confirm rejection'}
          </button>
          <button type="button" className="ghost-action" disabled={deciding} onClick={() => setPendingDecision(null)}>
            Cancel
          </button>
        </div>
      ) : null}
      {loadFailed ? <p role="alert" className="error">PROPOSALS UNAVAILABLE</p> : null}
      {decisionFailed ? <p role="alert" className="error">PROPOSAL DECISION FAILED</p> : null}
      {refreshFailed ? <p role="alert" className="error">DECISION SAVED, BUT WORKSPACE COULD NOT REFRESH</p> : null}
    </section>
  )
}
