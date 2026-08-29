import type { ArchitectureNodeId } from './memoryApi'

export type FeatureState = 'planned' | 'preview' | 'ready'

export type Point3D = readonly [x: number, y: number, z: number]
export type NeuralTone = 'authority' | 'projection' | 'memory'

export interface FoundationNode {
  id: ArchitectureNodeId
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
  source: ArchitectureNodeId
  target: ArchitectureNodeId
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
        id: 'identity-role',
        label: 'Identity & Role',
        detail: 'Purpose, identity, and operating role',
        kind: 'system_component',
        state: 'ready',
        position: [-1.35, -0.18, -0.58],
        radius: 1.05,
        tone: 'authority',
      },
      {
        id: 'goals-commitments',
        label: 'Goals & Commitments',
        detail: 'Outcomes, promises, and finish lines',
        kind: 'system_component',
        state: latticeState,
        position: [-0.58, 0.88, 0.08],
        radius: 0.82,
        tone: 'projection',
      },
      {
        id: 'projects-work',
        label: 'Projects & Work',
        detail: 'Active work, milestones, and deliverables',
        kind: 'system_component',
        state: latticeState,
        position: [0.72, 0.76, -0.24],
        radius: 0.86,
        tone: 'projection',
      },
      {
        id: 'knowledge-research',
        label: 'Knowledge & Research',
        detail: 'Evidence, concepts, and learned models',
        kind: 'system_component',
        state: latticeState,
        position: [0, 0, 0.52],
        radius: 1.32,
        tone: 'memory',
      },
      {
        id: 'people-relationships',
        label: 'People & Relationships',
        detail: 'People, teams, and interaction context',
        kind: 'system_component',
        state: latticeState,
        position: [-0.68, -0.86, -0.1],
        radius: 0.72,
        tone: 'projection',
      },
      {
        id: 'decisions-lessons',
        label: 'Decisions & Lessons',
        detail: 'Choices, corrections, and outcomes',
        kind: 'system_component',
        state: latticeState,
        position: [0.62, -0.92, 0.18],
        radius: 0.76,
        tone: 'projection',
      },
      {
        id: 'preferences-context',
        label: 'Preferences & Context',
        detail: 'Working style, constraints, and environment',
        kind: 'system_component',
        state: latticeState,
        position: [1.36, -0.14, -0.46],
        radius: 0.9,
        tone: 'authority',
      },
    ],
    connections: [
      { id: 'identity-goals', source: 'identity-role', target: 'goals-commitments', kind: 'lineage', curvature: 0.24, phase: 0.02 },
      { id: 'identity-people', source: 'identity-role', target: 'people-relationships', kind: 'lineage', curvature: 0.3, phase: 0.31 },
      { id: 'goals-knowledge', source: 'goals-commitments', target: 'knowledge-research', kind: 'projection', curvature: 0.22, phase: 0.58 },
      { id: 'people-knowledge', source: 'people-relationships', target: 'knowledge-research', kind: 'evidence', curvature: 0.28, phase: 0.78 },
      { id: 'projects-knowledge', source: 'projects-work', target: 'knowledge-research', kind: 'evidence', curvature: 0.26, phase: 0.18 },
      { id: 'decisions-knowledge', source: 'decisions-lessons', target: 'knowledge-research', kind: 'lineage', curvature: 0.32, phase: 0.45 },
      { id: 'context-knowledge', source: 'preferences-context', target: 'knowledge-research', kind: 'lineage', curvature: 0.25, phase: 0.67 },
      { id: 'goals-projects', source: 'goals-commitments', target: 'projects-work', kind: 'projection', curvature: 0.34, phase: 0.89 },
      { id: 'decisions-context', source: 'decisions-lessons', target: 'preferences-context', kind: 'lineage', curvature: 0.29, phase: 0.12 },
    ],
  }
}
