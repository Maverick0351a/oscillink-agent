import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import MemoryGraph from './MemoryGraph'
import type { CategoryLegendEntry, MemoryNodeSummary } from './memoryApi'
import { projectionDensity, shouldDrawNodeLabel } from './memoryGraphLayout'

const categories: CategoryLegendEntry[] = [
  { category: 'project', label: 'Projects', color: '#ff4fd8', symbol: 'P' },
  { category: 'research', label: 'Research', color: '#36f1cd', symbol: 'R' },
]

const memoryNodes: MemoryNodeSummary[] = [
  {
    id: 'doc_A37PTXSESJE0P4NFJTD7E7RRAH',
    title: 'Oscillink Agent',
    source_path: '20 Projects/Oscillink Agent.md',
    source_status: 'active',
    authority_state: 'approved',
    source_kind: 'obsidian',
    category: 'project',
    domains: ['ai_ml'],
    topics: [],
    content_hash: 'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    wikilink_count: 1,
  },
  {
    id: 'doc_PHBCG4C4DKQWX1903XXPVD7ZB6',
    title: 'Agent Architecture Research',
    source_path: '30 Notes/Research/Agent Research.md',
    source_status: 'active',
    authority_state: 'curated',
    source_kind: 'obsidian',
    category: 'research',
    domains: ['ai_ml', 'engineering'],
    topics: ['agent architecture'],
    content_hash: 'sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
    wikilink_count: 1,
  },
]

afterEach(cleanup)

describe('MemoryGraph', () => {
  it('uses a compact, focused-label policy for narrow reviewed-memory projections', () => {
    expect(projectionDensity('memory', 390)).toBe(0.22)
    expect(projectionDensity('memory', 900)).toBe(0.34)
    expect(projectionDensity('architecture', 390)).toBe(0.34)
    expect(shouldDrawNodeLabel('memory', 390, false)).toBe(false)
    expect(shouldDrawNodeLabel('memory', 390, true)).toBe(false)
    expect(shouldDrawNodeLabel('architecture', 390, false)).toBe(true)
  })

  it('exposes the graph renderer and reduced-motion accessibility copy', () => {
    render(<MemoryGraph latticeState="planned" />)

    const canvas = screen.getByRole('img', { name: 'Foundation memory architecture map' })
    expect(canvas.tagName).toBe('CANVAS')
    expect(canvas).toHaveAttribute('data-renderer', 'projected-3d-neural')
    expect(screen.getByText('FOUNDATION MAP · NOT MEMORY DATA')).toBeInTheDocument()
    expect(screen.getByText('DRAG TO ORBIT')).toBeInTheDocument()
  })

  it('renders reviewed records separately and exposes deterministic focused navigation', () => {
    const onSelect = vi.fn()
    render(
      <MemoryGraph
        mode="memory"
        latticeState="ready"
        nodes={memoryNodes}
        categories={categories}
        selectedId={memoryNodes[0]?.id ?? null}
        selectedLinks={['30 Notes/Research/Agent Research']}
        onSelect={onSelect}
      />,
    )

    expect(screen.getByRole('img', { name: 'Product memory lattice' })).toBeInTheDocument()
    expect(screen.getByText('PRODUCT MEMORY · 2 RECORDS')).toBeInTheDocument()
    expect(screen.queryByText('FOUNDATION MAP · NOT MEMORY DATA')).not.toBeInTheDocument()

    const selected = screen.getByRole('button', { name: 'Focus Oscillink Agent, Projects' })
    expect(selected).toHaveAttribute('aria-pressed', 'true')
    expect(selected).toHaveTextContent('P')

    fireEvent.click(screen.getByRole('button', { name: 'Focus Agent Architecture Research, Research' }))
    expect(onSelect).toHaveBeenCalledWith('doc_PHBCG4C4DKQWX1903XXPVD7ZB6')
  })
})
