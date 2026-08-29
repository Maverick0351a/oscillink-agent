import { Activity, Database, FileJson, X } from 'lucide-react'

import type { ChatRunInspectionResponse } from './chatApi'
import './runInspector.css'

interface RunInspectorProps {
  inspection: ChatRunInspectionResponse
  onClose: () => void
}

function label(value: string) {
  return value.replaceAll('_', ' ').toUpperCase()
}

export default function RunInspector({ inspection, onClose }: RunInspectorProps) {
  const manifest = inspection.context_manifest
  const exclusions = manifest.exclusion_summary

  return (
    <aside className="run-inspector" aria-label="Run inspector">
      <header className="run-inspector-header">
        <div>
          <span className="section-index">PERSISTED RUN / RESTART SAFE</span>
          <h2>Run Inspector</h2>
          <p>{inspection.run_id}</p>
        </div>
        <button type="button" aria-label="Close run inspector" onClick={onClose}>
          <X size={16} aria-hidden="true" />
        </button>
      </header>

      <section className="run-inspector-section" aria-label="Persisted event trajectory">
        <div className="run-inspector-section-title">
          <Activity size={15} aria-hidden="true" />
          <strong>{inspection.events.length} PERSISTED EVENTS</strong>
        </div>
        <ol className="run-event-timeline">
          {inspection.events.map((event, index) => (
            <li key={event.id}>
              <div className="run-event-index">{String(index + 1).padStart(2, '0')}</div>
              <div>
                <header>
                  <strong>{label(event.event_type)}</strong>
                  <time>{event.observed_at}</time>
                </header>
                <p>{label(event.actor.type)} · {event.actor.id}</p>
                <code>{event.id}</code>
                <dl>
                  <div>
                    <dt>PARENTS</dt>
                    <dd>{event.causal_parent_ids.length}</dd>
                  </div>
                  <div>
                    <dt>ARTIFACTS</dt>
                    <dd>{event.artifact_refs.length}</dd>
                  </div>
                </dl>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="run-inspector-section" aria-label="Compiled context manifest">
        <div className="run-inspector-section-title">
          <Database size={15} aria-hidden="true" />
          <strong>CONTEXT MANIFEST</strong>
        </div>
        <dl className="context-manifest-facts">
          <div><dt>ID</dt><dd>{manifest.id}</dd></div>
          <div><dt>COMPILED</dt><dd>{manifest.compiled_at}</dd></div>
          <div><dt>BUDGET</dt><dd>{manifest.total_token_count} / {manifest.token_budget} TOKENS</dd></div>
          <div><dt>POLICY</dt><dd>{manifest.policy_hash}</dd></div>
        </dl>

        <div className="run-exclusion-summary">
          <span>{exclusions.not_approved_count} UNAPPROVED EXCLUDED</span>
          <span>{exclusions.missing_source_count} MISSING SOURCE</span>
          <span>{exclusions.superseded_count} SUPERSEDED</span>
          <span>{exclusions.conflict_count} CONFLICTED</span>
        </div>

        <div className="run-context-items">
          {manifest.items.map((item) => (
            <article key={`${item.record_id}:${item.content_hash}`}>
              <header>
                <strong>{item.title}</strong>
                <span>RANK {item.retrieval_rank} · SCORE {item.retrieval_score}</span>
              </header>
              <p>{item.inclusion_reason}</p>
              <code>{item.record_id}</code>
              <small>{item.content_hash}</small>
            </article>
          ))}
          {manifest.items.length === 0 ? <p>NO APPROVED CONTEXT ITEMS</p> : null}
        </div>

        {manifest.omissions.length > 0 ? (
          <div className="run-context-omissions">
            <strong>{manifest.omissions.length} APPROVED ITEMS OMITTED</strong>
            {manifest.omissions.map((omission) => (
              <span key={`${omission.record_id}:${omission.reason}`}>
                {omission.record_id} · {label(omission.reason)}
              </span>
            ))}
          </div>
        ) : null}
      </section>

      <details className="exact-manifest-json">
        <summary><FileJson size={14} aria-hidden="true" /> Exact manifest JSON</summary>
        <pre>{JSON.stringify(manifest, null, 2)}</pre>
      </details>
    </aside>
  )
}
