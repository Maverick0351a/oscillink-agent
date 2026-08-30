import { Network, Search, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'

import { buildFoundationGraph, type FeatureState } from './foundationGraph'
import ArtifactImportPanel from './ArtifactImportPanel'
import MemoryCreatePanel from './MemoryCreatePanel'
import MemoryGraph from './MemoryGraph'
import MemoryInspector from './MemoryInspector'
import ProposalQueue from './ProposalQueue'
import SourceSyncPanel from './SourceSyncPanel'
import {
  loadMemoryNode,
  loadMemoryProjection,
  reviewMemoryNode,
  type MemoryCategory,
  type MemoryDomain,
  type MemoryNodeDetail,
  type MemoryNodeSummary,
  type MemoryProjection,
  type ArchitectureNodeId,
} from './memoryApi'

interface MemoryWorkspaceProps {
  latticeState: FeatureState
  embeddedArchitecture?: boolean
  activeRetrievalRecordIds?: string[]
  mutationsEnabled?: boolean
}

interface ArchitectureMemoryPanelProps {
  latticeState: FeatureState
  nodes: MemoryNodeSummary[]
  categories: MemoryProjection['index']['categories']
  domains: MemoryProjection['index']['domains']
  embedded?: boolean
  activeRetrievalNodeIds: ArchitectureNodeId[]
}

function ArchitectureMemoryPanel({
  latticeState,
  nodes,
  categories,
  domains,
  embedded = false,
  activeRetrievalNodeIds,
}: ArchitectureMemoryPanelProps) {
  const architecture = useMemo(() => buildFoundationGraph(latticeState), [latticeState])
  const [selectedArchitectureId, setSelectedArchitectureId] = useState<ArchitectureNodeId | null>(null)
  const selectedArchitecture = architecture.nodes.find((node) => node.id === selectedArchitectureId)
  const associatedNodes = selectedArchitectureId === null
    ? []
    : nodes.filter((node) => node.architecture_node_ids.includes(selectedArchitectureId))
  const categoryLabels = new Map(categories.map((entry) => [entry.category, entry.label] as const))
  const domainLabels = new Map(domains.map((entry) => [entry.domain, entry.label] as const))
  const recordLabel = `${associatedNodes.length} associated ${associatedNodes.length === 1 ? 'record' : 'records'}`

  return (
    <section className={`architecture-memory-panel ${embedded ? 'is-embedded' : ''}`} aria-label="System architecture memory">
      {embedded ? (
        <header className="architecture-memory-header">
          <div>
            <span className="section-index">MEMORY ARCHITECTURE</span>
            <h2>System Architecture</h2>
          </div>
          <span className={`retrieval-state ${activeRetrievalNodeIds.length > 0 ? 'active' : ''}`}>
            {activeRetrievalNodeIds.length > 0 ? `${activeRetrievalNodeIds.length} RETRIEVAL ACTIVE` : 'NO ACTIVE RETRIEVAL'}
          </span>
        </header>
      ) : null}
      <div className="memory-layout architecture-layout">
        <section className="lattice-panel" aria-label="Architecture visualization">
          <div className="graph-toolbar">
            <span><Network size={14} aria-hidden="true" /> MEMORY CONTAINERS</span>
            <span>Selected cyan · agent retrieval orange</span>
          </div>
          <MemoryGraph
            latticeState={latticeState}
            nodes={nodes}
            selectedId={selectedArchitectureId}
            activeRetrievalNodeIds={activeRetrievalNodeIds}
            onSelect={(id) => setSelectedArchitectureId(id as ArchitectureNodeId)}
          />
        </section>
        {selectedArchitecture !== undefined ? (
        <aside className="node-inspector architecture-memory-inspector" aria-label="Architecture memory inspector">
          <span className="section-index">NODE MEMORY</span>
          <button
            type="button"
            className="architecture-inspector-close"
            aria-label="Close memory details"
            onClick={() => setSelectedArchitectureId(null)}
          >
            <X size={14} aria-hidden="true" />
          </button>
          <header>
            <h3>{selectedArchitecture.label}</h3>
            <p>{selectedArchitecture.detail}</p>
            <strong>{recordLabel}</strong>
          </header>
          <div className="architecture-memory-records">
            {associatedNodes.length === 0 ? (
              <p className="architecture-memory-empty">No memory is explicitly associated with this container.</p>
            ) : associatedNodes.map((node) => (
              <article key={node.id}>
                <div>
                  <span>{categoryLabels.get(node.category) ?? node.category}</span>
                  <i className={`authority-dot ${node.authority_state}`}>{node.authority_state.toUpperCase()}</i>
                </div>
                <h4>{node.title}</h4>
                <p>{node.domains.map((domain) => domainLabels.get(domain) ?? domain).join(' · ')}</p>
                <small>{node.source_kind === 'obsidian' ? node.source_path : 'Native Oscillink memory'}</small>
              </article>
            ))}
          </div>
          <footer>
            Associations belong to immutable memory revisions. Selection does not change authority.
          </footer>
        </aside>
        ) : null}
      </div>
    </section>
  )
}

function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

export default function MemoryWorkspace({
  latticeState,
  embeddedArchitecture = false,
  activeRetrievalRecordIds = [],
  mutationsEnabled = true,
}: MemoryWorkspaceProps) {
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
  const [creationRefreshError, setCreationRefreshError] = useState<string | null>(null)
  const [proposalRefreshKey, setProposalRefreshKey] = useState(0)
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
  const activeRetrievalRecords = new Set(activeRetrievalRecordIds)
  const activeRetrievalNodeIds = Array.from(new Set(
    nodes
      .filter((node) => activeRetrievalRecords.has(node.id))
      .flatMap((node) => node.architecture_node_ids),
  ))
  const categories = projection?.index.categories ?? []
  const domains = projection?.index.domains ?? []
  const availableCategories = useMemo(() => {
    const present = new Set(nodes.map((node) => node.category))
    return categories.filter((entry) => present.has(entry.category))
  }, [categories, nodes])
  const availableDomains = useMemo(() => {
    const present = new Set(nodes.flatMap((node) => node.domains))
    return domains.filter((entry) => present.has(entry.domain))
  }, [domains, nodes])
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

  const handleCreated = async () => {
    setCreationRefreshError(null)
    try {
      const refreshed = await loadMemoryProjection()
      setProjection(refreshed)
    } catch {
      setCreationRefreshError('The candidate was created, but the lattice could not refresh.')
    }
  }

  const handleSynchronized = async () => {
    const refreshed = await loadMemoryProjection()
    setProjection(refreshed)
  }

  if (embeddedArchitecture) {
    return (
      <ArchitectureMemoryPanel
        latticeState={latticeState}
        nodes={nodes}
        categories={categories}
        domains={domains}
        embedded
        activeRetrievalNodeIds={activeRetrievalNodeIds}
      />
    )
  }

  return (
    <section className="memory-view">
      <div className="channel-header memory-channel-header">
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

      <section className="memory-command-deck" aria-label="Memory workspace controls">
        {activeProjection === 'memory' ? (
          <>
            <MemoryCreatePanel enabled={mutationsEnabled} onCreated={handleCreated} />
            <SourceSyncPanel enabled={mutationsEnabled} onSynchronized={handleSynchronized} />
            <ArtifactImportPanel
              enabled={mutationsEnabled}
              targetRecordId={selectedId}
              targetTitle={detail?.title ?? null}
              onImported={() => setProposalRefreshKey((current) => current + 1)}
            />
          </>
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

        {activeProjection === 'memory' && nodes.length > 0 ? (
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
                {availableCategories.map((entry) => (
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
                {availableDomains.map((entry) => (
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
        ) : null}
      </section>

      {creationRefreshError !== null ? (
        <div className="memory-notice error" role="alert">{creationRefreshError}</div>
      ) : null}

      {activeProjection === 'memory' ? (
        <ProposalQueue
          enabled={mutationsEnabled}
          refreshKey={proposalRefreshKey}
          onReviewed={() => setProposalRefreshKey((current) => current + 1)}
        />
      ) : null}

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
        <div className="memory-layout">
          <section className="lattice-panel" aria-label="Memory visualization">
            <div className="memory-graph-header">
              <div className="graph-toolbar">
                <span><Network size={14} aria-hidden="true" /> PRODUCT MEMORY</span>
                <span>{`Exact links only · ${visibleNodes.length} of ${nodes.length} memory records`}</span>
              </div>
              {nodes.length > 0 ? (
                <ul className="memory-category-legend" aria-label="Memory category legend">
                  {availableCategories.map((entry) => (
                    <li
                      key={entry.category}
                      style={{ '--category-color': entry.color } as CSSProperties}
                    >
                      <span aria-hidden="true">{entry.symbol}</span>
                      <i>{entry.label}</i>
                    </li>
                  ))}
                </ul>
              ) : null}
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
              {projection !== null && visibleNodes.length === 0 ? (
                <div className="memory-graph-empty" role="status">
                  {state === 'unavailable'
                    ? 'Create or synchronize memory to populate this lattice.'
                    : 'No memory records match the current filters.'}
                </div>
              ) : null}
            </div>
          </section>
          <MemoryInspector
            node={detail}
            categories={categories}
            domains={domains}
            loading={detailLoading}
            error={detailError}
            reviewing={reviewing}
            reviewError={reviewError}
            reviewEnabled={mutationsEnabled}
            unavailable={state === 'unavailable'}
            onReview={handleReview}
          />
        </div>
      ) : (
        <ArchitectureMemoryPanel
          latticeState={latticeState}
          nodes={nodes}
          categories={categories}
          domains={domains}
          activeRetrievalNodeIds={activeRetrievalNodeIds}
        />
      )}
    </section>
  )
}
