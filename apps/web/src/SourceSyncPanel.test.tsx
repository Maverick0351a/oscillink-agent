import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import SourceSyncPanel from './SourceSyncPanel'

const configuredSource = {
  schema_version: 1,
  source_kind: 'obsidian',
  state: 'configured',
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('SourceSyncPanel', () => {
  it('loads opaque status without synchronizing and stays locked without workspace authority', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(configuredSource), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    render(<SourceSyncPanel enabled={false} onSynchronized={vi.fn()} />)

    expect(await screen.findByText('OBSIDIAN · CONFIGURED')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Synchronize source' })).toBeDisabled()
    expect(screen.getByText('Unlock the local workspace to synchronize.')).toBeInTheDocument()
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/memory/sources/obsidian',
      expect.any(Object),
    )
  })

  it('requires confirmation and reports typed synchronization accounting', async () => {
    const synchronized = {
      schema_version: 1,
      state: 'synced',
      source_kind: 'obsidian',
      created: 2,
      revised: 1,
      unchanged: 3,
      missing: 1,
      issues: 1,
    }
    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const payload = init?.method === 'POST' ? synchronized : configuredSource
      return Promise.resolve(new Response(JSON.stringify(payload), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }))
    })
    const onSynchronized = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    render(<SourceSyncPanel enabled onSynchronized={onSynchronized} />)
    await screen.findByText('OBSIDIAN · CONFIGURED')

    fireEvent.click(screen.getByRole('button', { name: 'Synchronize source' }))

    expect(screen.getByText('Synchronize the configured source now?')).toBeInTheDocument()
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(0)

    fireEvent.click(screen.getByRole('button', { name: 'Confirm synchronization' }))

    expect(await screen.findByText('SOURCE SYNCHRONIZED')).toBeInTheDocument()
    expect(screen.getByText('2 created · 1 revised · 3 unchanged · 1 missing · 1 issue')).toBeInTheDocument()
    await waitFor(() => expect(onSynchronized).toHaveBeenCalledWith(synchronized))
  })

  it('reports synchronization success separately from a failed lattice refresh', async () => {
    const synchronized = {
      schema_version: 1,
      state: 'synced',
      source_kind: 'obsidian',
      created: 0,
      revised: 1,
      unchanged: 0,
      missing: 0,
      issues: 0,
    }
    vi.stubGlobal('fetch', vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const payload = init?.method === 'POST' ? synchronized : configuredSource
      return Promise.resolve(new Response(JSON.stringify(payload), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }))
    }))
    render(<SourceSyncPanel enabled onSynchronized={vi.fn().mockRejectedValue(new Error('offline'))} />)
    await screen.findByText('OBSIDIAN · CONFIGURED')

    fireEvent.click(screen.getByRole('button', { name: 'Synchronize source' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm synchronization' }))

    expect(await screen.findByText('SOURCE SYNCHRONIZED')).toBeInTheDocument()
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The source was synchronized, but the lattice could not refresh.',
    )
    expect(screen.queryByText('Source synchronization failed. No success was recorded.')).not.toBeInTheDocument()
  })
})
