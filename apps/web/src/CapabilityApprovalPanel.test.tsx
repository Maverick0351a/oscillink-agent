import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import CapabilityApprovalPanel from './CapabilityApprovalPanel'
import type { PendingToolRequestResponse } from './chatApi'

const pending: PendingToolRequestResponse = {
  schema_version: 1,
  state: 'awaiting_approval',
  session_id: 'ses_01J00000000000000000000050',
  run_id: 'run_01J00000000000000000000050',
  task_id: 'tsk_01J00000000000000000000050',
  provider: { kind: 'fake', model: 'deterministic-v1' },
  subject_actor_id: 'model_fake_deterministic_v1',
  tool_request_event_id: 'evt_01J00000000000000000000050',
  request: {
    schema_version: 1,
    operation: 'file.read',
    scope_id: 'workspace_a',
    target: 'docs/evidence.txt',
    max_bytes: 4096,
  },
  valid_for_seconds: 60,
  allowed_extensions: ['.txt'],
  network_allowed: false,
}

afterEach(cleanup)

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((nextResolve, nextReject) => {
    resolve = nextResolve
    reject = nextReject
  })
  return { promise, resolve, reject }
}

describe('CapabilityApprovalPanel', () => {
  it('shows the exact portable authority envelope without a host path', () => {
    render(<CapabilityApprovalPanel pending={pending} onDecision={vi.fn()} />)

    const panel = screen.getByRole('region', { name: 'Capability approval' })
    expect(panel).toHaveTextContent('AWAITING HUMAN APPROVAL')
    expect(panel).toHaveTextContent('workspace_a')
    expect(panel).toHaveTextContent('docs/evidence.txt')
    expect(panel).toHaveTextContent('model_fake_deterministic_v1')
    expect(panel).toHaveTextContent('4,096 BYTES')
    expect(panel).toHaveTextContent('.txt')
    expect(panel).toHaveTextContent('NETWORK DENIED')
    expect(panel).toHaveTextContent('60 SECONDS')
    expect(panel).not.toHaveTextContent(/C:\\|\/Users\/|\/home\//)
  })

  it('locks both decisions while approval is pending and reports success', async () => {
    const operation = deferred<'succeeded' | 'denied'>()
    const onDecision = vi.fn(() => operation.promise)
    render(<CapabilityApprovalPanel pending={pending} onDecision={onDecision} />)

    fireEvent.click(screen.getByRole('button', { name: 'Approve file read' }))
    expect(screen.getByText('APPROVAL IN PROGRESS')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Approve file read' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Deny file read' })).toBeDisabled()

    operation.resolve('succeeded')
    expect(await screen.findByText('TOOL LOOP SUCCEEDED')).toBeInTheDocument()
    expect(onDecision).toHaveBeenCalledWith('approved')
  })

  it('records denial distinctly and exposes no execution controls afterward', async () => {
    const onDecision = vi.fn(async () => 'denied' as const)
    render(<CapabilityApprovalPanel pending={pending} onDecision={onDecision} />)

    fireEvent.click(screen.getByRole('button', { name: 'Deny file read' }))
    expect(await screen.findByText('REQUEST DENIED')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Approve file read' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Deny file read' })).not.toBeInTheDocument()
  })

  it('keeps the exact request visible when mutation fails', async () => {
    const onDecision = vi.fn(async () => {
      throw new Error('request failed')
    })
    render(<CapabilityApprovalPanel pending={pending} onDecision={onDecision} />)

    fireEvent.click(screen.getByRole('button', { name: 'Approve file read' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('CAPABILITY DECISION FAILED')
    expect(screen.getByText('docs/evidence.txt')).toBeInTheDocument()
  })
})
