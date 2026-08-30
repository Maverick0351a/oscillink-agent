import { FileInput } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import {
  importArtifact,
  loadArtifactImportSources,
  type ArtifactImportResponse,
  type ArtifactImportScope,
} from './artifactApi'

interface ArtifactImportPanelProps {
  enabled: boolean
  targetRecordId: string | null
  targetTitle: string | null
  onImported: (response: ArtifactImportResponse) => void | Promise<void>
}

const formatBytes = (bytes: number): string => `${bytes} B`

const selectionValue = (scopeId: string, target: string): string => `${scopeId}\n${target}`

export default function ArtifactImportPanel({
  enabled,
  targetRecordId,
  targetTitle,
  onImported,
}: ArtifactImportPanelProps) {
  const [scopes, setScopes] = useState<ArtifactImportScope[]>([])
  const [loading, setLoading] = useState(false)
  const [loadFailed, setLoadFailed] = useState(false)
  const [selection, setSelection] = useState('')
  const [confirming, setConfirming] = useState(false)
  const [importing, setImporting] = useState(false)
  const [result, setResult] = useState<ArtifactImportResponse | null>(null)
  const [importFailed, setImportFailed] = useState(false)
  const [refreshFailed, setRefreshFailed] = useState(false)
  const requestVersion = useRef(0)

  useEffect(() => {
    const version = ++requestVersion.current
    if (!enabled) {
      setScopes([])
      setSelection('')
      return
    }
    const controller = new AbortController()
    setLoading(true)
    setLoadFailed(false)
    void loadArtifactImportSources(controller.signal)
      .then((response) => {
        if (requestVersion.current !== version) return
        const nextScopes = Array.isArray(response.scopes) ? response.scopes : []
        setScopes(nextScopes)
        const first = nextScopes
          .filter((scope) => scope.state === 'configured')
          .flatMap((scope) => scope.targets.map((target) => selectionValue(scope.scope_id, target.target)))[0]
        setSelection(first ?? '')
      })
      .catch((error: unknown) => {
        if (
          requestVersion.current === version
          && !(error instanceof DOMException && error.name === 'AbortError')
        ) setLoadFailed(true)
      })
      .finally(() => {
        if (requestVersion.current === version) setLoading(false)
      })
    return () => controller.abort()
  }, [enabled])

  const choices = useMemo(
    () =>
      scopes.flatMap((scope) =>
        scope.state === 'configured'
          ? scope.targets.map((target) => ({
              value: selectionValue(scope.scope_id, target.target),
              label: `${target.source_name} · ${formatBytes(target.logical_bytes)}`,
              scopeId: scope.scope_id,
              target: target.target,
            }))
          : [],
      ),
    [scopes],
  )
  const selected = choices.find((choice) => choice.value === selection)
  const canImport = enabled && targetRecordId !== null && selected !== undefined && !importing

  const confirmImport = async () => {
    if (!canImport || targetRecordId === null || selected === undefined) return
    setImporting(true)
    setImportFailed(false)
    setRefreshFailed(false)
    try {
      const imported = await importArtifact({
        scopeId: selected.scopeId,
        target: selected.target,
        targetRecordId,
      })
      setResult(imported)
      setConfirming(false)
      try {
        await onImported(imported)
      } catch {
        setRefreshFailed(true)
      }
    } catch {
      setImportFailed(true)
    } finally {
      setImporting(false)
    }
  }

  return (
    <section className="artifact-import-panel" aria-label="Artifact import">
      <div className="artifact-import-heading">
        <FileInput size={15} aria-hidden="true" />
        <div>
          <strong>Governed evidence import</strong>
          <span>{enabled ? (loading ? 'CHECKING SOURCES' : 'CONFIGURED TARGETS ONLY') : 'WORKSPACE LOCKED'}</span>
        </div>
      </div>
      <label>
        Evidence target
        <select
          value={selection}
          onChange={(event) => {
            setSelection(event.target.value)
            setResult(null)
          }}
          disabled={!enabled || loading || importing || choices.length === 0}
        >
          {choices.length === 0 ? <option value="">No import target available</option> : null}
          {choices.map((choice) => (
            <option key={choice.value} value={choice.value}>{choice.label}</option>
          ))}
        </select>
      </label>
      <button
        type="button"
        className="secondary-action"
        disabled={!canImport}
        onClick={() => setConfirming(true)}
      >
        Import selected evidence
      </button>
      {targetRecordId === null && enabled ? <p className="hint">Select a memory record first.</p> : null}
      {loadFailed ? <p role="alert" className="error">IMPORT TARGETS UNAVAILABLE</p> : null}
      {confirming ? (
        <div className="artifact-import-confirmation" role="group" aria-label="Confirm artifact import">
          <p>Create a pending evidence association with {targetTitle ?? 'the selected memory'}?</p>
          <button type="button" className="primary-action" disabled={importing} onClick={() => void confirmImport()}>
            {importing ? 'Importing…' : 'Confirm import'}
          </button>
          <button type="button" className="ghost-action" disabled={importing} onClick={() => setConfirming(false)}>
            Cancel
          </button>
        </div>
      ) : null}
      {result?.association.state === 'candidate' ? <p className="success">IMPORTED · PENDING REVIEW</p> : null}
      {result?.association.state === 'unattached' ? <p className="success">IMPORTED · UNATTACHED</p> : null}
      {importFailed ? <p role="alert" className="error">ARTIFACT IMPORT FAILED</p> : null}
      {refreshFailed ? <p role="alert" className="error">IMPORTED, BUT PROPOSALS COULD NOT REFRESH</p> : null}
    </section>
  )
}
