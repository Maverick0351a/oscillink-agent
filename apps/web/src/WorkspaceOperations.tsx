import { Archive, FileJson, LoaderCircle, RotateCcw, ShieldCheck } from 'lucide-react'
import { useEffect, useState } from 'react'

import {
  createWorkspaceExport,
  loadLatestWorkspaceExport,
  restoreWorkspaceExport,
  type WorkspaceExportResponse,
  type WorkspaceExportView,
} from './workspaceApi'
import './workspaceOperations.css'

interface WorkspaceOperationsProps {
  enabled: boolean
}

type LoadState = 'idle' | 'loading' | 'ready' | 'error'
type OperationState = 'idle' | 'exporting' | 'restoring' | 'restored' | 'failed'

function byteLabel(bytes: number) {
  return `${(bytes / 1024).toFixed(1)} KIB`
}

export default function WorkspaceOperations({ enabled }: WorkspaceOperationsProps) {
  const [loadState, setLoadState] = useState<LoadState>('idle')
  const [latest, setLatest] = useState<WorkspaceExportResponse | null>(null)
  const [unavailableReason, setUnavailableReason] = useState<WorkspaceExportView['reason']>(null)
  const [operation, setOperation] = useState<OperationState>('idle')
  const [confirmation, setConfirmation] = useState('')

  useEffect(() => {
    if (!enabled) {
      setLoadState('idle')
      setLatest(null)
      setUnavailableReason(null)
      setConfirmation('')
      return
    }
    const controller = new AbortController()
    setLoadState('loading')
    loadLatestWorkspaceExport(controller.signal)
      .then((view) => {
        setLatest(view.state === 'available' ? view.export : null)
        setUnavailableReason(view.state === 'unavailable' ? view.reason : null)
        setLoadState('ready')
      })
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === 'AbortError')) {
          setLoadState('error')
        }
      })
    return () => controller.abort()
  }, [enabled])

  const createExport = async () => {
    if (!enabled || operation === 'exporting' || operation === 'restoring') return
    setOperation('exporting')
    setConfirmation('')
    try {
      const response = await createWorkspaceExport()
      setLatest(response)
      setUnavailableReason(null)
      setOperation('idle')
    } catch {
      setOperation('failed')
    }
  }

  const restoreExport = async () => {
    if (
      !enabled
      || latest === null
      || confirmation !== `RESTORE ${latest.export_id}`
      || operation === 'exporting'
      || operation === 'restoring'
    ) return
    setOperation('restoring')
    try {
      await restoreWorkspaceExport(latest.export_id)
      setOperation('restored')
      setConfirmation('')
    } catch {
      setOperation('failed')
    }
  }

  const totalBytes = latest?.manifest.entries.reduce(
    (total, entry) => total + entry.byte_count,
    0,
  ) ?? 0
  const restorePhrase = latest === null ? '' : `RESTORE ${latest.export_id}`

  return (
    <section className="workspace-operations" aria-label="Workspace operations">
      <header className="workspace-operations-header">
        <Archive size={16} aria-hidden="true" />
        <div>
          <span className="section-index">WORKSPACE RECOVERY / HUMAN CONTROLLED</span>
          <h2>Workspace Operations</h2>
        </div>
        <button
          type="button"
          disabled={!enabled || operation === 'exporting' || operation === 'restoring'}
          onClick={() => void createExport()}
        >
          {operation === 'exporting'
            ? <LoaderCircle size={14} aria-hidden="true" />
            : <Archive size={14} aria-hidden="true" />}
          Create verified export
        </button>
      </header>

      {!enabled ? (
        <p className="workspace-operation-empty">
          Unlock the local workspace to manage verified exports.
        </p>
      ) : loadState === 'loading' ? (
        <p className="workspace-operation-empty">Loading latest verified export…</p>
      ) : loadState === 'error' ? (
        <p className="workspace-operation-error" role="alert">
          Latest export state could not be loaded.
        </p>
      ) : latest === null ? (
        <div className="workspace-operation-empty">
          <strong>
            {unavailableReason === 'export_invalid'
              ? 'LATEST EXPORT INVALID'
              : 'NO VERIFIED EXPORT'}
          </strong>
          <p>
            {unavailableReason === 'export_invalid'
              ? 'The latest server-managed bundle failed portable-path, hash, or database verification.'
              : 'Create a content-hashed recovery bundle before attempting restore.'}
          </p>
        </div>
      ) : (
        <>
          <div className="workspace-export-summary">
            <div>
              <span>LATEST VERIFIED EXPORT</span>
              <strong>{latest.export_id}</strong>
            </div>
            <span>
              {latest.manifest.entries.length} ENTRIES · {byteLabel(totalBytes)}
            </span>
          </div>

          <div className="workspace-export-entries">
            {latest.manifest.entries.map((entry) => (
              <article key={entry.path}>
                <header><strong>{entry.path}</strong><span>{entry.kind.toUpperCase()}</span></header>
                <small>{byteLabel(entry.byte_count)} · {entry.content_hash}</small>
              </article>
            ))}
          </div>

          <div className="workspace-restore-control">
            <div>
              <ShieldCheck size={14} aria-hidden="true" />
              <p>
                Restore atomically replaces active canonical state. Type
                <code>{restorePhrase}</code> to bind this action to the exact export.
              </p>
            </div>
            <label>
              <span>Restore confirmation</span>
              <input
                aria-label="Restore confirmation"
                autoComplete="off"
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
              />
            </label>
            <button
              type="button"
              disabled={confirmation !== restorePhrase || operation === 'restoring'}
              onClick={() => void restoreExport()}
            >
              {operation === 'restoring'
                ? <LoaderCircle size={14} aria-hidden="true" />
                : <RotateCcw size={14} aria-hidden="true" />}
              Restore verified export
            </button>
          </div>

          <details className="workspace-export-json">
            <summary><FileJson size={14} aria-hidden="true" /> Exact export manifest JSON</summary>
            <pre>{JSON.stringify(latest.manifest, null, 2)}</pre>
          </details>
        </>
      )}

      {operation === 'restored' ? (
        <p className="workspace-operation-success" role="status">RESTORE COMPLETED</p>
      ) : null}
      {operation === 'failed' ? (
        <p className="workspace-operation-error" role="alert">
          Workspace operation failed. No success was recorded.
        </p>
      ) : null}
    </section>
  )
}
