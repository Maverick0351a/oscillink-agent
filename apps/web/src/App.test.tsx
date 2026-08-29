import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from './App'

const statusResponse = {
  service: 'oscillink-agent',
  version: '0.1.0',
  api_state: 'online',
  storage: {
    ledger: { state: 'ready', record_count: 12 },
    artifacts: { state: 'ready', record_count: 4 },
  },
  features: {
    chat: 'planned',
    memory_lattice: 'planned',
    appearance: 'preview',
  },
}

const memoryNode = {
  id: 'doc_A37PTXSESJE0P4NFJTD7E7RRAH',
  title: 'Oscillink Agent',
  source_path: '20 Projects/Oscillink Agent.md',
  source_status: 'active',
  category: 'project',
  domains: ['ai_ml'],
  topics: [],
  content_hash: 'sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
  wikilink_count: 0,
}

function appFetch(input: RequestInfo | URL) {
  const path = String(input)
  let payload: unknown = statusResponse
  if (path.endsWith('/memory/index')) {
    payload = {
      schema_version: 1,
      state: 'ready',
      reason: null,
      index_hash: 'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      node_count: 1,
      issue_count: 0,
      categories: [{ category: 'project', label: 'Projects', color: '#ff4fd8', symbol: 'P' }],
      domains: [{ domain: 'ai_ml', label: 'AI / ML' }],
      issues: [],
    }
  } else if (path.endsWith('/memory/nodes')) {
    payload = {
      schema_version: 1,
      state: 'ready',
      reason: null,
      index_hash: 'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      count: 1,
      applied_filters: { category: null, domain: null },
      nodes: [memoryNode],
    }
  } else if (path.includes('/memory/nodes/')) {
    payload = {
      schema_version: 1,
      state: 'ready',
      node: {
        ...memoryNode,
        frontmatter_type: 'project',
        wikilinks: [],
        classification_basis: ['frontmatter:type=project'],
      },
    }
  }
  return Promise.resolve(
    new Response(JSON.stringify(payload), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('Oscillink Agent shell', () => {
  it('renders live backend and storage status', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(statusResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )

    render(<App />)

    expect(screen.getByRole('img', { name: 'Oscillink logo' })).toHaveAttribute(
      'src',
      '/oscillink-logo.png',
    )
    expect(screen.getByRole('heading', { name: 'Oscillink Agent' })).toBeInTheDocument()
    expect(await screen.findByText('API ONLINE')).toBeInTheDocument()
    expect(screen.getByText('12 events')).toBeInTheDocument()
    expect(screen.getByText('4 artifacts')).toBeInTheDocument()
  })

  it('opens the real reviewed-memory projection and preserves the architecture view', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(appFetch))
    render(<App />)
    await screen.findByText('API ONLINE')

    fireEvent.click(screen.getByRole('button', { name: 'Memory Lattice' }))

    expect(screen.getByRole('heading', { name: 'Memory Lattice' })).toBeInTheDocument()
    expect(await screen.findByText('READY · 1 REVIEWED')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Reviewed memory lattice' })).toBeInTheDocument()
    expect(
      await screen.findByRole('heading', { name: 'Oscillink Agent', level: 3 }),
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'System Architecture' }))
    expect(screen.getByText('FOUNDATION MAP · NOT MEMORY DATA')).toBeInTheDocument()
  })

  it('shows the foundation agent while keeping unavailable chat disabled', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(statusResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )
    render(<App />)
    await screen.findByText('API ONLINE')

    expect(
      screen.getByRole('img', { name: 'Oscillink Agent avatar, foundation idle' }),
    ).toBeInTheDocument()
    expect(screen.getByText('MODEL RUNTIME PENDING')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Message Oscillink Agent' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Send message' })).toBeDisabled()
  })

  it('reports an offline API instead of remaining in a connecting state', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('connection refused')))

    render(<App />)

    expect(await screen.findByText('API OFFLINE')).toBeInTheDocument()
    expect(screen.queryByText('CONNECTING')).not.toBeInTheDocument()
  })
})
