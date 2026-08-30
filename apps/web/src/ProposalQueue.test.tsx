import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import ProposalQueue from './ProposalQueue'

const pendingProposal = {
  proposal_id: 'evt_01J00000000000000000000400',
  state: 'pending_review',
  target_record_id: 'mem_01J00000000000000000000001',
  artifact_ref: `sha256:${'b'.repeat(64)}`,
  source_name: 'evidence.md',
  created_at: '2026-08-29T21:00:00Z',
  decision_event_id: null,
  decided_at: null,
  decided_by: null,
}

const approvedProposal = {
  ...pendingProposal,
  state: 'approved',
  decision_event_id: 'evt_01J00000000000000000000401',
  decided_at: '2026-08-29T21:01:00Z',
  decided_by: 'human_local_user',
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('ProposalQueue', () => {
  it('does not expose proposal data while the workspace is locked', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    render(<ProposalQueue enabled={false} refreshKey={0} onReviewed={vi.fn()} />)

    expect(screen.getByText('PROPOSALS LOCKED')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('approves a pending relationship only after explicit confirmation', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method !== 'POST') {
        return new Response(
          JSON.stringify({ schema_version: 1, count: 1, proposals: [pendingProposal] }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        )
      }
      expect(String(input)).toBe(
        `/api/v1/memory-proposals/${pendingProposal.proposal_id}/decisions`,
      )
      const headers = init.headers as Record<string, string>
      expect(headers['Idempotency-Key']).toMatch(/^proposal-decision-/)
      expect(JSON.parse(String(init.body))).toMatchObject({
        schema_version: 1,
        decision: 'approved',
      })
      return new Response(JSON.stringify(approvedProposal), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    })
    vi.stubGlobal('fetch', fetchMock)
    const onReviewed = vi.fn(async () => undefined)

    render(<ProposalQueue enabled refreshKey={0} onReviewed={onReviewed} />)

    await screen.findByText('evidence.md')
    fireEvent.click(screen.getByRole('button', { name: 'Approve evidence.md' }))
    expect(screen.getByText(/Approve this untrusted evidence relationship/)).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByRole('button', { name: 'Confirm approval' }))

    expect(await screen.findByText('APPROVED')).toBeInTheDocument()
    await waitFor(() => expect(onReviewed).toHaveBeenCalledWith(approvedProposal))
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('does not let an older proposal load replace a newer refresh', async () => {
    let releaseFirst: (response: Response) => void = () => undefined
    const firstGate = new Promise<Response>((resolve) => { releaseFirst = resolve })
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => firstGate)
      .mockResolvedValueOnce(new Response(
        JSON.stringify({ schema_version: 1, count: 0, proposals: [] }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ))
    vi.stubGlobal('fetch', fetchMock)
    const props = { enabled: true, onReviewed: vi.fn() }
    const { rerender } = render(<ProposalQueue {...props} refreshKey={0} />)

    rerender(<ProposalQueue {...props} refreshKey={1} />)
    expect(await screen.findByText('No evidence proposals.')).toBeInTheDocument()
    await act(async () => {
      releaseFirst(new Response(
        JSON.stringify({ schema_version: 1, count: 1, proposals: [pendingProposal] }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ))
      await firstGate
      await Promise.resolve()
    })

    expect(screen.queryByText('evidence.md')).not.toBeInTheDocument()
  })
})
