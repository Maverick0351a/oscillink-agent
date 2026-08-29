import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  Link2,
  LoaderCircle,
  Sparkles,
  Tags,
  XCircle,
} from 'lucide-react'

import type {
  CategoryLegendEntry,
  DomainLegendEntry,
  MemoryNodeDetail,
} from './memoryApi'

interface MemoryInspectorProps {
  node: MemoryNodeDetail | null
  categories: CategoryLegendEntry[]
  domains: DomainLegendEntry[]
  loading: boolean
  error: string | null
  reviewing: boolean
  reviewError: string | null
  onReview: (decision: 'approved' | 'rejected') => void
}

export default function MemoryInspector({
  node,
  categories,
  domains,
  loading,
  error,
  reviewing,
  reviewError,
  onReview,
}: MemoryInspectorProps) {
  if (loading) {
    return (
      <aside className="node-inspector" aria-label="Memory node inspector" aria-live="polite">
        <span className="section-index">NODE INSPECTOR</span>
        <div className="inspector-empty"><LoaderCircle size={24} aria-hidden="true" /></div>
        <h3>Loading record</h3>
        <p>Resolving focused provenance from the typed memory projection.</p>
      </aside>
    )
  }

  if (error !== null) {
    return (
      <aside className="node-inspector" aria-label="Memory node inspector" aria-live="polite">
        <span className="section-index">NODE INSPECTOR</span>
        <div className="inspector-empty error"><AlertTriangle size={24} aria-hidden="true" /></div>
        <h3>Inspector unavailable</h3>
        <p>{error}</p>
      </aside>
    )
  }

  if (node === null) {
    return (
      <aside className="node-inspector" aria-label="Memory node inspector">
        <span className="section-index">NODE INSPECTOR</span>
        <div className="inspector-empty"><Sparkles size={24} aria-hidden="true" /></div>
        <h3>No memory selected</h3>
        <p>Select a memory record to inspect its authority, source, digest, labels, and links.</p>
      </aside>
    )
  }

  const category = categories.find((entry) => entry.category === node.category)
  const domainLabels = node.domains.map(
    (domain) => domains.find((entry) => entry.domain === domain)?.label ?? domain,
  )

  return (
    <aside className="node-inspector has-selection" aria-label="Memory node inspector">
      <span className="section-index">NODE INSPECTOR</span>
      <div className="inspector-title-row">
        <span
          className="category-sigil"
          style={{ '--category-color': category?.color ?? '#93a4ad' } as React.CSSProperties}
          aria-hidden="true"
        >
          {category?.symbol ?? '?'}
        </span>
        <div>
          <p className="inspector-kicker">{node.authority_state.toUpperCase()} RECORD</p>
          <h3>{node.title}</h3>
        </div>
      </div>

      <div className="inspector-badges" aria-label="Record classification">
        <span>{node.source_kind === 'native' ? 'NATIVE MEMORY' : 'OBSIDIAN SOURCE'}</span>
        <span>{category?.label ?? node.category}</span>
        {domainLabels.map((domain) => <span key={domain}>{domain}</span>)}
      </div>

      <dl>
        <div><dt>AUTHORITY</dt><dd>{node.authority_state.toUpperCase()}</dd></div>
        <div><dt>SOURCE STATUS</dt><dd>{node.source_status?.toUpperCase() ?? 'NOT APPLICABLE'}</dd></div>
        <div><dt>TYPE</dt><dd>{node.frontmatter_type}</dd></div>
        <div><dt>LINKS</dt><dd>{node.wikilink_count}</dd></div>
      </dl>

      {node.authority_state === 'candidate' || node.authority_state === 'curated' ? (
        <section className="memory-review-controls" aria-label="Human memory review">
          <p>Record an immutable human decision for this revision.</p>
          <div>
            <button
              type="button"
              className="approve"
              disabled={reviewing}
              onClick={() => onReview('approved')}
            >
              {reviewing ? <LoaderCircle size={15} aria-hidden="true" /> : <CheckCircle2 size={15} aria-hidden="true" />}
              Approve memory
            </button>
            <button
              type="button"
              className="reject"
              disabled={reviewing}
              onClick={() => onReview('rejected')}
            >
              <XCircle size={15} aria-hidden="true" /> Reject memory
            </button>
          </div>
        </section>
      ) : null}
      {reviewError !== null ? <p className="review-error" role="alert">{reviewError}</p> : null}

      <section className="inspector-section">
        <h4><FileText size={13} aria-hidden="true" /> Source</h4>
        <p>{node.source_path ?? 'Oscillink native memory'}</p>
        <code>{node.content_hash}</code>
      </section>

      {node.topics.length > 0 ? (
        <section className="inspector-section">
          <h4><Tags size={13} aria-hidden="true" /> Topics</h4>
          <ul className="inspector-tag-list">
            {node.topics.map((topic) => <li key={topic}>{topic}</li>)}
          </ul>
        </section>
      ) : null}

      <section className="inspector-section">
        <h4><Tags size={13} aria-hidden="true" /> Classification basis</h4>
        <ul>
          {node.classification_basis.map((basis) => <li key={basis}>{basis}</li>)}
        </ul>
      </section>

      <section className="inspector-section">
        <h4><Link2 size={13} aria-hidden="true" /> Exact wikilinks</h4>
        {node.wikilinks.length > 0 ? (
          <ul>{node.wikilinks.map((link) => <li key={link}>{link}</li>)}</ul>
        ) : (
          <p>No exact wikilinks recorded.</p>
        )}
      </section>
    </aside>
  )
}
