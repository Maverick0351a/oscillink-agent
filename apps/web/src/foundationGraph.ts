export type FeatureState = 'planned' | 'preview' | 'ready'

export type Point3D = readonly [x: number, y: number, z: number]
export type NeuralTone = 'authority' | 'projection' | 'memory'

export interface FoundationNode {
  id: string
  label: string
  detail: string
  kind: 'system_component'
  state: FeatureState
  position: Point3D
  radius: number
  tone: NeuralTone
}

export interface FoundationConnection {
  id: string
  source: string
  target: string
  kind: 'projection' | 'lineage' | 'evidence'
  curvature: number
  phase: number
}

export interface FoundationGraph {
  nodes: FoundationNode[]
  connections: FoundationConnection[]
}

export function buildFoundationGraph(latticeState: FeatureState): FoundationGraph {
  return {
    nodes: [
      {
        id: 'obsidian-authority',
        label: 'Reviewed Obsidian',
        detail: 'Human authority',
        kind: 'system_component',
        state: 'ready',
        position: [-1.35, -0.18, -0.58],
        radius: 1.05,
        tone: 'authority',
      },
      {
        id: 'fts-index',
        label: 'FTS5 Index',
        detail: 'Rebuildable projection',
        kind: 'system_component',
        state: latticeState,
        position: [-0.58, 0.88, 0.08],
        radius: 0.82,
        tone: 'projection',
      },
      {
        id: 'cited-retrieval',
        label: 'Cited Retrieval',
        detail: 'Evidence packets',
        kind: 'system_component',
        state: latticeState,
        position: [0.72, 0.76, -0.24],
        radius: 0.86,
        tone: 'projection',
      },
      {
        id: 'memory-lattice',
        label: 'Memory Lattice',
        detail: 'Typed provenance graph',
        kind: 'system_component',
        state: latticeState,
        position: [0, 0, 0.52],
        radius: 1.32,
        tone: 'memory',
      },
      {
        id: 'temporal-view',
        label: 'Temporal View',
        detail: 'Valid-time projection',
        kind: 'system_component',
        state: latticeState,
        position: [-0.68, -0.86, -0.1],
        radius: 0.72,
        tone: 'projection',
      },
      {
        id: 'contradiction-map',
        label: 'Contradiction Map',
        detail: 'Correction lineage',
        kind: 'system_component',
        state: latticeState,
        position: [0.62, -0.92, 0.18],
        radius: 0.76,
        tone: 'projection',
      },
      {
        id: 'provenance',
        label: 'Provenance',
        detail: 'Source and artifact lineage',
        kind: 'system_component',
        state: latticeState,
        position: [1.36, -0.14, -0.46],
        radius: 0.9,
        tone: 'authority',
      },
    ],
    connections: [
      { id: 'authority-index', source: 'obsidian-authority', target: 'fts-index', kind: 'projection', curvature: 0.24, phase: 0.02 },
      { id: 'authority-temporal', source: 'obsidian-authority', target: 'temporal-view', kind: 'projection', curvature: 0.3, phase: 0.31 },
      { id: 'index-lattice', source: 'fts-index', target: 'memory-lattice', kind: 'projection', curvature: 0.22, phase: 0.58 },
      { id: 'temporal-lattice', source: 'temporal-view', target: 'memory-lattice', kind: 'lineage', curvature: 0.28, phase: 0.78 },
      { id: 'retrieval-lattice', source: 'cited-retrieval', target: 'memory-lattice', kind: 'evidence', curvature: 0.26, phase: 0.18 },
      { id: 'contradiction-lattice', source: 'contradiction-map', target: 'memory-lattice', kind: 'lineage', curvature: 0.32, phase: 0.45 },
      { id: 'provenance-lattice', source: 'provenance', target: 'memory-lattice', kind: 'lineage', curvature: 0.25, phase: 0.67 },
      { id: 'index-retrieval', source: 'fts-index', target: 'cited-retrieval', kind: 'evidence', curvature: 0.34, phase: 0.89 },
      { id: 'contradiction-provenance', source: 'contradiction-map', target: 'provenance', kind: 'lineage', curvature: 0.29, phase: 0.12 },
    ],
  }
}
