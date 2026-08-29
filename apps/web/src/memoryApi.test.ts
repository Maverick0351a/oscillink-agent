import { afterEach, describe, expect, it, vi } from 'vitest'

import { loadMemoryNode, loadMemoryProjection } from './memoryApi'

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
})
