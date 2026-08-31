import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import WorkspaceOperations from './WorkspaceOperations'

const exportResponse = {
  schema_version: 1,
  export_id: 'exp_01J00000000000000000000060',
  manifest: {
    schema_version: 1,
    store_versions: {
      events: 1,
      memory: 1,
      capabilities: 1,
      proposals: 1,
    },
    entries: [
      {
        path: 'databases/events.sqlite3',
        kind: 'database',
        byte_count: 4096,
        content_hash: `sha256:${'a'.repeat(64)}`,
      },
      {
        path: 'databases/memory.sqlite3',
        kind: 'database',
        byte_count: 8192,
        content_hash: `sha256:${'b'.repeat(64)}`,
      },
    ],
  },
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('WorkspaceOperations', () => {
  it('does not inspect or mutate exports while workspace auth is locked', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    render(<WorkspaceOperations enabled={false} />)

    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Create verified export' })).toBeDisabled()
    expect(screen.getByText('Unlock the local workspace to manage verified exports.')).toBeInTheDocument()
  })

  it('creates a verified manifest and requires exact restore confirmation', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({
        schema_version: 1,
        state: 'unavailable',
        reason: 'export_missing',
        export: null,
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exportResponse), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ...exportResponse,
        state: 'restored',
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)

    render(<WorkspaceOperations enabled />)

    expect(await screen.findByText('NO VERIFIED EXPORT')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Create verified export' }))

    expect(await screen.findByText(exportResponse.export_id)).toBeInTheDocument()
    expect(screen.getByText('2 ENTRIES · 12.0 KIB')).toBeInTheDocument()
    expect(screen.getByText('Exact export manifest JSON')).toBeInTheDocument()
    const restore = screen.getByRole('button', { name: 'Restore verified export' })
    expect(restore).toBeDisabled()

    fireEvent.change(screen.getByLabelText('Restore confirmation'), {
      target: { value: `RESTORE ${exportResponse.export_id}` },
    })
    expect(restore).toBeEnabled()
    fireEvent.click(restore)

    expect(await screen.findByText('RESTORE COMPLETED')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/v1/workspace/exports',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      '/api/v1/workspace/restores',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('distinguishes an invalid server-managed bundle from no export', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        schema_version: 1,
        state: 'unavailable',
        reason: 'export_invalid',
        export: null,
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    ))

    render(<WorkspaceOperations enabled />)

    expect(await screen.findByText('LATEST EXPORT INVALID')).toBeInTheDocument()
    expect(screen.getByText(/failed portable-path, hash, or database verification/i)).toBeInTheDocument()
    expect(screen.queryByText('NO VERIFIED EXPORT')).not.toBeInTheDocument()
  })
})
