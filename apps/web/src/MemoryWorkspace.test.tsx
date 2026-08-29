import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import MemoryWorkspace from './MemoryWorkspace'

const indexResponse = {
  schema_version: 1,
  state: 'ready',
  reason: null,
  index_hash: 'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
  node_count: 2,
  issue_count: 0,
  categories: [
    { category: 'project', label: 'Projects', color: '#ff4fd8', symbol: 'P' },
    { category: 'research', label: 'Research', color: '#36f1cd', symbol: 'R' },
  ],
  domains: [
    { domain: 'ai_ml', label: 'AI / ML' },
    { domain: 'engineering', label: 'Engineering' },
  ],
  issues: [],
}

const nodes = [
  {
    id: 'mem_A37PTXSESJE0P4NFJTD7E7RRAH',
    title: 'Oscillink Agent',
    source_path: '20 Projects/Oscillink Agent.md',
    source_status: 'active',
    authority_state: 'approved',
    source_kind: 'obsidian',
    category: 'project',
    domains: ['ai_ml'],
    topics: [],
    content_hash: 'sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
    wikilink_count: 1,
  },
  {
    id: 'mem_PHBCG4C4DKQWX1903XXPVD7ZB6',
    title: 'Agent Architecture Research',
    source_path: null,
    source_status: null,
    authority_state: 'candidate',
    source_kind: 'native',
    category: 'research',
    domains: ['ai_ml', 'engineering'],
    topics: ['agent architecture'],
    content_hash: 'sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc',
    wikilink_count: 1,
  },
]

const collectionResponse = {
  schema_version: 1,
  state: 'ready',
  reason: null,
  index_hash: indexResponse.index_hash,
  count: 2,
  applied_filters: { category: null, domain: null },
  nodes,
}

function detailResponse(index: number) {
  const node = nodes[index]
  if (node === undefined) throw new Error('unknown fixture node')
  return {
    schema_version: 1,
    state: 'ready',
    node: {
      ...node,
      frontmatter_type: node.category,
      wikilinks: index === 0 ? ['30 Notes/Research/Agent Research'] : ['20 Projects/Oscillink Agent'],
      classification_basis: [`frontmatter:type=${node.category}`],
    },
  }
}

function stubReadyMemory() {
  const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const path = String(input)
    let payload: unknown
    if (path.endsWith('/index')) payload = indexResponse
    else if (path.endsWith('/nodes')) payload = collectionResponse
    else if (path.endsWith(nodes[0]?.id ?? 'missing')) payload = detailResponse(0)
    else if (path.endsWith(nodes[1]?.id ?? 'missing')) payload = detailResponse(1)
    else return Promise.resolve(new Response(null, { status: 404 }))
    return Promise.resolve(
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function stubUnavailableMemory() {
  const unavailableIndex = {
    ...indexResponse,
    state: 'unavailable',
    reason: 'vault_not_configured',
    index_hash: null,
    node_count: 0,
  }
  const unavailableCollection = {
    ...collectionResponse,
    state: 'unavailable',
    reason: 'vault_not_configured',
    index_hash: null,
    count: 0,
    nodes: [],
  }
  const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const payload = String(input).endsWith('/index') ? unavailableIndex : unavailableCollection
    return Promise.resolve(
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('MemoryWorkspace', () => {
  it('loads reviewed nodes and resolves focused inspector detail by stable ID', async () => {
    const fetchMock = stubReadyMemory()

    render(<MemoryWorkspace latticeState="ready" />)

    expect(await screen.findByText('READY · 2 MEMORY RECORDS')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Product memory lattice' })).toBeInTheDocument()
    const legend = screen.getByRole('list', { name: 'Memory category legend' })
    expect(within(legend).getByText('Projects')).toBeInTheDocument()
    expect(within(legend).getByText('Research')).toBeInTheDocument()
    expect(within(legend).getByText('P')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Oscillink Agent' })).toBeInTheDocument()
    expect(screen.getByText('APPROVED RECORD')).toBeInTheDocument()
    expect(screen.getByText('OBSIDIAN SOURCE')).toBeInTheDocument()
    expect(screen.getByText('20 Projects/Oscillink Agent.md')).toBeInTheDocument()
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/v1/memory/nodes/mem_A37PTXSESJE0P4NFJTD7E7RRAH',
        expect.any(Object),
      )
    })
  })

  it('combines search, category, and domain filters without retaining hidden focus', async () => {
    stubReadyMemory()
    render(<MemoryWorkspace latticeState="ready" />)
    await screen.findByText('READY · 2 MEMORY RECORDS')
    await screen.findByRole('heading', { name: 'Oscillink Agent' })

    fireEvent.change(screen.getByRole('combobox', { name: 'Filter by category' }), {
      target: { value: 'research' },
    })
    fireEvent.change(screen.getByRole('combobox', { name: 'Filter by domain' }), {
      target: { value: 'engineering' },
    })

    expect(screen.getByText(/1 of 2 memory records/)).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Agent Architecture Research' })).toBeInTheDocument()

    fireEvent.change(screen.getByRole('searchbox', { name: 'Search product memory' }), {
      target: { value: 'Oscillink' },
    })

    expect(screen.getByText('No memory records match the current filters.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'No memory selected' })).toBeInTheDocument()
  })

  it('surfaces unavailable memory and keeps System Architecture as a separate honest view', async () => {
    const fetchMock = stubUnavailableMemory()
    render(<MemoryWorkspace latticeState="preview" />)

    expect(await screen.findByText('MEMORY UNAVAILABLE')).toBeInTheDocument()
    expect(screen.getByText(/no product-owned memory repository is initialized/i)).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Product memory lattice' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'System Architecture' }))

    expect(
      screen.getByRole('img', { name: 'Foundation memory architecture map' }),
    ).toBeInTheDocument()
    expect(screen.getByText('FOUNDATION MAP · NOT MEMORY DATA')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
