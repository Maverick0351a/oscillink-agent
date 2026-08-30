import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import persistedContextManifest from './fixtures/persistedContextManifest.json'
import { setWorkspaceCredential } from './workspaceAuth'

const statusResponse = {
  service: 'oscillink-agent',
  version: '0.1.0',
  api_state: 'online',
  workspace_auth: { state: 'ready' },
  storage: {
    ledger: { state: 'ready', record_count: 12 },
    artifacts: { state: 'ready', record_count: 4 },
    memory: { state: 'ready', record_count: 1 },
  },
  features: {
    chat: 'ready',
    capability_broker: 'preview',
    memory_lattice: 'ready',
    appearance: 'preview',
    workspace_terminal: 'preview',
  },
}

const memoryNode = {
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
  wikilink_count: 0,
  architecture_node_ids: ['projects-work'],
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
  } else if (path.includes('/chat/sessions/')) {
    payload = {
      schema_version: 1,
      session_id: 'ses_01ARZ3NDEKTSV4RRFFQ69G5FC1',
      run_id: 'run_01ARZ3NDEKTSV4RRFFQ69G5FC1',
      events: [
        {
          id: 'evt_01ARZ3NDEKTSV4RRFFQ69G5FC1',
          event_type: 'message',
          observed_at: '2026-08-29T00:00:00Z',
          actor: { id: 'human_local-user', type: 'human' },
          artifact_refs: [],
          causal_parent_ids: [],
          payload: { message: 'What should this agent remember?' },
        },
        {
          id: 'evt_01ARZ3NDEKTSV4RRFFQ69G5FC2',
          event_type: 'model_call',
          observed_at: '2026-08-29T00:00:01Z',
          actor: { id: 'system_chat-runtime', type: 'system' },
          artifact_refs: ['sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd'],
          causal_parent_ids: ['evt_01ARZ3NDEKTSV4RRFFQ69G5FC1'],
          payload: { provider_model: 'deterministic-v1' },
        },
        {
          id: 'evt_01ARZ3NDEKTSV4RRFFQ69G5FC3',
          event_type: 'message',
          observed_at: '2026-08-29T00:00:02Z',
          actor: { id: 'model_deterministic-v1', type: 'model' },
          artifact_refs: [],
          causal_parent_ids: ['evt_01ARZ3NDEKTSV4RRFFQ69G5FC2'],
          payload: { answer: 'Grounded in approved memory: Oscillink Agent.' },
        },
      ],
      context_manifest: persistedContextManifest,
    }
  } else if (path.endsWith('/chat/messages')) {
    payload = {
      schema_version: 1,
      session_id: 'ses_01ARZ3NDEKTSV4RRFFQ69G5FC1',
      run_id: 'run_01ARZ3NDEKTSV4RRFFQ69G5FC1',
      task_id: 'tsk_01ARZ3NDEKTSV4RRFFQ69G5FC1',
      provider: { kind: 'fake', model: 'deterministic-v1' },
      answer: 'Grounded in approved memory: Oscillink Agent.',
      citations: [{
        record_id: memoryNode.id,
        content_hash: memoryNode.content_hash,
        title: memoryNode.title,
      }],
      context_manifest: persistedContextManifest,
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
  setWorkspaceCredential(null)
  vi.unstubAllGlobals()
})

describe('Oscillink Agent shell', () => {
  it('renders live backend and storage status', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(appFetch))

    render(<App />)

    expect(screen.getByRole('img', { name: 'Oscillink logo' })).toHaveAttribute(
      'src',
      '/oscillink-logo.png',
    )
    expect(screen.getByRole('heading', { name: 'Oscillink Agent' })).toBeInTheDocument()
    expect(await screen.findByText('API ONLINE')).toBeInTheDocument()
    expect(screen.getByText('12 events')).toBeInTheDocument()
    expect(screen.getByText('4 artifacts')).toBeInTheDocument()
    expect(screen.getByText('Memory READY')).toBeInTheDocument()
    expect(screen.getByText('AUTH READY')).toBeInTheDocument()
  })

  it('keeps mutating controls locked when workspace authentication is locked', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((input: RequestInfo | URL) => {
      if (String(input).endsWith('/api/v1/status')) {
        return Promise.resolve(new Response(JSON.stringify({
          ...statusResponse,
          workspace_auth: { state: 'locked' },
        }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      return appFetch(input)
    }))

    render(<App />)

    expect(await screen.findByText('AUTH LOCKED')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Send message' })).toBeDisabled()
    expect(screen.getByText('WORKSPACE AUTHENTICATION REQUIRED')).toBeInTheDocument()
  })

  it('unlocks the local workspace with an in-memory credential', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(
      (input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input).endsWith('/api/v1/status')) {
          const headers = new Headers(init?.headers)
          const state = headers.get('Authorization') === 'Bearer browser-credential'
            ? 'ready'
            : 'locked'
          return Promise.resolve(new Response(JSON.stringify({
            ...statusResponse,
            workspace_auth: { state },
          }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
        }
        return appFetch(input)
      },
    ))

    render(<App />)
    expect(await screen.findByText('AUTH LOCKED')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Local workspace credential'), {
      target: { value: 'browser-credential' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Unlock workspace' }))

    expect(await screen.findByText('AUTH READY')).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledWith('/api/v1/status', expect.objectContaining({
      headers: { Authorization: 'Bearer browser-credential' },
    }))
  })

  it('keeps chat, architecture memory, and node details in one workspace', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(appFetch))
    render(<App />)
    await screen.findByText('API ONLINE')

    expect(screen.getByRole('region', { name: 'Agent chat' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'System Architecture' })).toBeInTheDocument()
    expect(await screen.findByRole('img', { name: 'System architecture memory map' })).toBeInTheDocument()
    expect(screen.getByText('ARCHITECTURE MEMORY · 1 ASSOCIATION')).toBeInTheDocument()
    expect(screen.getByText('NO ACTIVE RETRIEVAL')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', {
      name: 'Inspect Projects & Work, 1 associated memory record',
    }))
    const inspector = screen.getByRole('complementary', { name: 'Architecture memory inspector' })
    expect(within(inspector).getByRole('heading', { name: 'Projects & Work' })).toBeInTheDocument()
    expect(within(inspector).getByRole('heading', { name: 'Oscillink Agent' })).toBeInTheDocument()
  })

  it('opens the governed Product Memory workspace from the integrated app', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(appFetch))
    render(<App />)
    await screen.findByText('API ONLINE')

    fireEvent.click(screen.getByRole('button', { name: 'Open Product Memory' }))

    expect(await screen.findByRole('region', { name: 'Memory workspace controls' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Product Memory' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(await screen.findByRole('heading', { name: 'Oscillink Agent' })).toBeInTheDocument()
  })

  it('runs governed chat and renders cited memory with inspectable run metadata', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(appFetch))
    render(<App />)
    await screen.findByText('API ONLINE')

    const presence = screen.getByRole('region', { name: 'Agent chat' })
    expect(
      within(presence).getByRole('img', { name: 'Oscillink Agent avatar, foundation idle' }),
    ).toBeInTheDocument()
    expect(screen.getByText('DETERMINISTIC RUNTIME')).toBeInTheDocument()
    const composer = screen.getByRole('textbox', { name: 'Message Oscillink Agent' })
    fireEvent.change(composer, { target: { value: 'What should this agent remember?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }))

    expect(await screen.findByText('Grounded in approved memory: Oscillink Agent.')).toBeInTheDocument()
    expect(screen.getByText('CITED MEMORY · Oscillink Agent')).toBeInTheDocument()
    expect(screen.getByText('RUN 01ARZ3NDEKTSV4RRFFQ69G5FC1')).toBeInTheDocument()
    expect(screen.getByText('CONTEXT 01ARZ3NDEKTSV4RRFFQ69G5FC1')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Inspect persisted run' }))
    const runInspector = await screen.findByRole('complementary', { name: 'Run inspector' })
    expect(within(runInspector).getByText('3 PERSISTED EVENTS')).toBeInTheDocument()
    expect(within(runInspector).getByText('MODEL CALL')).toBeInTheDocument()
    expect(within(runInspector).getByText('Oscillink Agent')).toBeInTheDocument()
    expect(within(runInspector).getByText('RANK 1 · SCORE 4')).toBeInTheDocument()
    expect(
      within(runInspector).getByText('PROJECT · AI ML · HUMAN VERIFIED'),
    ).toBeInTheDocument()
    expect(within(runInspector).queryByText(/undefined/i)).not.toBeInTheDocument()
    expect(within(runInspector).getByText('0 UNAPPROVED EXCLUDED')).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/chat/sessions/ses_01ARZ3NDEKTSV4RRFFQ69G5FC1/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FC1',
      { headers: {} },
    )
  })

  it('opens a truthful governed terminal pane inside chat without execution authority', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(appFetch))
    render(<App />)
    await screen.findByText('API ONLINE')

    expect(screen.queryByRole('button', { name: 'Workspace Terminal' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Workspace Terminal' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Open terminal pane' }))

    expect(screen.getByRole('heading', { name: 'Workspace Terminal' })).toBeInTheDocument()
    expect(screen.getByText('PREVIEW · EXECUTION LOCKED')).toBeInTheDocument()
    expect(screen.getByText('No process created')).toBeInTheDocument()
    expect(screen.getByText('Sandbox policy pending')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Workspace command' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Run command' })).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: 'Close terminal pane' }))
    expect(screen.queryByRole('heading', { name: 'Workspace Terminal' })).not.toBeInTheDocument()
  })

  it('reports an offline API instead of remaining in a connecting state', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('connection refused')))

    render(<App />)

    expect(await screen.findByText('API OFFLINE')).toBeInTheDocument()
    expect(screen.queryByText('CONNECTING')).not.toBeInTheDocument()
  })
})
