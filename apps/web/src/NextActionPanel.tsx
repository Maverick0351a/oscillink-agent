import { ArrowRight, Database, KeyRound, MessageSquare, ShieldAlert } from 'lucide-react'

interface NextActionPanelProps {
  workspaceState: 'unavailable' | 'locked' | 'ready'
  memoryCount: number
  pendingApproval: boolean
  hasAnswer: boolean
  onFocusCredential: () => void
  onOpenMemory: () => void
  onFocusChat: () => void
}

export default function NextActionPanel({
  workspaceState,
  memoryCount,
  pendingApproval,
  hasAnswer,
  onFocusCredential,
  onOpenMemory,
  onFocusChat,
}: NextActionPanelProps) {
  if (workspaceState !== 'ready') {
    return (
      <section className="next-action-panel" aria-label="Next action">
        <KeyRound size={20} aria-hidden="true" />
        <div>
          <span>STEP 1 OF 3</span>
          <h2>Unlock your workspace</h2>
          <p>Paste the credential created by the private-pilot launcher. It stays in this browser session.</p>
        </div>
        <button type="button" onClick={onFocusCredential}>
          Go to unlock <ArrowRight size={15} aria-hidden="true" />
        </button>
      </section>
    )
  }

  if (pendingApproval) {
    return (
      <section className="next-action-panel attention" aria-label="Next action">
        <ShieldAlert size={20} aria-hidden="true" />
        <div>
          <span>YOUR DECISION IS REQUIRED</span>
          <h2>Review requested access</h2>
          <p>The agent is paused. Check the exact file and limits below, then approve once or deny.</p>
        </div>
      </section>
    )
  }

  if (memoryCount === 0) {
    return (
      <section className="next-action-panel" aria-label="Next action">
        <Database size={20} aria-hidden="true" />
        <div>
          <span>STEP 2 OF 3</span>
          <h2>Add trusted memory</h2>
          <p>Approved memory is the evidence the agent may use when it answers you.</p>
        </div>
        <button type="button" onClick={onOpenMemory}>
          Add trusted memory <ArrowRight size={15} aria-hidden="true" />
        </button>
      </section>
    )
  }

  return (
    <section className="next-action-panel ready" aria-label="Next action">
      <MessageSquare size={20} aria-hidden="true" />
      <div>
        <span>STEP 3 OF 3</span>
        <h2>{hasAnswer ? 'Continue the conversation' : 'Ask a question'}</h2>
        <p>The agent answers from approved memory and shows the evidence and run history.</p>
      </div>
      <button type="button" onClick={onFocusChat}>
        {hasAnswer ? 'Ask another question' : 'Start asking'} <ArrowRight size={15} aria-hidden="true" />
      </button>
    </section>
  )
}
