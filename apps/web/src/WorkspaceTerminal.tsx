import {
  Box,
  ChevronRight,
  CircleDot,
  Clock3,
  FolderLock,
  Network,
  Play,
  ShieldCheck,
  Terminal,
  WifiOff,
} from 'lucide-react'

interface WorkspaceTerminalProps {
  terminalState: 'planned' | 'preview' | 'ready'
  embedded?: boolean
}

const guardrails = [
  {
    icon: FolderLock,
    label: 'Workspace scope',
    value: 'Not assigned',
    detail: 'No host path exposed',
  },
  {
    icon: Box,
    label: 'Sandbox',
    value: 'Policy pending',
    detail: 'No process created',
  },
  {
    icon: WifiOff,
    label: 'Network',
    value: 'Denied by default',
    detail: 'No egress grant',
  },
  {
    icon: Clock3,
    label: 'Execution budget',
    value: 'Not issued',
    detail: 'No runtime authority',
  },
]

export default function WorkspaceTerminal({ terminalState, embedded = false }: WorkspaceTerminalProps) {
  const stateLabel = terminalState === 'preview' ? 'PREVIEW · EXECUTION LOCKED' : 'PLANNED · OFFLINE'

  return (
    <section className={`terminal-view ${embedded ? 'is-embedded' : ''}`}>
      <div className="channel-header terminal-channel-header">
        <div>
          <span className="section-index">03 / WORKSPACE</span>
          <h2>Workspace Terminal</h2>
          <p>Governed command execution with explicit scope, policy, budgets and complete run provenance.</p>
        </div>
        <span className="pending-badge terminal-state-badge">{stateLabel}</span>
      </div>

      <div className="terminal-layout">
        <section className="terminal-console" aria-label="Governed command runner preview">
          <header className="terminal-console-bar">
            <div className="terminal-window-marks" aria-hidden="true">
              <i />
              <i />
              <i />
            </div>
            <span><Terminal size={13} aria-hidden="true" /> WORKSPACE://NOT-ASSIGNED</span>
            <strong><CircleDot size={10} aria-hidden="true" /> NO SESSION</strong>
          </header>

          <div className="terminal-screen" role="log" aria-label="Terminal output" aria-live="polite">
            <div className="terminal-boot-line">
              <span>OSCILLINK</span>
              <p>Governed workspace command surface</p>
              <i>v0.1 preview</i>
            </div>
            <div className="terminal-notice">
              <ShieldCheck size={18} aria-hidden="true" />
              <div>
                <strong>Execution boundary not initialized</strong>
                <p>
                  No shell, process or host path has been opened. Commands unlock only after an
                  authenticated workspace, sandbox policy and typed capability grant are active.
                </p>
              </div>
            </div>
            <div className="terminal-system-lines" aria-label="Terminal readiness">
              <p><span>[scope]</span> No workspace assigned</p>
              <p><span>[sandbox]</span> Sandbox policy pending</p>
              <p><span>[network]</span> Denied by default</p>
              <p><span>[audit]</span> Append-only command record required</p>
            </div>
          </div>

          <div className="terminal-command-row">
            <ChevronRight size={16} aria-hidden="true" />
            <label className="sr-only" htmlFor="workspace-command">Workspace command</label>
            <input
              id="workspace-command"
              aria-label="Workspace command"
              placeholder="Command input unlocks after the governed runner is connected"
              disabled
            />
            <button type="button" aria-label="Run command" disabled>
              <Play size={14} aria-hidden="true" /> Run
            </button>
          </div>
          <footer className="terminal-console-footer">
            <span><ShieldCheck size={12} aria-hidden="true" /> POLICY FIRST</span>
            <span>0 PROCESSES</span>
            <span>0 B OUTPUT</span>
          </footer>
        </section>

        <aside className="terminal-guardrails" aria-label="Terminal guardrails">
          <header>
            <span className="section-index">EXECUTION ENVELOPE</span>
            <h3>Guardrails</h3>
            <p>Every command must resolve to a workspace, actor, grant and bounded process.</p>
          </header>

          <div className="terminal-guardrail-grid">
            {guardrails.map(({ icon: Icon, label, value, detail }) => (
              <article key={label}>
                <Icon size={16} aria-hidden="true" />
                <div>
                  <span>{label}</span>
                  <strong>{value}</strong>
                  <small>{detail}</small>
                </div>
              </article>
            ))}
          </div>

          <section className="terminal-policy-chain">
            <h4><Network size={14} aria-hidden="true" /> Authorization chain</h4>
            <ol>
              <li><span>01</span><div><strong>Identify actor</strong><small>Human and agent authority remain separate</small></div></li>
              <li><span>02</span><div><strong>Resolve workspace</strong><small>Relative paths inside one explicit scope</small></div></li>
              <li><span>03</span><div><strong>Evaluate policy</strong><small>Arguments, network, time and output bounded</small></div></li>
              <li><span>04</span><div><strong>Record outcome</strong><small>Exit status and artifacts enter run history</small></div></li>
            </ol>
          </section>
        </aside>
      </div>
    </section>
  )
}
