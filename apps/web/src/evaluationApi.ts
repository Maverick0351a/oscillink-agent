import { workspaceAuthorizationHeaders } from './workspaceAuth'

export type EvaluationCondition =
  | 'no_memory'
  | 'raw_transcript'
  | 'generated_summary'
  | 'approved_lexical'

export interface EvaluationMetrics {
  correctness: number
  citation_precision: number
  evidence_recall: number
  obsolete_memory_reuse: number
  contradiction_handling: number | null
  abstention: number | null
  unsafe_instruction_following: number
  latency_ms: number
  context_units: number
  output_tokens: number
  provider_usage_units: number | null
  estimated_cost_usd: number | null
  human_correction_burden: number | null
  critical_provenance_failures: number
}

export interface EvaluationResult {
  case_id: string
  condition: EvaluationCondition
  state: 'succeeded' | 'failed'
  output: {
    answer: string
    citations: string[]
    latency_ms: number
    output_tokens: number
    provider_usage_units: number | null
    estimated_cost_usd: number | null
    human_correction_burden: number | null
  } | null
  metrics: EvaluationMetrics | null
  error_type: string | null
}

export interface EvaluationReport {
  schema_version: 1
  suite_id: string
  suite_version: string
  manifest_hash: string
  fixture_hash: string
  code_revision: string
  worktree_dirty: boolean
  provider: {
    kind: 'fake' | 'ollama' | 'openai_compatible'
    model: string
    actor_id: string
    operation: string
    configuration_hash: string
  }
  smoke_only: boolean
  budget: {
    max_context_units: number
    max_output_tokens: number
    max_seconds: number
  }
  results: EvaluationResult[]
  passed: boolean
}

export interface EvaluationReportView {
  schema_version: 1
  state: 'available' | 'unavailable'
  freshness: 'current' | 'stale' | 'unknown'
  reason:
    | 'report_missing'
    | 'report_invalid'
    | 'code_revision_mismatch'
    | 'dirty_worktree'
    | null
  report: EvaluationReport | null
}

export async function loadLatestEvaluation(
  signal?: AbortSignal,
): Promise<EvaluationReportView> {
  const response = await fetch('/api/v1/evaluations/latest', {
    headers: workspaceAuthorizationHeaders(),
    signal,
  })
  if (!response.ok) throw new Error(`evaluation evidence failed: ${response.status}`)
  return response.json() as Promise<EvaluationReportView>
}
