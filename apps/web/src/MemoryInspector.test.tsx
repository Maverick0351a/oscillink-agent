import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import MemoryInspector from './MemoryInspector'
import type { CategoryLegendEntry, DomainLegendEntry, MemoryNodeDetail } from './memoryApi'

const categories: CategoryLegendEntry[] = [
  { category: 'project', label: 'Projects', color: '#ff4fd8', symbol: 'P' },
]
const domains: DomainLegendEntry[] = [{ domain: 'ai_ml', label: 'AI / ML' }]
const node: MemoryNodeDetail = {
  id: 'mem_A37PTXSESJE0P4NFJTD7E7RRAH',
  title: 'Oscillink Agent',
  source_path: '20 Projects/Oscillink Agent.md',
  source_status: 'active',
  authority_state: 'approved',
  source_kind: 'obsidian',
  category: 'project',
  domains: ['ai_ml'],
  topics: ['long-term memory'],
  content_hash: 'sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
  wikilink_count: 1,
  frontmatter_type: 'project',
  wikilinks: ['30 Notes/Research/Agent Research'],
  classification_basis: ['frontmatter:type=project', 'metadata:area=AI Research'],
}

afterEach(cleanup)

describe('MemoryInspector', () => {
  it('shows exact provenance and classification for a focused node', () => {
    render(
      <MemoryInspector
        node={node}
        categories={categories}
        domains={domains}
        loading={false}
        error={null}
      />,
    )

    expect(screen.getByRole('heading', { name: 'Oscillink Agent' })).toBeInTheDocument()
    expect(screen.getByText('Projects')).toBeInTheDocument()
    expect(screen.getByText('APPROVED RECORD')).toBeInTheDocument()
    expect(screen.getByText('OBSIDIAN SOURCE')).toBeInTheDocument()
    expect(screen.getByText('AI / ML')).toBeInTheDocument()
    expect(screen.getByText('20 Projects/Oscillink Agent.md')).toBeInTheDocument()
    expect(screen.getByText(node.content_hash)).toBeInTheDocument()
    expect(screen.getByText('frontmatter:type=project')).toBeInTheDocument()
    expect(screen.getByText('30 Notes/Research/Agent Research')).toBeInTheDocument()
  })

  it('does not fabricate provenance before a record is selected', () => {
    render(
      <MemoryInspector
        node={null}
        categories={categories}
        domains={domains}
        loading={false}
        error={null}
      />,
    )

    expect(screen.getByRole('heading', { name: 'No memory selected' })).toBeInTheDocument()
    expect(screen.getByText(/Select a memory record/)).toBeInTheDocument()
    expect(screen.queryByText('Oscillink Agent')).not.toBeInTheDocument()
  })
})
