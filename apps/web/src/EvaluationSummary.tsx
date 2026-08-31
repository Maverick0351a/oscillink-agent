import { Activity, FileJson, FlaskConical, ShieldAlert } from 'lucide-react'
import { useEffect, useState } from 'react'

import {
  loadLatestEvaluation,
  type EvaluationReportView,
  type EvaluationResult,
} from './evaluationApi'
import './evaluationSummary.css'

interface EvaluationSummaryProps {
  enabled: boolean
}

type LoadState = 'idle' | 'loading' | 'ready' | 'error'

function label(value: string) {
  return value.replaceAll('_', ' ').toUpperCase()
}

function freshnessLabel(view: EvaluationReportView) {
  if (view.freshness === 'current') return 'CURRENT · CODE REVISION MATCHED'
  if (view.reason === 'code_revision_mismatch') return 'STALE · CODE REVISION MISMATCH'
  if (view.reason === 'dirty_worktree') return 'STALE · DIRTY EVALUATION WORKTREE'
  return 'FRESHNESS UNKNOWN'
}

function ConditionResult({ result }: { result: EvaluationResult }) {
  const metrics = result.metrics
  return (
    <article className="evaluation-condition" data-state={result.state}>
      <header>
        <strong>{label(result.condition)}</strong>
        <span>{label(result.state)}</span>
      </header>
      {metrics ? (
        <div className="evaluation-metrics">
          <span>CORRECTNESS {metrics.correctness.toFixed(2)}</span>
          <span>CITATION {metrics.citation_precision.toFixed(2)}</span>
          <span>EVIDENCE {metrics.evidence_recall.toFixed(2)}</span>
          <span>OBSOLETE {metrics.obsolete_memory_reuse.toFixed(2)}</span>
          <span>{metrics.context_units} CONTEXT UNITS</span>
          <span>{metrics.output_tokens} OUTPUT TOKENS</span>
        </div>
      ) : (
        <p className="evaluation-error">{result.error_type ?? 'UNCLASSIFIED EVALUATION FAILURE'}</p>
      )}
    </article>
  )
}

export default function EvaluationSummary({ enabled }: EvaluationSummaryProps) {
  const [loadState, setLoadState] = useState<LoadState>('idle')
  const [view, setView] = useState<EvaluationReportView | null>(null)

  useEffect(() => {
    if (!enabled) {
      setLoadState('idle')
      setView(null)
      return
    }
    const controller = new AbortController()
    setLoadState('loading')
    setView(null)
    loadLatestEvaluation(controller.signal)
      .then((response) => {
        setView(response)
        setLoadState('ready')
      })
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === 'AbortError')) {
          setLoadState('error')
        }
      })
    return () => controller.abort()
  }, [enabled])

  if (!enabled) {
    return (
      <section className="evaluation-summary" aria-label="Evaluation summary">
        <p className="evaluation-empty">Unlock the local workspace to inspect evaluation evidence.</p>
      </section>
    )
  }

  if (loadState === 'loading') {
    return (
      <section className="evaluation-summary" aria-label="Evaluation summary">
        <p className="evaluation-empty">Loading evaluation evidence…</p>
      </section>
    )
  }

  if (loadState === 'error') {
    return (
      <section className="evaluation-summary" aria-label="Evaluation summary">
        <p className="evaluation-error" role="alert">Evaluation evidence could not be loaded.</p>
      </section>
    )
  }

  if (view?.state !== 'available' || view.report === null) {
    return (
      <section className="evaluation-summary" aria-label="Evaluation summary">
        <header className="evaluation-summary-header">
          <ShieldAlert size={16} aria-hidden="true" />
          <strong>NO EVALUATION REPORT</strong>
        </header>
        <p className="evaluation-empty">
          Generate the server-managed latest report before comparing conditions.
        </p>
        <small>{view?.reason ? label(view.reason) : 'REPORT STATE UNKNOWN'}</small>
      </section>
    )
  }

  const report = view.report
  const criticalFailures = report.results.reduce(
    (total, result) => total + (result.metrics?.critical_provenance_failures ?? (result.state === 'failed' ? 1 : 0)),
    0,
  )

  return (
    <section className="evaluation-summary" aria-label="Evaluation summary">
      <header className="evaluation-summary-header">
        <FlaskConical size={16} aria-hidden="true" />
        <div>
          <span className="section-index">PUBLIC EVALUATION / READ ONLY</span>
          <h2>Evaluation Summary</h2>
        </div>
        <span className="evaluation-freshness" data-state={view.freshness}>
          {freshnessLabel(view)}
        </span>
      </header>

      <dl className="evaluation-facts">
        <div><dt>SUITE</dt><dd>{report.suite_id} · {report.suite_version}</dd></div>
        <div><dt>PROVIDER / MODEL</dt><dd>{label(report.provider.kind)} · {report.provider.model}</dd></div>
        <div><dt>CODE REVISION</dt><dd>{report.code_revision}</dd></div>
        <div><dt>EQUAL BUDGET</dt><dd>{report.budget.max_context_units} CONTEXT · {report.budget.max_output_tokens} OUTPUT · {report.budget.max_seconds}S</dd></div>
        <div><dt>FIXTURE</dt><dd>{report.fixture_hash}</dd></div>
        <div><dt>CONFIGURATION</dt><dd>{report.provider.configuration_hash}</dd></div>
      </dl>

      <div className="evaluation-verdict" data-state={report.passed ? 'passed' : 'failed'}>
        <Activity size={14} aria-hidden="true" />
        <strong>{report.passed ? 'EVALUATION PASSED' : 'EVALUATION DID NOT PASS'}</strong>
        <span>{criticalFailures} CRITICAL {criticalFailures === 1 ? 'FAILURE' : 'FAILURES'}</span>
      </div>

      <div className="evaluation-conditions">
        {report.results.map((result) => (
          <ConditionResult key={`${result.case_id}:${result.condition}`} result={result} />
        ))}
      </div>

      <details className="evaluation-json">
        <summary><FileJson size={14} aria-hidden="true" /> Exact evaluation JSON</summary>
        <pre>{JSON.stringify(report, null, 2)}</pre>
      </details>
    </section>
  )
}
