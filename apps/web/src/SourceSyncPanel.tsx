import { DatabaseZap, LoaderCircle } from 'lucide-react'
import { useEffect, useState } from 'react'

import {
  loadMemorySourceStatus,
  syncObsidianSource,
  type MemorySourceStatus,
  type MemorySourceSyncResult,
} from './memoryApi'

interface SourceSyncPanelProps {
  enabled: boolean
  onSynchronized: (result: MemorySourceSyncResult) => void | Promise<void>
}

function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

export default function SourceSyncPanel({ enabled, onSynchronized }: SourceSyncPanelProps) {
  const [status, setStatus] = useState<MemorySourceStatus | null>(null)
  const [statusError, setStatusError] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [synchronizing, setSynchronizing] = useState(false)
  const [result, setResult] = useState<MemorySourceSyncResult | null>(null)
  const [syncError, setSyncError] = useState(false)
  const [refreshError, setRefreshError] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    loadMemorySourceStatus(controller.signal)
      .then((nextStatus) => {
        setStatus(nextStatus)
        setStatusError(false)
      })
      .catch((error: unknown) => {
        if (!isAbort(error)) setStatusError(true)
      })
    return () => controller.abort()
  }, [])

  const sourceState = status?.state
  const configured = sourceState === 'configured'
  const statusLabel = statusError || (status !== null && sourceState === undefined)
    ? 'OBSIDIAN · STATUS UNAVAILABLE'
    : status === null
      ? 'OBSIDIAN · CHECKING'
      : `OBSIDIAN · ${sourceState?.replace('_', ' ').toUpperCase()}`

  const synchronize = async () => {
    if (!enabled || !configured || synchronizing) return
    setSynchronizing(true)
    setSyncError(false)
    setRefreshError(false)
    setResult(null)
    try {
      const synchronized = await syncObsidianSource()
      setResult(synchronized)
      setConfirming(false)
      try {
        await onSynchronized(synchronized)
      } catch {
        setRefreshError(true)
      }
    } catch {
      setSyncError(true)
    } finally {
      setSynchronizing(false)
    }
  }

  return (
    <section className="source-sync-panel" aria-label="Source synchronization">
      <header><DatabaseZap size={14} aria-hidden="true" /><strong>CONFIGURED SOURCE</strong></header>
      <p>{statusLabel}</p>
      {!enabled ? <p>Unlock the local workspace to synchronize.</p> : null}
      {confirming ? (
        <div className="source-sync-confirmation">
          <p>Synchronize the configured source now?</p>
          <button type="button" disabled={synchronizing} onClick={() => void synchronize()}>
            {synchronizing ? <LoaderCircle size={14} aria-hidden="true" /> : null}
            Confirm synchronization
          </button>
          <button type="button" disabled={synchronizing} onClick={() => setConfirming(false)}>Cancel</button>
        </div>
      ) : (
        <button type="button" disabled={!enabled || !configured} onClick={() => setConfirming(true)}>
          Synchronize source
        </button>
      )}
      {result !== null ? (
        <div className="source-sync-result" role="status">
          <strong>SOURCE SYNCHRONIZED</strong>
          <p>
            {result.created} created · {result.revised} revised · {result.unchanged} unchanged ·{' '}
            {result.missing} missing · {result.issues} {result.issues === 1 ? 'issue' : 'issues'}
          </p>
        </div>
      ) : null}
      {refreshError ? (
        <p className="error" role="alert">The source was synchronized, but the lattice could not refresh.</p>
      ) : null}
      {syncError ? <p className="error" role="alert">Source synchronization failed. No success was recorded.</p> : null}
    </section>
  )
}
