import { Network, Search } from 'lucide-react'
import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'

import type { FeatureState } from './foundationGraph'
import MemoryGraph from './MemoryGraph'
import MemoryInspector from './MemoryInspector'
import {
  loadMemoryNode,
  loadMemoryProjection,
  reviewMemoryNode,
  type MemoryCategory,
  type MemoryDomain,
  type MemoryNodeDetail,
  type MemoryProjection,
} from './memoryApi'

interface MemoryWorkspaceProps {
  latticeState: FeatureState
}

function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

export default function MemoryWorkspace({ latticeState }: MemoryWorkspaceProps) {
  const [activeProjection, setActiveProjection] = useState<'memory' | 'architecture'>('memory')
  const [projection, setProjection] = useState<MemoryProjection | null>(null)
  const [projectionError, setProjectionError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const selectedIdRef = useRef<string | null>(null)
  const [detail, setDetail] = useState<MemoryNodeDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [reviewing, setReviewing] = useState(false)
  const [reviewError, setReviewError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<MemoryCategory | ''>('')
  const [domainFilter, setDomainFilter] = useState<MemoryDomain | ''>('')

  useEffect(() => {
    const controller = new AbortController()
    loadMemoryProjection(controller.signal)
      .then((nextProjection) => {
        setProjection(nextProjection)
        setProjectionError(null)
        setSelectedId(nextProjection.collection.nodes[0]?.id ?? null)
      })
      .catch((error: unknown) => {
        if (!isAbort(error)) setProjectionError('The product-memory API could not be reached.')
      })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    selectedIdRef.current = selectedId
    setReviewError(null)
  }, [selectedId])

  useEffect(() => {
    if (selectedId === null) {
      setDetail(null)
      setDetailError(null)
      setDetailLoading(false)
      return
    }
    const controller = new AbortController()
    setDetail(null)
    setDetailError(null)
    setDetailLoading(true)
    loadMemoryNode(selectedId, controller.signal)
      .then((response) => setDetail(response.node))
      .catch((error: unknown) => {
        if (!isAbort(error)) setDetailError('Focused provenance could not be loaded.')
      })
      .finally(() => {
        if (!controller.signal.aborted) setDetailLoading(false)
      })
    return () => controller.abort()
  }, [selectedId])

  const state = projection?.index.state
  const nodeCount = projection?.index.node_count ?? 0
  const issueCount = projection?.index.issue_count ?? 0
  const unavailableReason = projection?.index.reason ?? null
  const badge = projectionError !== null
    ? 'MEMORY OFFLINE'
    : state === 'ready'
      ? `READY · ${nodeCount} MEMORY RECORDS`
      : state === 'degraded'
        ? `DEGRADED · ${issueCount} ISSUES`
        : state === 'unavailable'
          ? 'MEMORY UNAVAILABLE'
          : 'INDEX CONNECTING'
  const nodes = projection?.collection.nodes ?? []
  const categories = projection?.index.categories ?? []
  const domains = projection?.index.domains ?? []
  const visibleNodes = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase()
    const categoryLabels = new Map(categories.map((entry) => [entry.category, entry.label] as const))
    const domainLabels = new Map(domains.map((entry) => [entry.domain, entry.label] as const))
    return nodes.filter((node) => {
      if (categoryFilter !== '' && node.category !== categoryFilter) return false
      if (domainFilter !== '' && !node.domains.includes(domainFilter)) return false
      if (normalizedQuery === '') return true
      const searchable = [
        node.title,
        node.source_path ?? '',
        categoryLabels.get(node.category) ?? node.category,
        ...node.domains.map((domain) => domainLabels.get(domain) ?? domain),
        ...node.topics,
      ].join(' ').toLocaleLowerCase()
      return searchable.includes(normalizedQuery)
    })
  }, [categories, categoryFilter, domainFilter, domains, nodes, query])

  useEffect(() => {
    if (projection === null) return
    setSelectedId((current) => {
      if (current !== null && visibleNodes.some((node) => node.id === current)) return current
      return visibleNodes[0]?.id ?? null
    })
  }, [projection, visibleNodes])

  const filtersActive = query !== '' || categoryFilter !== '' || domainFilter !== ''
  const unavailableMessage = state !== 'unavailable'
    ? null
    : unavailableReason === 'vault_not_configured'
      ? 'No product-owned memory repository is initialized. Create memory or synchronize a source.'
      : unavailableReason === 'vault_not_found'
        ? 'The configured reviewed-memory source is unavailable.'
        : 'The reviewed-memory index could not be built safely.'

  const handleReview = async (decision: 'approved' | 'rejected') => {
    if (detail === null || reviewing) return
    const reviewedId = detail.id
    setReviewing(true)
    setReviewError(null)
    let reviewed: Awaited<ReturnType<typeof reviewMemoryNode>>
    try {
      reviewed = await reviewMemoryNode(reviewedId, decision)
    } catch {
      if (selectedIdRef.current === reviewedId) {
        setReviewError('The review decision was not recorded. The displayed authority is unchanged.')
      }
      setReviewing(false)
      return
    }
    setDetail((current) => current?.id === reviewedId ? reviewed.node : current)
    try {
      const refreshed = await loadMemoryProjection()
      setProjection(refreshed)
    } catch {
      if (selectedIdRef.current === reviewedId) {
        setReviewError('The review decision was recorded, but the lattice could not refresh.')
      }
    } finally {
      setReviewing(false)
    }
  }

  return (
    <section className="memory-view">
      <div className="channel-header">
        <div>
          <span className="section-index">02 / MEMORY</span>
          <h2>Memory Lattice</h2>
          <p>Product-owned memory with typed provenance and explicit human authority.</p>
        </div>
        <span className={`pending-badge memory-state ${state ?? 'loading'}`}>{badge}</span>
      </div>

      {projectionError !== null ? (
        <div className="memory-notice error" role="alert">{projectionError}</div>
      ) : null}

      <div className="memory-projection-tabs" aria-label="Memory projection view">
        <button
          type="button"
          aria-pressed={activeProjection === 'memory'}
          onClick={() => setActiveProjection('memory')}
        >
          Product Memory
        </button>
        <button
          type="button"
          aria-pressed={activeProjection === 'architecture'}
          onClick={() => setActiveProjection('architecture')}
        >
          System Architecture
        </button>
      </div>

      {unavailableMessage !== null && activeProjection === 'memory' ? (
        <div className="memory-notice unavailable" role="status">{unavailableMessage}</div>
      ) : null}
      {state === 'degraded' && activeProjection === 'memory' ? (
        <div className="memory-notice degraded" role="status">
          Valid reviewed records remain available; {issueCount} source issue
          {issueCount === 1 ? '' : 's'} were omitted and reported.
        </div>
      ) : null}

      {activeProjection === 'memory' ? (
        <>
      <div className="memory-controls" aria-label="Memory navigation controls">
        <label className="memory-search">
          <span className="sr-only">Search product memory</span>
          <Search size={14} aria-hidden="true" />
          <input
            type="search"
            aria-label="Search product memory"
            placeholder="Search title, source, topic…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <label>
          <span className="sr-only">Filter by category</span>
          <select
            aria-label="Filter by category"
            value={categoryFilter}
            onChange={(event) => setCategoryFilter(event.target.value as MemoryCategory | '')}
          >
            <option value="">All categories</option>
            {categories.map((entry) => (
              <option key={entry.category} value={entry.category}>{entry.symbol} · {entry.label}</option>
            ))}
          </select>
        </label>
        <label>
          <span className="sr-only">Filter by domain</span>
          <select
            aria-label="Filter by domain"
            value={domainFilter}
            onChange={(event) => setDomainFilter(event.target.value as MemoryDomain | '')}
          >
            <option value="">All domains</option>
            {domains.map((entry) => (
              <option key={entry.domain} value={entry.domain}>{entry.label}</option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="reset-filters"
          disabled={!filtersActive}
          onClick={() => {
            setQuery('')
            setCategoryFilter('')
            setDomainFilter('')
          }}
        >
          Reset
        </button>
      </div>

      <ul className="memory-category-legend" aria-label="Memory category legend">
        {categories.map((entry) => (
          <li
            key={entry.category}
            style={{ '--category-color': entry.color } as CSSProperties}
          >
            <span aria-hidden="true">{entry.symbol}</span>
            <i>{entry.label}</i>
          </li>
        ))}
      </ul>

      <div className="memory-layout">
        <div className="lattice-panel">
          <div className="graph-toolbar">
            <span><Network size={14} aria-hidden="true" /> PRODUCT MEMORY</span>
            <span>{`Exact links only · ${visibleNodes.length} of ${nodes.length} memory records`}</span>
          </div>
          <div className="memory-graph-stage">
            <MemoryGraph
              mode="memory"
              latticeState={latticeState}
              nodes={visibleNodes}
              categories={categories}
              selectedId={selectedId}
              selectedLinks={detail?.wikilinks ?? []}
              onSelect={setSelectedId}
            />
            {projection !== null && state !== 'unavailable' && visibleNodes.length === 0 ? (
              <div className="memory-graph-empty" role="status">
                No memory records match the current filters.
              </div>
            ) : null}
          </div>
        </div>
        <MemoryInspector
          node={detail}
          categories={categories}
          domains={domains}
          loading={detailLoading}
          error={detailError}
          reviewing={reviewing}
          reviewError={reviewError}
          onReview={handleReview}
        />
      </div>
        </>
      ) : (
        <div className="memory-layout architecture-layout">
          <div className="lattice-panel">
            <div className="graph-toolbar">
              <span><Network size={14} aria-hidden="true" /> SYSTEM ARCHITECTURE</span>
              <span>Foundation components · separate from canonical memory</span>
            </div>
            <MemoryGraph latticeState={latticeState} />
          </div>
          <aside className="node-inspector architecture-inspector" aria-label="Architecture view notes">
            <span className="section-index">VIEW CONTRACT</span>
            <div className="inspector-empty"><Network size={24} aria-hidden="true" /></div>
            <h3>System Architecture</h3>
            <p>
              This scaffold describes planned and connected system components. It is not reviewed
              memory data and does not create canonical relationships.
            </p>
          </aside>
        </div>
      )}
    </section>
  )
}
