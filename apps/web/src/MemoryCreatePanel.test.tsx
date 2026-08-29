import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import MemoryCreatePanel from './MemoryCreatePanel'

const createdResponse = {
  schema_version: 1,
  state: 'ready',
  node: {
    id: 'mem_A37PTXSESJE0P4NFJTD7E7RRAH',
    title: 'Continuity decision',
    source_path: null,
    source_status: null,
    authority_state: 'candidate',
    source_kind: 'native',
    category: 'governance',
    domains: ['software'],
    topics: ['continuity'],
    content_hash: `sha256:${'b'.repeat(64)}`,
    wikilink_count: 0,
    architecture_node_ids: ['decisions-lessons'],
    frontmatter_type: 'native',
    wikilinks: [],
    classification_basis: ['human-authored native memory'],
  },
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('MemoryCreatePanel', () => {
  it('keeps creation unavailable while workspace auth is locked', () => {
    render(<MemoryCreatePanel enabled={false} onCreated={vi.fn()} />)

    expect(screen.getByRole('button', { name: 'Create candidate memory' })).toBeDisabled()
    expect(screen.getByText('Unlock the local workspace to create memory.')).toBeInTheDocument()
  })

  it('creates an explicit candidate and reports the authority state', async () => {
    const onCreated = vi.fn()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify(createdResponse), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      }),
    ))
    render(<MemoryCreatePanel enabled onCreated={onCreated} />)

    fireEvent.change(screen.getByLabelText('Memory title'), {
      target: { value: 'Continuity decision' },
    })
    fireEvent.change(screen.getByLabelText('Memory content'), {
      target: { value: 'Use approved memory for customer-facing answers.' },
    })
    fireEvent.change(screen.getByLabelText('Memory category'), {
      target: { value: 'governance' },
    })
    fireEvent.click(screen.getByRole('checkbox', { name: 'Software' }))
    fireEvent.change(screen.getByLabelText('Memory topics'), {
      target: { value: 'continuity' },
    })
    fireEvent.click(screen.getByRole('checkbox', { name: 'Decisions & lessons' }))
    fireEvent.click(screen.getByRole('button', { name: 'Create candidate memory' }))

    expect(await screen.findByText('CANDIDATE CREATED')).toBeInTheDocument()
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(createdResponse.node))
  })
})
