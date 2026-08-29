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
    { category: 'tooling', label: 'Tooling', color: '#8a7dff', symbol: 'T' },
  ],
  domains: [
    { domain: 'ai_ml', label: 'AI / ML' },
    { domain: 'engineering', label: 'Engineering' },
    { domain: 'science', label: 'Science' },
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
    architecture_node_ids: ['projects-work', 'decisions-lessons'],
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
    architecture_node_ids: ['knowledge-research'],
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

function stubReadyMemory(
  reviewStatus = 200,
  reviewGate?: Promise<void>,
  refreshStatus = 200,
) {
  let candidateAuthority = 'candidate'
  let indexRequests = 0
  const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    let payload: unknown
    if (path.endsWith('/index')) {
      indexRequests += 1
      if (indexRequests > 1 && refreshStatus !== 200) {
        return Promise.resolve(new Response(null, { status: refreshStatus }))
      }
      payload = indexResponse
    }
    else if (path.endsWith('/nodes') && init?.method === 'POST') {
      return Promise.resolve(new Response(JSON.stringify(detailResponse(1)), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      }))
    }
    else if (path.endsWith('/nodes')) {
      payload = {
        ...collectionResponse,
        nodes: nodes.map((node, index) => (
          index === 1 ? { ...node, authority_state: candidateAuthority } : node
        )),
      }
    }
    else if (path.endsWith(`${nodes[1]?.id ?? 'missing'}/reviews`) && init?.method === 'POST') {
      if (reviewStatus !== 200) {
        return Promise.resolve(new Response(null, { status: reviewStatus }))
      }
      const requestBody = typeof init.body === 'string'
        ? JSON.parse(init.body) as { decision: string }
        : { decision: 'approved' }
      if (reviewGate !== undefined) {
        return reviewGate.then(() => {
          candidateAuthority = requestBody.decision
          return new Response(JSON.stringify({
            ...detailResponse(1),
            node: { ...detailResponse(1).node, authority_state: candidateAuthority },
          }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          })
        })
      }
      candidateAuthority = requestBody.decision
      payload = {
        ...detailResponse(1),
        node: { ...detailResponse(1).node, authority_state: candidateAuthority },
      }
    }
    else if (path.endsWith(nodes[0]?.id ?? 'missing')) payload = detailResponse(0)
    else if (path.endsWith(nodes[1]?.id ?? 'missing')) {
      payload = {
        ...detailResponse(1),
        node: { ...detailResponse(1).node, authority_state: candidateAuthority },
      }
    }
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
    const controls = screen.getByRole('region', { name: 'Memory workspace controls' })
    expect(within(controls).getByRole('button', { name: 'Product Memory' })).toBeInTheDocument()
    expect(within(controls).getByRole('searchbox', { name: 'Search product memory' })).toBeInTheDocument()
    const visualization = screen.getByRole('region', { name: 'Memory visualization' })
    expect(screen.getByRole('img', { name: 'Product memory lattice' })).toBeInTheDocument()
    const legend = within(visualization).getByRole('list', { name: 'Memory category legend' })
    expect(within(legend).getByText('Projects')).toBeInTheDocument()
    expect(within(legend).getByText('Research')).toBeInTheDocument()
    expect(within(legend).getByText('P')).toBeInTheDocument()
    expect(within(legend).queryByText('Tooling')).not.toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'T · Tooling' })).not.toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'Science' })).not.toBeInTheDocument()
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

  it('opens architecture nodes as memory containers with explicit associated records', async () => {
    stubReadyMemory()
    render(<MemoryWorkspace latticeState="ready" />)
    expect(await screen.findByText('READY · 2 MEMORY RECORDS')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'System Architecture' }))

    expect(screen.getByRole('img', { name: 'System architecture memory map' })).toBeInTheDocument()
    expect(screen.getByText('ARCHITECTURE MEMORY · 3 ASSOCIATIONS')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', {
      name: 'Inspect Decisions & Lessons, 1 associated memory record',
    }))

    const inspector = screen.getByRole('complementary', { name: 'Architecture memory inspector' })
    expect(within(inspector).getByRole('heading', { name: 'Decisions & Lessons' })).toBeInTheDocument()
    expect(within(inspector).getByRole('heading', { name: 'Oscillink Agent' })).toBeInTheDocument()
    expect(within(inspector).getByText('APPROVED')).toBeInTheDocument()
    expect(within(inspector).getByText('1 associated record')).toBeInTheDocument()
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

  it('lets a human approve a candidate and reflects the governed result', async () => {
    const fetchMock = stubReadyMemory()
    render(<MemoryWorkspace latticeState="ready" />)
    await screen.findByRole('heading', { name: 'Oscillink Agent' })

    fireEvent.change(screen.getByRole('combobox', { name: 'Filter by category' }), {
      target: { value: 'research' },
    })
    expect(
      await screen.findByRole('heading', { name: 'Agent Architecture Research' }),
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Approve memory' }))

    expect(await screen.findByText('APPROVED RECORD')).toBeInTheDocument()
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/v1/memory/nodes/mem_PHBCG4C4DKQWX1903XXPVD7ZB6/reviews',
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
        }),
      )
    })
    expect(screen.queryByRole('button', { name: 'Approve memory' })).not.toBeInTheDocument()
  })

  it('keeps review controls disabled while workspace authentication is locked', async () => {
    const fetchMock = stubReadyMemory()
    render(<MemoryWorkspace latticeState="ready" mutationsEnabled={false} />)
    await screen.findByRole('heading', { name: 'Oscillink Agent' })

    fireEvent.change(screen.getByRole('combobox', { name: 'Filter by category' }), {
      target: { value: 'research' },
    })
    await screen.findByRole('heading', { name: 'Agent Architecture Research' })

    expect(screen.getByRole('button', { name: 'Approve memory' })).toBeDisabled()
    expect(screen.getByText('Unlock the local workspace to record a review.')).toBeInTheDocument()
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(0)
  })

  it('reports candidate creation separately from a failed lattice refresh', async () => {
    stubReadyMemory(200, undefined, 503)
    render(<MemoryWorkspace latticeState="ready" mutationsEnabled />)
    await screen.findByRole('heading', { name: 'Oscillink Agent' })

    fireEvent.change(screen.getByLabelText('Memory title'), {
      target: { value: 'New governed decision' },
    })
    fireEvent.change(screen.getByLabelText('Memory content'), {
      target: { value: 'Keep candidate authority until human review.' },
    })
    fireEvent.click(screen.getByRole('checkbox', { name: 'Software' }))
    fireEvent.click(screen.getByRole('button', { name: 'Create candidate memory' }))

    expect(await screen.findByText('CANDIDATE CREATED')).toBeInTheDocument()
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The candidate was created, but the lattice could not refresh.',
    )
  })

  it('lets a human reject a candidate and reflects the terminal authority state', async () => {
    stubReadyMemory()
    render(<MemoryWorkspace latticeState="ready" />)
    await screen.findByRole('heading', { name: 'Oscillink Agent' })

    fireEvent.change(screen.getByRole('combobox', { name: 'Filter by category' }), {
      target: { value: 'research' },
    })
    await screen.findByRole('heading', { name: 'Agent Architecture Research' })

    fireEvent.click(screen.getByRole('button', { name: 'Reject memory' }))

    expect(await screen.findByText('REJECTED RECORD')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Reject memory' })).not.toBeInTheDocument()
  })

  it('keeps authority unchanged and explains a failed review request', async () => {
    stubReadyMemory(409)
    render(<MemoryWorkspace latticeState="ready" />)
    await screen.findByRole('heading', { name: 'Oscillink Agent' })

    fireEvent.change(screen.getByRole('combobox', { name: 'Filter by category' }), {
      target: { value: 'research' },
    })
    await screen.findByRole('heading', { name: 'Agent Architecture Research' })

    fireEvent.click(screen.getByRole('button', { name: 'Approve memory' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The review decision was not recorded. The displayed authority is unchanged.',
    )
    expect(screen.getByText('CANDIDATE RECORD')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Approve memory' })).toBeEnabled()
  })

  it('distinguishes a recorded decision from a failed lattice refresh', async () => {
    stubReadyMemory(200, undefined, 503)
    render(<MemoryWorkspace latticeState="ready" />)
    await screen.findByRole('heading', { name: 'Oscillink Agent' })

    fireEvent.change(screen.getByRole('combobox', { name: 'Filter by category' }), {
      target: { value: 'research' },
    })
    await screen.findByRole('heading', { name: 'Agent Architecture Research' })
    fireEvent.click(screen.getByRole('button', { name: 'Approve memory' }))

    expect(await screen.findByText('APPROVED RECORD')).toBeInTheDocument()
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The review decision was recorded, but the lattice could not refresh.',
    )
  })

  it('does not replace the current inspector when an earlier review finishes', async () => {
    let releaseReview: () => void = () => {}
    const reviewGate = new Promise<void>((resolve) => { releaseReview = resolve })
    const fetchMock = stubReadyMemory(200, reviewGate)
    render(<MemoryWorkspace latticeState="ready" />)
    await screen.findByRole('heading', { name: 'Oscillink Agent' })

    fireEvent.change(screen.getByRole('combobox', { name: 'Filter by category' }), {
      target: { value: 'research' },
    })
    await screen.findByRole('heading', { name: 'Agent Architecture Research' })
    fireEvent.click(screen.getByRole('button', { name: 'Approve memory' }))

    fireEvent.change(screen.getByRole('combobox', { name: 'Filter by category' }), {
      target: { value: 'project' },
    })
    await screen.findByRole('heading', { name: 'Oscillink Agent' })
    releaseReview()

    await waitFor(() => {
      const nodeCollectionCalls = fetchMock.mock.calls.filter(
        ([input]) => String(input).endsWith('/nodes'),
      )
      expect(nodeCollectionCalls).toHaveLength(2)
    })
    expect(screen.getByRole('heading', { name: 'Oscillink Agent' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Agent Architecture Research' })).not.toBeInTheDocument()
  })

  it('surfaces unavailable memory while keeping empty architecture containers truthful', async () => {
    const fetchMock = stubUnavailableMemory()
    render(<MemoryWorkspace latticeState="preview" />)

    expect(await screen.findByText('MEMORY UNAVAILABLE')).toBeInTheDocument()
    expect(screen.getByText(/no product-owned memory repository is initialized/i)).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Product memory lattice' })).toBeInTheDocument()
    expect(screen.getByText('Create or synchronize memory to populate this lattice.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'No memory available' })).toBeInTheDocument()
    expect(screen.queryByRole('searchbox', { name: 'Search product memory' })).not.toBeInTheDocument()
    expect(screen.queryByRole('list', { name: 'Memory category legend' })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'System Architecture' }))

    expect(
      screen.getByRole('img', { name: 'System architecture memory map' }),
    ).toBeInTheDocument()
    expect(screen.getByText('ARCHITECTURE MEMORY · 0 ASSOCIATIONS')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
