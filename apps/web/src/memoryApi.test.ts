import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  createMemoryNode,
  loadMemoryNode,
  loadMemoryProjection,
  reviewMemoryNode,
} from './memoryApi'

const indexResponse = {
  schema_version: 1 as const,
  state: 'ready' as const,
  reason: null,
  index_hash: 'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
  node_count: 1,
  issue_count: 0,
  categories: [
    { category: 'project' as const, label: 'Projects', color: '#ff4fd8', symbol: 'P' },
  ],
  domains: [{ domain: 'ai_ml' as const, label: 'AI / ML' }],
  issues: [],
}

const collectionResponse = {
  schema_version: 1 as const,
  state: 'ready' as const,
  reason: null,
  index_hash: indexResponse.index_hash,
  count: 1,
  applied_filters: { category: null, domain: null },
  nodes: [
    {
      id: 'doc_A37PTXSESJE0P4NFJTD7E7RRAH',
      title: 'Oscillink Agent',
      source_path: '20 Projects/Oscillink Agent.md',
      source_status: 'active',
      category: 'project' as const,
      domains: ['ai_ml' as const],
      topics: [],
      content_hash: 'sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
      wikilink_count: 1,
    },
  ],
}

const detailResponse = {
  schema_version: 1 as const,
  state: 'ready' as const,
  node: {
    ...collectionResponse.nodes[0],
    frontmatter_type: 'project',
    wikilinks: ['30 Notes/Research/Agent Research'],
    classification_basis: ['frontmatter:type=project'],
  },
}

afterEach(() => vi.unstubAllGlobals())

describe('memory API client', () => {
  it('creates a bounded candidate memory through the authenticated API', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(detailResponse), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await createMemoryNode({
      title: 'Continuity decision',
      content: 'Use approved memory for customer-facing answers.',
      category: 'governance',
      domains: ['software'],
      topics: ['continuity', 'citations'],
      architecture_node_ids: ['decisions-lessons'],
    })

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/v1/memory/nodes')
    expect(init.method).toBe('POST')
    expect(init.headers).toEqual(expect.objectContaining({
      'Content-Type': 'application/json',
    }))
    expect(JSON.parse(String(init.body))).toEqual({
      schema_version: 1,
      title: 'Continuity decision',
      content: 'Use approved memory for customer-facing answers.',
      category: 'governance',
      domains: ['software'],
      topics: ['continuity', 'citations'],
      architecture_node_ids: ['decisions-lessons'],
    })
  })

  it('loads the index and node collection as one projection snapshot', async () => {
    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const path = String(input)
      const payload = path.endsWith('/index') ? indexResponse : collectionResponse
      return Promise.resolve(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    })
    vi.stubGlobal('fetch', fetchMock)

    const projection = await loadMemoryProjection()

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/memory/index', expect.any(Object))
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/memory/nodes', expect.any(Object))
    expect(projection.index.node_count).toBe(1)
    expect(projection.collection.nodes[0]?.title).toBe('Oscillink Agent')
  })

  it('retries the complete projection when index and nodes use different snapshots', async () => {
    const nextHash = 'sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc'
    const responses = [
      indexResponse,
      { ...collectionResponse, index_hash: nextHash },
      { ...indexResponse, index_hash: nextHash },
      { ...collectionResponse, index_hash: nextHash },
    ]
    const fetchMock = vi.fn().mockImplementation(() => {
      const payload = responses.shift()
      return Promise.resolve(new Response(JSON.stringify(payload), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }))
    })
    vi.stubGlobal('fetch', fetchMock)

    const projection = await loadMemoryProjection()

    expect(fetchMock).toHaveBeenCalledTimes(4)
    expect(projection.index.index_hash).toBe(nextHash)
    expect(projection.collection.index_hash).toBe(nextHash)
  })

  it('loads focused inspector metadata by encoded stable ID', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(detailResponse), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const detail = await loadMemoryNode('doc_A37PTXSESJE0P4NFJTD7E7RRAH')

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/memory/nodes/doc_A37PTXSESJE0P4NFJTD7E7RRAH',
      expect.any(Object),
    )
    expect(detail.node.classification_basis).toEqual(['frontmatter:type=project'])
  })

  it('submits a typed idempotent review decision', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(detailResponse), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await reviewMemoryNode('mem_A37PTXSESJE0P4NFJTD7E7RRAH', 'approved')

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    const body = JSON.parse(String(init.body)) as Record<string, unknown>
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      '/api/v1/memory/nodes/mem_A37PTXSESJE0P4NFJTD7E7RRAH/reviews',
    )
    expect(init.method).toBe('POST')
    expect(init.headers).toEqual(expect.objectContaining({
      'Content-Type': 'application/json',
      'Idempotency-Key': expect.stringMatching(/^memory-review-evt_[0-9A-HJKMNP-TV-Z]{26}$/),
    }))
    expect(body).toEqual({
      schema_version: 1,
      request_id: expect.stringMatching(/^evt_[0-9A-HJKMNP-TV-Z]{26}$/),
      decision: 'approved',
    })
  })
})
