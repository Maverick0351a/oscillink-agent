import { describe, expect, it } from 'vitest'

import { buildFoundationGraph } from './foundationGraph'

describe('foundation graph', () => {
  it('builds a spatial neural scaffold without presenting architecture as memory', () => {
    const graph = buildFoundationGraph('planned')

    expect(graph.nodes).toHaveLength(7)
    expect(graph.connections).toHaveLength(9)
    expect(graph.nodes.every((node) => node.kind === 'system_component')).toBe(true)
    expect(graph.nodes.every((node) => node.position.length === 3)).toBe(true)
    expect(new Set(graph.nodes.map((node) => node.position[2])).size).toBeGreaterThan(3)
    expect(graph.nodes.find((node) => node.id === 'memory-lattice')?.state).toBe('planned')
    expect(graph.connections.every((connection) => connection.curvature > 0)).toBe(true)
  })
})
