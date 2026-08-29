import {
  Activity,
  Box,
  Database,
  MessageSquare,
  Network,
  Send,
  ShieldCheck,
  Sparkles,
  Terminal,
} from 'lucide-react'
import { useEffect, useState } from 'react'

import AgentAvatar from './AgentAvatar'
import MemoryWorkspace from './MemoryWorkspace'

interface ComponentStatus {
  state: 'not_initialized' | 'ready' | 'error'
  record_count: number
}

interface ServiceStatus {
  service: 'oscillink-agent'
  version: string
  api_state: 'online'
  storage: {
    ledger: ComponentStatus
    artifacts: ComponentStatus
  }
  features: {
    chat: 'planned' | 'preview' | 'ready'
    memory_lattice: 'planned' | 'preview' | 'ready'
    appearance: 'planned' | 'preview' | 'ready'
  }
}

type ActiveView = 'chat' | 'memory'
type ConnectionState = 'connecting' | 'online' | 'offline'

function stateLabel(state: ComponentStatus['state'] | undefined) {
  if (state === 'ready') return 'READY'
  if (state === 'error') return 'FAULT'
  return 'STANDBY'
}

export default function App() {
  const [status, setStatus] = useState<ServiceStatus | null>(null)
  const [connectionState, setConnectionState] = useState<ConnectionState>('connecting')
  const [activeView, setActiveView] = useState<ActiveView>('chat')

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
  const chatReady = status?.features.chat === 'ready'

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
            aria-pressed={activeView === 'chat'}
            onClick={() => setActiveView('chat')}
          >
            <MessageSquare size={18} aria-hidden="true" />
            <span>Chat</span>
            <i aria-hidden="true">01</i>
          </button>
          <button
            type="button"
            aria-pressed={activeView === 'memory'}
            onClick={() => setActiveView('memory')}
          >
            <Network size={18} aria-hidden="true" />
            <span>Memory Lattice</span>
            <i aria-hidden="true">02</i>
          </button>
        </nav>

        <div className="foundation-modules">
          <p className="nav-overline">FOUNDATION</p>
          <div><Database size={15} aria-hidden="true" /> Event ledger</div>
          <div><Box size={15} aria-hidden="true" /> Artifact store</div>
          <div className="muted"><ShieldCheck size={15} aria-hidden="true" /> Capability broker</div>
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
            <p className="view-title">{activeView === 'chat' ? 'Communication Channel' : 'Memory Lattice'}</p>
          </div>
          <section className="status-cluster" aria-label="System status">
            <span className={`status-pill ${connectionState}`}>{apiLabel}</span>
            {status ? (
              <>
                <span><Activity size={13} aria-hidden="true" />{status.storage.ledger.record_count} events</span>
                <span><Box size={13} aria-hidden="true" />{status.storage.artifacts.record_count} artifacts</span>
              </>
            ) : null}
          </section>
        </header>

        <main className="workspace">
          {activeView === 'chat' ? (
            <section className="chat-view">
              <div className="channel-header">
                <div>
                  <span className="section-index">01 / CHAT</span>
                  <h2>Chat</h2>
                  <p>Governed conversation with cited memory and complete event lineage.</p>
                </div>
                <span className="pending-badge">MODEL RUNTIME PENDING</span>
              </div>

              <div className="conversation-stage">
                <div className="system-divider"><span>FOUNDATION CHANNEL</span></div>
                <article className="foundation-message">
                  <div className="message-sigil"><Terminal size={18} aria-hidden="true" /></div>
                  <div>
                    <header><strong>OSCILLINK SYSTEM</strong><time>FOUNDATION PHASE</time></header>
                    <p>
                      Interface link established. Durable storage telemetry is live. Conversation
                      remains locked until the governed model runtime, cited retrieval, and
                      capability broker are connected.
                    </p>
                    <div className="readiness-row">
                      <span data-state={status?.storage.ledger.state ?? 'not_initialized'}>
                        Ledger {stateLabel(status?.storage.ledger.state)}
                      </span>
                      <span data-state={status?.storage.artifacts.state ?? 'not_initialized'}>
                        Artifacts {stateLabel(status?.storage.artifacts.state)}
                      </span>
                      <span data-state="not_initialized">Memory STANDBY</span>
                    </div>
                  </div>
                </article>
              </div>

              <div className="composer-shell">
                <label className="sr-only" htmlFor="chat-message">Message Oscillink Agent</label>
                <textarea
                  id="chat-message"
                  aria-label="Message Oscillink Agent"
                  placeholder="Chat unlocks when the governed runtime is connected."
                  disabled={!chatReady}
                />
                <div className="composer-footer">
                  <span><ShieldCheck size={14} aria-hidden="true" /> Governed channel</span>
                  <button type="button" aria-label="Send message" disabled={!chatReady}>
                    <Send size={16} aria-hidden="true" /> Send
                  </button>
                </div>
              </div>
            </section>
          ) : (
            <MemoryWorkspace latticeState={status?.features.memory_lattice ?? 'planned'} />
          )}
        </main>
      </section>

      <aside className="presence-rail">
        <div className="presence-header">
          <span className="section-index">AGENT PRESENCE</span>
          <span className="preview-chip">PREVIEW</span>
        </div>
        <AgentAvatar />
        <div className="identity-block">
          <span>OSCILLINK</span>
          <h2>Foundation Form</h2>
          <p>Appearance manifest not yet governed. This local SVG is a reversible interface preview.</p>
        </div>
        <div className="telemetry-list">
          <div><span>STATE</span><strong>IDLE</strong></div>
          <div><span>TRUST MODE</span><strong>GOVERNED</strong></div>
          <div><span>MEMORY</span><strong>STANDBY</strong></div>
          <div><span>MODEL</span><strong>DISCONNECTED</strong></div>
        </div>
        <div className="appearance-note">
          <Sparkles size={16} aria-hidden="true" />
          <p>Future forms will use versioned, human-approved appearance manifests.</p>
        </div>
      </aside>
    </div>
  )
}