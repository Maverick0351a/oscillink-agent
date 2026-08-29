import { LoaderCircle, Plus } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import {
  createMemoryNode,
  type ArchitectureNodeId,
  type MemoryCategory,
  type MemoryDomain,
  type MemoryNodeDetail,
} from './memoryApi'

interface MemoryCreatePanelProps {
  enabled: boolean
  onCreated: (node: MemoryNodeDetail) => void | Promise<void>
}

const categories: Array<[MemoryCategory, string]> = [
  ['research', 'Research'],
  ['tooling', 'Tooling'],
  ['project', 'Project'],
  ['experiment', 'Experiment'],
  ['governance', 'Governance'],
  ['reference', 'Reference'],
  ['note', 'Note'],
]

const domains: Array<[MemoryDomain, string]> = [
  ['ai_ml', 'AI / ML'],
  ['rf_em', 'RF / EM'],
  ['science', 'Science'],
  ['mathematics', 'Mathematics'],
  ['engineering', 'Engineering'],
  ['software', 'Software'],
  ['business', 'Business'],
  ['general', 'General'],
]

const architectureNodes: Array<[ArchitectureNodeId, string]> = [
  ['identity-role', 'Identity & role'],
  ['goals-commitments', 'Goals & commitments'],
  ['projects-work', 'Projects & work'],
  ['knowledge-research', 'Knowledge & research'],
  ['people-relationships', 'People & relationships'],
  ['decisions-lessons', 'Decisions & lessons'],
  ['preferences-context', 'Preferences & context'],
]

function toggle<T extends string>(values: T[], value: T): T[] {
  return values.includes(value)
    ? values.filter((candidate) => candidate !== value)
    : [...values, value]
}

export default function MemoryCreatePanel({ enabled, onCreated }: MemoryCreatePanelProps) {
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [category, setCategory] = useState<MemoryCategory>('note')
  const [selectedDomains, setSelectedDomains] = useState<MemoryDomain[]>([])
  const [topics, setTopics] = useState('')
  const [associations, setAssociations] = useState<ArchitectureNodeId[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<'candidate' | 'error' | null>(null)

  const valid = title.trim() !== '' && content.trim() !== '' && selectedDomains.length > 0

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!enabled || !valid || submitting) return
    setSubmitting(true)
    setResult(null)
    try {
      const response = await createMemoryNode({
        title: title.trim(),
        content: content.trim(),
        category,
        domains: selectedDomains,
        topics: topics.split(',').map((topic) => topic.trim()).filter(Boolean),
        architecture_node_ids: associations,
      })
      await onCreated(response.node)
      setResult('candidate')
      setTitle('')
      setContent('')
      setTopics('')
      setSelectedDomains([])
      setAssociations([])
    } catch {
      setResult('error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="memory-create-panel" aria-label="Create candidate memory">
      <header><Plus size={14} aria-hidden="true" /><strong>NEW CANDIDATE MEMORY</strong></header>
      <form onSubmit={(event) => void submit(event)}>
        <label>
          <span>Title</span>
          <input aria-label="Memory title" maxLength={512} value={title} onChange={(event) => setTitle(event.target.value)} />
        </label>
        <label>
          <span>Content</span>
          <textarea aria-label="Memory content" maxLength={2 * 1024 * 1024} value={content} onChange={(event) => setContent(event.target.value)} />
        </label>
        <label>
          <span>Category</span>
          <select aria-label="Memory category" value={category} onChange={(event) => setCategory(event.target.value as MemoryCategory)}>
            {categories.map(([value, text]) => <option key={value} value={value}>{text}</option>)}
          </select>
        </label>
        <fieldset>
          <legend>Domains</legend>
          {domains.map(([value, text]) => (
            <label key={value}>
              <input type="checkbox" checked={selectedDomains.includes(value)} onChange={() => setSelectedDomains(toggle(selectedDomains, value))} />
              {text}
            </label>
          ))}
        </fieldset>
        <label>
          <span>Topics</span>
          <input aria-label="Memory topics" placeholder="comma, separated" value={topics} onChange={(event) => setTopics(event.target.value)} />
        </label>
        <fieldset>
          <legend>Architecture associations</legend>
          {architectureNodes.map(([value, text]) => (
            <label key={value}>
              <input type="checkbox" checked={associations.includes(value)} onChange={() => setAssociations(toggle(associations, value))} />
              {text}
            </label>
          ))}
        </fieldset>
        {!enabled ? <p>Unlock the local workspace to create memory.</p> : null}
        {result === 'candidate' ? <p className="success" role="status">CANDIDATE CREATED</p> : null}
        {result === 'error' ? <p className="error" role="alert">Candidate creation failed. No success was recorded.</p> : null}
        <button type="submit" disabled={!enabled || !valid || submitting}>
          {submitting ? <LoaderCircle size={14} aria-hidden="true" /> : <Plus size={14} aria-hidden="true" />}
          Create candidate memory
        </button>
      </form>
    </section>
  )
}
