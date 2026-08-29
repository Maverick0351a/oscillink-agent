export type GraphMode = 'architecture' | 'memory'

export function projectionDensity(mode: GraphMode, width: number) {
  return mode === 'memory' && width < 520 ? 0.22 : 0.34
}

export function shouldDrawNodeLabel(mode: GraphMode, width: number, _highlighted: boolean) {
  return mode === 'architecture' || width >= 520
}
