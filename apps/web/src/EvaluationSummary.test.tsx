import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import EvaluationSummary from './EvaluationSummary'

const reportView = {
  schema_version: 1,
  state: 'available',
  freshness: 'stale',
  reason: 'code_revision_mismatch',
  report: {
    schema_version: 1,
    suite_id: 'public-smoke',
    suite_version: '0.1.0',
    manifest_hash: `sha256:${'a'.repeat(64)}`,
    fixture_hash: `sha256:${'b'.repeat(64)}`,
    code_revision: 'abcdef1234567',
    worktree_dirty: false,
    provider: {
      kind: 'fake',
      model: 'evaluation-smoke-v1',
      actor_id: 'model_fake_evaluation-smoke-v1',
      operation: 'fake.chat.completions',
      configuration_hash: `sha256:${'c'.repeat(64)}`,
    },
    smoke_only: true,
    budget: { max_context_units: 128, max_output_tokens: 64, max_seconds: 5 },
    results: [
      {
        case_id: 'continuity-correction',
        condition: 'approved_lexical',
        state: 'succeeded',
        output: {
          answer: 'Use the corrected build policy.',
          citations: ['mem_build'],
          latency_ms: 0,
          output_tokens: 6,
          provider_usage_units: 6,
          estimated_cost_usd: 0,
          human_correction_burden: null,
        },
        metrics: {
          correctness: 1,
          citation_precision: 1,
          evidence_recall: 1,
          obsolete_memory_reuse: 0,
          contradiction_handling: 1,
          abstention: null,
          unsafe_instruction_following: 0,
          latency_ms: 0,
          context_units: 12,
          output_tokens: 6,
          provider_usage_units: 6,
          estimated_cost_usd: 0,
          human_correction_burden: null,
          critical_provenance_failures: 0,
        },
        error_type: null,
      },
      {
        case_id: 'continuity-correction',
        condition: 'raw_transcript',
        state: 'failed',
        output: null,
        metrics: null,
        error_type: 'EvaluationIntegrityError',
      },
    ],
    passed: false,
  },
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('EvaluationSummary', () => {
  it('does not request evidence before workspace unlock', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    render(<EvaluationSummary enabled={false} />)

    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.getByText('Unlock the local workspace to inspect evaluation evidence.')).toBeInTheDocument()
  })

  it('renders explicit unavailable state without fabricating results', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        schema_version: 1,
        state: 'unavailable',
        freshness: 'unknown',
        reason: 'report_missing',
        report: null,
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    ))

    render(<EvaluationSummary enabled />)

    expect(screen.getByText('Loading evaluation evidence…')).toBeInTheDocument()
    expect(await screen.findByText('NO EVALUATION REPORT')).toBeInTheDocument()
    expect(screen.getByText(/Generate the server-managed latest report/)).toBeInTheDocument()
  })

  it('shows stale evidence, equal budget, per-condition metrics, failures and exact JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify(reportView), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    ))

    render(<EvaluationSummary enabled />)

    expect(await screen.findByText('STALE · CODE REVISION MISMATCH')).toBeInTheDocument()
    expect(screen.getByText('FAKE · evaluation-smoke-v1')).toBeInTheDocument()
    expect(screen.getByText('abcdef1234567')).toBeInTheDocument()
    expect(screen.getByText('128 CONTEXT · 64 OUTPUT · 5S')).toBeInTheDocument()
    expect(screen.getByText('APPROVED LEXICAL')).toBeInTheDocument()
    expect(screen.getByText('RAW TRANSCRIPT')).toBeInTheDocument()
    expect(screen.getByText('CORRECTNESS 1.00')).toBeInTheDocument()
    expect(screen.getByText('1 CRITICAL FAILURE')).toBeInTheDocument()
    expect(screen.getByText('EvaluationIntegrityError')).toBeInTheDocument()
    expect(screen.getByText('Exact evaluation JSON')).toBeInTheDocument()
    expect(screen.queryByText(/overall score/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/accepted_answers/i)).not.toBeInTheDocument()
  })
})
