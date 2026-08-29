export type GraphMode = 'architecture' | 'memory'

export function projectionDensity(mode: GraphMode, width: number) {
  if (mode === 'memory' && width < 520) return 0.22
  if (mode === 'architecture' && width < 560) return 0.28
  return 0.34
}

export function shouldDrawNodeLabel(mode: GraphMode, width: number, _highlighted: boolean) {
  return mode === 'architecture' || width >= 520
}
