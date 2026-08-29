import {
  Activity,
  Box,
  Database,
  MessageSquare,
  Send,
  ShieldCheck,
  Terminal,
  X,
} from 'lucide-react'
import { useEffect, useState } from 'react'

import AgentAvatar from './AgentAvatar'
import {
  createChatSessionId,
  inspectChatRun,
  sendChatMessage,
  type ChatMessageResponse,
  type ChatRunInspectionResponse,
} from './chatApi'
import MemoryWorkspace from './MemoryWorkspace'
import RunInspector from './RunInspector'
import WorkspaceTerminal from './WorkspaceTerminal'
import { setWorkspaceCredential } from './workspaceAuth'

interface ComponentStatus {
  state: 'not_initialized' | 'ready' | 'error'
  record_count: number
}

interface ServiceStatus {
  service: 'oscillink-agent'
  version: string
  api_state: 'online'
  workspace_auth: {
    state: 'unavailable' | 'locked' | 'ready'
  }
  storage: {
    ledger: ComponentStatus
    artifacts: ComponentStatus
    memory: ComponentStatus
  }
  features: {
    chat: 'planned' | 'preview' | 'ready'
    capability_broker: 'planned' | 'preview' | 'ready'
    memory_lattice: 'planned' | 'preview' | 'ready'
    appearance: 'planned' | 'preview' | 'ready'
    workspace_terminal: 'planned' | 'preview' | 'ready'
  }
}

type ConnectionState = 'connecting' | 'online' | 'offline'

function stateLabel(state: ComponentStatus['state'] | undefined) {
  if (state === 'ready') return 'READY'
  if (state === 'error') return 'FAULT'
  return 'STANDBY'
}

export default function App() {
  const [status, setStatus] = useState<ServiceStatus | null>(null)
  const [connectionState, setConnectionState] = useState<ConnectionState>('connecting')
  const [terminalOpen, setTerminalOpen] = useState(false)
  const [activeView, setActiveView] = useState<'agent' | 'memory'>('agent')
  const [chatMessage, setChatMessage] = useState('')
  const [chatResponse, setChatResponse] = useState<ChatMessageResponse | null>(null)
  const [chatError, setChatError] = useState<string | null>(null)
  const [chatSubmitting, setChatSubmitting] = useState(false)
  const [runInspection, setRunInspection] = useState<ChatRunInspectionResponse | null>(null)
  const [runInspecting, setRunInspecting] = useState(false)
  const [chatSessionId] = useState(createChatSessionId)
  const [credentialInput, setCredentialInput] = useState('')
  const [authSubmitting, setAuthSubmitting] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/v1/status', { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`status request failed: ${response.status}`)
        }
        return response.json() as Promise<ServiceStatus>
      })
      .then((nextStatus) => {
        if (nextStatus.workspace_auth.state !== 'ready') {
          setWorkspaceCredential(null)
        }
        setStatus(nextStatus)
        setConnectionState('online')
      })
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === 'AbortError')) {
          setStatus(null)
          setConnectionState('offline')
        }
      })
    return () => controller.abort()
  }, [])

  const apiLabel =
    connectionState === 'connecting' ? 'CONNECTING' : `API ${connectionState.toUpperCase()}`
  const workspaceReady = status?.workspace_auth.state === 'ready'
  const chatReady = status?.features.chat === 'ready' && workspaceReady

  async function unlockWorkspace() {
    const credential = credentialInput.trim()
    if (!credential || authSubmitting) return
    setAuthSubmitting(true)
    setAuthError(null)
    try {
      const response = await fetch('/api/v1/status', {
        headers: { Authorization: `Bearer ${credential}` },
      })
      if (!response.ok) throw new Error(`status request failed: ${response.status}`)
      const nextStatus = await response.json() as ServiceStatus
      if (nextStatus.workspace_auth.state !== 'ready') {
        throw new Error('credential rejected')
      }
      setWorkspaceCredential(credential)
      setCredentialInput('')
      setStatus(nextStatus)
    } catch {
      setWorkspaceCredential(null)
      setAuthError('The local workspace credential was not accepted.')
    } finally {
      setAuthSubmitting(false)
    }
  }

  async function submitChatMessage() {
    const message = chatMessage.trim()
    if (!chatReady || chatSubmitting || !message) return
    setChatSubmitting(true)
    setChatError(null)
    try {
      const response = await sendChatMessage(chatSessionId, message)
      setChatResponse(response)
      setRunInspection(null)
      setChatMessage('')
    } catch {
      setChatError('The governed chat run could not be completed.')
    } finally {
      setChatSubmitting(false)
    }
  }

  async function inspectPersistedRun() {
    if (!chatResponse || runInspecting) return
    setRunInspecting(true)
    setChatError(null)
    try {
      setRunInspection(await inspectChatRun(chatResponse.session_id, chatResponse.run_id))
    } catch {
      setChatError('The persisted run could not be inspected.')
    } finally {
      setRunInspecting(false)
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup">
          <div className="brand-logo-frame">
            <img
              className="brand-logo"
              src="/oscillink-logo.png"
              alt="Oscillink logo"
              width="1024"
              height="1024"
            />
          </div>
          <div className="brand-copy">
            <h1><span>Oscillink</span> Agent</h1>
            <p>LONGITUDINAL SYSTEM</p>
          </div>
        </div>

        <nav className="primary-nav" aria-label="Primary navigation">
          <p className="nav-overline">INTERFACES</p>
          <button
            type="button"
            aria-pressed={activeView === 'agent'}
            onClick={() => setActiveView('agent')}
          >
            <MessageSquare size={18} aria-hidden="true" />
            <span>Agent Workspace</span>
            <i aria-hidden="true">01</i>
          </button>
          <button
            type="button"
            aria-label="Open Product Memory"
            aria-pressed={activeView === 'memory'}
            onClick={() => setActiveView('memory')}
          >
            <Database size={18} aria-hidden="true" />
            <span>Product Memory</span>
            <i aria-hidden="true">02</i>
          </button>
        </nav>

        <div className="foundation-modules">
          <p className="nav-overline">FOUNDATION</p>
          <div><Database size={15} aria-hidden="true" /> Event ledger</div>
          <div><Box size={15} aria-hidden="true" /> Artifact store</div>
          <div className="muted">
            <ShieldCheck size={15} aria-hidden="true" />
            Capability broker {status?.features.capability_broker.toUpperCase() ?? 'PLANNED'}
          </div>
        </div>

        <div className="sidebar-footer">
          <span className={`connection-orb ${connectionState}`} />
          <div>
            <strong>{connectionState.toUpperCase()}</strong>
            <small>LOCAL NODE / v{status?.version ?? '0.1.0'}</small>
          </div>
        </div>
      </aside>

      <section className="workstation">
        <header className="topbar">
          <div>
            <p className="eyebrow">OSCILLINK // AGENT CONSOLE</p>
            <p className="view-title">{activeView === 'agent' ? 'Agent Workspace' : 'Product Memory'}</p>
          </div>
          <section className="status-cluster" aria-label="System status">
            <span className={`status-pill ${connectionState}`}>{apiLabel}</span>
            {status ? (
              <>
                <span>AUTH {status.workspace_auth.state.toUpperCase()}</span>
                <span><Activity size={13} aria-hidden="true" />{status.storage.ledger.record_count} events</span>
                <span><Box size={13} aria-hidden="true" />{status.storage.artifacts.record_count} artifacts</span>
              </>
            ) : null}
          </section>
        </header>

        {status?.workspace_auth.state === 'locked' ? (
          <section className="workspace-auth-bar" aria-label="Local workspace authentication">
            <label htmlFor="workspace-credential">Local workspace credential</label>
            <input
              id="workspace-credential"
              type="password"
              autoComplete="off"
              value={credentialInput}
              onChange={(event) => setCredentialInput(event.target.value)}
            />
            <button
              type="button"
              disabled={authSubmitting || !credentialInput.trim()}
              onClick={() => void unlockWorkspace()}
            >
              {authSubmitting ? 'Unlocking workspace' : 'Unlock workspace'}
            </button>
            {authError ? <span role="alert">{authError}</span> : null}
          </section>
        ) : null}

        <main className="workspace">
          {activeView === 'memory' ? (
            <MemoryWorkspace
              latticeState={status?.features.memory_lattice ?? 'planned'}
              mutationsEnabled={workspaceReady}
            />
          ) : (
            <div className="unified-agent-workspace">
            <div className={`chat-operations-column ${terminalOpen ? 'has-terminal' : ''}`}>
            <section className="chat-view" aria-label="Agent chat">
              <div className="channel-header">
                <div className="chat-agent-presence">
                  <AgentAvatar />
                  <div>
                    <span className="section-index">OSCILLINK AGENT / CHAT</span>
                    <h2>Chat</h2>
                    <p>Governed conversation with cited memory and complete event lineage.</p>
                  </div>
                </div>
                <div className="channel-actions">
                  <span className="pending-badge">
                    {chatReady
                      ? 'DETERMINISTIC RUNTIME'
                      : workspaceReady
                        ? 'MODEL RUNTIME PENDING'
                        : 'WORKSPACE AUTHENTICATION REQUIRED'}
                  </span>
                  <button
                    type="button"
                    className="terminal-pane-toggle"
                    aria-label={terminalOpen ? 'Close terminal pane' : 'Open terminal pane'}
                    aria-pressed={terminalOpen}
                    onClick={() => setTerminalOpen((open) => !open)}
                  >
                    {terminalOpen ? <X size={15} aria-hidden="true" /> : <Terminal size={15} aria-hidden="true" />}
                    {terminalOpen ? 'Close terminal' : 'Terminal'}
                  </button>
                </div>
              </div>

              <div className="conversation-stage">
                <div className="system-divider"><span>FOUNDATION CHANNEL</span></div>
                <article className="foundation-message">
                  <div className="message-sigil"><Terminal size={18} aria-hidden="true" /></div>
                  <div>
                    <header><strong>OSCILLINK SYSTEM</strong><time>FOUNDATION PHASE</time></header>
                    <p>
                      {chatReady
                        ? 'Deterministic local chat is connected. Each run compiles approved product memory into a persisted, revision-bound context manifest.'
                        : 'Interface link established. Conversation remains locked until the governed model runtime and cited retrieval are connected.'}
                    </p>
                    <div className="readiness-row">
                      <span data-state={status?.storage.ledger.state ?? 'not_initialized'}>
                        Ledger {stateLabel(status?.storage.ledger.state)}
                      </span>
                      <span data-state={status?.storage.artifacts.state ?? 'not_initialized'}>
                        Artifacts {stateLabel(status?.storage.artifacts.state)}
                      </span>
                      <span data-state={status?.storage.memory.state ?? 'not_initialized'}>
                        Memory {stateLabel(status?.storage.memory.state)}
                      </span>
                    </div>
                  </div>
                </article>
                {chatResponse ? (
                  <article className="chat-run-message" aria-label="Governed chat response">
                    <header>
                      <strong>OSCILLINK AGENT</strong>
                      <span>{chatResponse.provider.model}</span>
                    </header>
                    <p>{chatResponse.answer}</p>
                    <div className="chat-run-citations">
                      {chatResponse.citations.map((citation) => (
                        <span key={`${citation.record_id}:${citation.content_hash}`}>
                          CITED MEMORY · {citation.title}
                        </span>
                      ))}
                    </div>
                    <footer>
                      <span>RUN {chatResponse.run_id.replace('run_', '')}</span>
                      <span>CONTEXT {chatResponse.context_manifest.id.replace('ctx_', '')}</span>
                      <span>{chatResponse.context_manifest.total_token_count} TOKENS</span>
                      <button
                        type="button"
                        aria-label="Inspect persisted run"
                        disabled={runInspecting}
                        onClick={() => void inspectPersistedRun()}
                      >
                        <Activity size={13} aria-hidden="true" />
                        {runInspecting ? 'LOADING RUN' : 'INSPECT RUN'}
                      </button>
                    </footer>
                  </article>
                ) : null}
                {chatError ? <p className="chat-run-error" role="alert">{chatError}</p> : null}
              </div>

              <div className="composer-shell">
                <label className="sr-only" htmlFor="chat-message">Message Oscillink Agent</label>
                <textarea
                  id="chat-message"
                  aria-label="Message Oscillink Agent"
                  placeholder={chatReady ? 'Ask using approved product memory.' : 'Chat unlocks when the governed runtime is connected.'}
                  disabled={!chatReady}
                  value={chatMessage}
                  onChange={(event) => setChatMessage(event.target.value)}
                />
                <div className="composer-footer">
                  <span><ShieldCheck size={14} aria-hidden="true" /> Governed channel</span>
                  <button
                    type="button"
                    aria-label="Send message"
                    disabled={!chatReady || chatSubmitting || !chatMessage.trim()}
                    onClick={() => void submitChatMessage()}
                  >
                    <Send size={16} aria-hidden="true" /> Send
                  </button>
                </div>
              </div>
            </section>
            {terminalOpen ? (
              <section className="chat-terminal-pane" aria-label="Chat terminal pane">
                <WorkspaceTerminal
                  terminalState={status?.features.workspace_terminal ?? 'planned'}
                  embedded
                />
              </section>
            ) : null}
            </div>
            <MemoryWorkspace
              latticeState={status?.features.memory_lattice ?? 'planned'}
              embeddedArchitecture
              activeRetrievalRecordIds={chatResponse?.citations.map((citation) => citation.record_id) ?? []}
            />
            {runInspection ? (
              <RunInspector inspection={runInspection} onClose={() => setRunInspection(null)} />
            ) : null}
          </div>
          )}
        </main>
      </section>
    </div>
  )
}