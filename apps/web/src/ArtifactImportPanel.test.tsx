import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import ArtifactImportPanel from './ArtifactImportPanel'

const sourceResponse = {
  schema_version: 1,
  count: 1,
  scopes: [
    {
      scope_id: 'user_selection',
      state: 'configured',
      targets: [
        { target: 'evidence.md', source_name: 'evidence.md', logical_bytes: 19 },
      ],
    },
  ],
}

const importedResponse = {
  schema_version: 1,
  state: 'imported',
  event_id: 'evt_01J00000000000000000000300',
  artifact: {
    artifact_ref: `sha256:${'a'.repeat(64)}`,
    source_scope_id: 'user_selection',
    source_name: 'evidence.md',
    media_type: 'text/markdown',
    logical_bytes: 19,
    unique_physical_bytes: 19,
    deduplicated: false,
  },
  association: {
    state: 'candidate',
    review_state: 'pending_review',
    target_record_id: 'mem_01J00000000000000000000001',
    event_id: 'evt_01J00000000000000000000301',
  },
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('ArtifactImportPanel', () => {
  it('does not enumerate or import while the workspace is locked', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    render(
      <ArtifactImportPanel
        enabled={false}
        targetRecordId="mem_01J00000000000000000000001"
        targetTitle="Target memory"
        onImported={vi.fn()}
      />,
    )

    expect(screen.getByText('WORKSPACE LOCKED')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Import selected evidence' })).toBeDisabled()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('imports only a server-enumerated target after confirmation', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).endsWith('/artifact-imports/sources')) {
        return new Response(JSON.stringify(sourceResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      expect(String(input)).toBe('/api/v1/artifact-imports')
      expect(init?.method).toBe('POST')
      expect(init?.headers).toMatchObject({
        'Content-Type': 'application/json',
      })
      const headers = init?.headers as Record<string, string>
      expect(headers['Idempotency-Key']).toMatch(/^artifact-import-/)
      expect(JSON.parse(String(init?.body))).toMatchObject({
        schema_version: 1,
        scope_id: 'user_selection',
        target: 'evidence.md',
        target_record_id: 'mem_01J00000000000000000000001',
      })
      return new Response(JSON.stringify(importedResponse), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      })
    })
    vi.stubGlobal('fetch', fetchMock)
    const onImported = vi.fn(async () => undefined)

    render(
      <ArtifactImportPanel
        enabled
        targetRecordId="mem_01J00000000000000000000001"
        targetTitle="Target memory"
        onImported={onImported}
      />,
    )

    await screen.findByRole('option', { name: 'evidence.md · 19 B' })
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Import selected evidence' }))
    expect(screen.getByText(/Create a pending evidence association with Target memory/)).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByRole('button', { name: 'Confirm import' }))

    expect(await screen.findByText('IMPORTED · PENDING REVIEW')).toBeInTheDocument()
    await waitFor(() => expect(onImported).toHaveBeenCalledWith(importedResponse))
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('ignores a stale source-list completion after the workspace locks', async () => {
    let releaseSources: (response: Response) => void = () => undefined
    const sourceGate = new Promise<Response>((resolve) => { releaseSources = resolve })
    vi.stubGlobal('fetch', vi.fn(() => sourceGate))
    const props = {
      targetRecordId: 'mem_01J00000000000000000000001',
      targetTitle: 'Target memory',
      onImported: vi.fn(),
    }
    const { rerender } = render(<ArtifactImportPanel enabled {...props} />)

    rerender(<ArtifactImportPanel enabled={false} {...props} />)
    await act(async () => {
      releaseSources(new Response(JSON.stringify(sourceResponse), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }))
      await sourceGate
      await Promise.resolve()
    })

    await waitFor(() => expect(screen.getByText('WORKSPACE LOCKED')).toBeInTheDocument())
    expect(screen.queryByRole('option', { name: 'evidence.md · 19 B' })).not.toBeInTheDocument()
  })
})
