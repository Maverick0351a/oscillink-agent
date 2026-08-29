import { useEffect, useMemo, useRef, type CSSProperties } from 'react'

import {
  buildFoundationGraph,
  type FeatureState,
  type NeuralTone,
  type Point3D,
} from './foundationGraph'
import type { ArchitectureNodeId, CategoryLegendEntry, MemoryNodeSummary } from './memoryApi'
import {
  projectionDensity,
  shouldDrawNodeLabel,
  type GraphMode,
} from './memoryGraphLayout'

interface MemoryGraphProps {
  latticeState: FeatureState
  mode?: GraphMode
  nodes?: MemoryNodeSummary[]
  categories?: CategoryLegendEntry[]
  selectedId?: string | null
  selectedLinks?: string[]
  activeRetrievalNodeIds?: ArchitectureNodeId[]
  onSelect?: (nodeId: string) => void
}

interface Rotation {
  yaw: number
  pitch: number
}

interface ProjectedPoint {
  x: number
  y: number
  depth: number
  scale: number
}

interface ProjectedNode extends ProjectedPoint {
  node: VisualNode
  radius: number
}

interface Palette {
  core: string
  bright: string
  dark: string
  glow: string
}

const RETRIEVAL_PALETTE: Palette = {
  core: '#ff9d3f',
  bright: '#ffe0a3',
  dark: '#3c1c08',
  glow: 'rgba(255, 145, 48, 0.94)',
}

interface VisualNode {
  id: string
  label: string
  detail: string
  state: FeatureState
  position: Point3D
  radius: number
  palette: Palette
}

interface VisualConnection {
  id: string
  source: string
  target: string
  kind: 'projection' | 'lineage' | 'evidence' | 'exact'
  curvature: number
  phase: number
}

interface VisualGraph {
  nodes: VisualNode[]
  connections: VisualConnection[]
}

const PALETTES: Record<NeuralTone, Palette> = {
  authority: {
    core: '#36f1cd',
    bright: '#e8fffa',
    dark: '#064a43',
    glow: 'rgba(54, 241, 205, 0.62)',
  },
  projection: {
    core: '#45aab5',
    bright: '#b8fbff',
    dark: '#082d38',
    glow: 'rgba(69, 170, 181, 0.52)',
  },
  memory: {
    core: '#ff4fd8',
    bright: '#ffe8fb',
    dark: '#511147',
    glow: 'rgba(255, 79, 216, 0.65)',
  },
}

const MONO_FONT = '"Cascadia Code", "SFMono-Regular", Consolas, monospace'

function paletteFromHex(color: string): Palette {
  const match = color.match(/^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i)
  if (match === null) return PALETTES.projection
  const red = Number.parseInt(match[1] ?? '93', 16)
  const green = Number.parseInt(match[2] ?? 'a4', 16)
  const blue = Number.parseInt(match[3] ?? 'ad', 16)
  return {
    core: color,
    bright: `rgb(${Math.min(255, red + 95)} ${Math.min(255, green + 95)} ${Math.min(255, blue + 95)})`,
    dark: `rgb(${Math.round(red * 0.24)} ${Math.round(green * 0.24)} ${Math.round(blue * 0.24)})`,
    glow: `rgb(${red} ${green} ${blue} / 62%)`,
  }
}

function stableFraction(value: string, salt: number): number {
  let hash = 2166136261 ^ salt
  for (const character of value) {
    hash ^= character.charCodeAt(0)
    hash = Math.imul(hash, 16777619)
  }
  return (hash >>> 0) / 4294967295
}

function memoryPosition(nodeId: string): Point3D {
  const angle = stableFraction(nodeId, 17) * Math.PI * 2
  const z = stableFraction(nodeId, 71) * 1.45 - 0.725
  const radius = Math.sqrt(Math.max(0.2, 1 - z * z)) * 1.45
  return [Math.cos(angle) * radius, Math.sin(angle) * radius, z]
}

function normalizeWikiTarget(value: string): string {
  return value.replaceAll('\\', '/').replace(/\.md$/i, '').toLocaleLowerCase()
}

function buildVisualGraph(
  mode: 'architecture' | 'memory',
  latticeState: FeatureState,
  nodes: MemoryNodeSummary[],
  categories: CategoryLegendEntry[],
  selectedId: string | null,
  selectedLinks: string[],
): VisualGraph {
  if (mode === 'architecture') {
    const foundation = buildFoundationGraph(latticeState)
    const associationCounts = new Map<string, number>()
    for (const memory of nodes) {
      for (const architectureNodeId of memory.architecture_node_ids) {
        associationCounts.set(
          architectureNodeId,
          (associationCounts.get(architectureNodeId) ?? 0) + 1,
        )
      }
    }
    return {
      nodes: foundation.nodes.map((node) => ({
        ...node,
        detail: `${node.detail} · ${associationCounts.get(node.id) ?? 0} memory`,
        palette: PALETTES[node.tone],
      })),
      connections: foundation.connections,
    }
  }

  const categoryById = new Map(categories.map((entry) => [entry.category, entry] as const))
  const visualNodes = nodes.map((node) => {
    const category = categoryById.get(node.category)
    return {
      id: node.id,
      label: node.title,
      detail: category?.label ?? node.category,
      state: 'ready' as const,
      position: memoryPosition(node.id),
      radius: 0.92 + Math.min(node.wikilink_count, 4) * 0.08,
      palette: paletteFromHex(category?.color ?? '#93a4ad'),
    }
  })
  const source = nodes.find((node) => node.id === selectedId)
  const targetByPath = new Map(
    nodes
      .filter((node) => node.source_path !== null)
      .map((node) => [normalizeWikiTarget(node.source_path ?? ''), node] as const),
  )
  const exactTargets = source === undefined
    ? []
    : selectedLinks
        .map((target) => targetByPath.get(normalizeWikiTarget(target)))
        .filter((target): target is MemoryNodeSummary => target !== undefined && target.id !== source.id)

  return {
    nodes: visualNodes,
    connections: exactTargets.map((target, index) => ({
      id: `${source?.id ?? 'none'}-${target.id}`,
      source: source?.id ?? '',
      target: target.id,
      kind: 'exact',
      curvature: 0.22 + index * 0.04,
      phase: stableFraction(target.id, 131),
    })),
  }
}

function rotatePoint([x, y, z]: Point3D, rotation: Rotation): Point3D {
  const cosYaw = Math.cos(rotation.yaw)
  const sinYaw = Math.sin(rotation.yaw)
  const yawX = x * cosYaw - z * sinYaw
  const yawZ = x * sinYaw + z * cosYaw
  const cosPitch = Math.cos(rotation.pitch)
  const sinPitch = Math.sin(rotation.pitch)

  return [yawX, y * cosPitch - yawZ * sinPitch, y * sinPitch + yawZ * cosPitch]
}

function projectPoint(
  point: Point3D,
  rotation: Rotation,
  width: number,
  height: number,
  zoom: number,
  density: number,
): ProjectedPoint {
  const [x, y, z] = rotatePoint(point, rotation)
  const cameraDistance = 4.4
  const scale = cameraDistance / (cameraDistance - z)
  const fieldScale = Math.min(width, height) * density * zoom

  return {
    x: width / 2 + x * fieldScale * scale,
    y: height / 2 + y * fieldScale * scale,
    depth: z,
    scale,
  }
}

function connectionControl(
  source: Point3D,
  target: Point3D,
  connection: VisualConnection,
): Point3D {
  const dx = target[0] - source[0]
  const dy = target[1] - source[1]
  const planarLength = Math.hypot(dx, dy) || 1
  const direction = connection.kind === 'lineage' ? 1 : -1

  return [
    (source[0] + target[0]) / 2 - (dy / planarLength) * connection.curvature,
    (source[1] + target[1]) / 2 + (dx / planarLength) * connection.curvature,
    (source[2] + target[2]) / 2 + connection.curvature * 0.85 * direction,
  ]
}

function quadraticPoint(source: Point3D, control: Point3D, target: Point3D, t: number): Point3D {
  const inverse = 1 - t
  return [
    inverse * inverse * source[0] + 2 * inverse * t * control[0] + t * t * target[0],
    inverse * inverse * source[1] + 2 * inverse * t * control[1] + t * t * target[1],
    inverse * inverse * source[2] + 2 * inverse * t * control[2] + t * t * target[2],
  ]
}

function drawSynapse(
  context: CanvasRenderingContext2D,
  source: VisualNode,
  target: VisualNode,
  connection: VisualConnection,
  rotation: Rotation,
  width: number,
  height: number,
  zoom: number,
  density: number,
  time: number,
) {
  const control = connectionControl(source.position, target.position, connection)
  const points: ProjectedPoint[] = []

  for (let step = 0; step <= 24; step += 1) {
    points.push(
      projectPoint(
        quadraticPoint(source.position, control, target.position, step / 24),
        rotation,
        width,
        height,
        zoom,
        density,
      ),
    )
  }

  const first = points[0]
  const last = points[points.length - 1]
  if (first === undefined || last === undefined) return

  const trace = () => {
    context.beginPath()
    context.moveTo(first.x, first.y)
    for (const point of points.slice(1)) context.lineTo(point.x, point.y)
  }

  context.save()
  context.lineCap = 'round'
  context.lineJoin = 'round'

  trace()
  context.strokeStyle = 'rgba(54, 241, 205, 0.1)'
  context.lineWidth = 7
  context.shadowColor = 'rgba(54, 241, 205, 0.45)'
  context.shadowBlur = 13
  context.stroke()

  const gradient = context.createLinearGradient(first.x, first.y, last.x, last.y)
  gradient.addColorStop(0, connection.kind === 'lineage' ? 'rgba(255, 79, 216, 0.38)' : 'rgba(54, 241, 205, 0.34)')
  gradient.addColorStop(0.5, 'rgba(138, 255, 234, 0.78)')
  gradient.addColorStop(1, 'rgba(69, 170, 181, 0.28)')
  trace()
  context.strokeStyle = gradient
  context.lineWidth = 1.25
  context.shadowBlur = 5
  context.stroke()

  const pulseProgress = (time * 0.000085 + connection.phase) % 1
  for (let trail = 0; trail < 4; trail += 1) {
    const t = Math.max(0, pulseProgress - trail * 0.018)
    const pulse = projectPoint(
      quadraticPoint(source.position, control, target.position, t),
      rotation,
      width,
      height,
      zoom,
      density,
    )
    const radius = Math.max(0.7, (2.5 - trail * 0.45) * pulse.scale)
    context.beginPath()
    context.arc(pulse.x, pulse.y, radius, 0, Math.PI * 2)
    context.fillStyle = trail === 0 ? '#d8fff8' : `rgba(54, 241, 205, ${0.42 - trail * 0.09})`
    context.shadowColor = '#36f1cd'
    context.shadowBlur = trail === 0 ? 12 : 5
    context.fill()
  }

  context.restore()
}

function drawNeuron(
  context: CanvasRenderingContext2D,
  projected: ProjectedNode,
  highlighted: boolean,
  showLabel: boolean,
) {
  const { node, x, y, radius, scale } = projected
  const palette = node.palette
  const readiness = node.state === 'ready' ? 1 : 0.64

  context.save()
  context.globalAlpha = readiness

  context.beginPath()
  context.arc(x, y, radius * 1.65, 0, Math.PI * 2)
  context.strokeStyle = palette.glow
  context.lineWidth = highlighted ? 1.4 : 0.65
  context.shadowColor = palette.glow
  context.shadowBlur = highlighted ? 24 : 14
  context.stroke()

  const sphere = context.createRadialGradient(
    x - radius * 0.38,
    y - radius * 0.42,
    radius * 0.08,
    x,
    y,
    radius,
  )
  sphere.addColorStop(0, palette.bright)
  sphere.addColorStop(0.2, palette.core)
  sphere.addColorStop(0.7, palette.dark)
  sphere.addColorStop(1, '#03070b')
  context.beginPath()
  context.arc(x, y, radius, 0, Math.PI * 2)
  context.fillStyle = sphere
  context.shadowColor = palette.glow
  context.shadowBlur = highlighted ? 27 : 18
  context.fill()

  context.beginPath()
  context.arc(x - radius * 0.31, y - radius * 0.34, Math.max(1.2, radius * 0.12), 0, Math.PI * 2)
  context.fillStyle = 'rgba(255, 255, 255, 0.88)'
  context.shadowColor = '#ffffff'
  context.shadowBlur = 8
  context.fill()

  for (let satellite = 0; satellite < 3; satellite += 1) {
    const angle = satellite * (Math.PI * 2 / 3) + node.position[2]
    const orbit = radius * 1.34
    const satelliteX = x + Math.cos(angle) * orbit
    const satelliteY = y + Math.sin(angle) * orbit
    context.beginPath()
    context.moveTo(x + Math.cos(angle) * radius, y + Math.sin(angle) * radius)
    context.lineTo(satelliteX, satelliteY)
    context.strokeStyle = palette.glow
    context.lineWidth = 0.7
    context.stroke()
    context.beginPath()
    context.arc(satelliteX, satelliteY, Math.max(1, radius * 0.07), 0, Math.PI * 2)
    context.fillStyle = palette.bright
    context.fill()
  }

  if (showLabel) {
    const fontSize = Math.max(8, Math.min(11, 9.2 * scale))
    context.globalAlpha = highlighted ? 1 : Math.max(0.68, readiness)
    context.font = `600 ${fontSize}px ${MONO_FONT}`
    context.textAlign = 'center'
    context.textBaseline = 'top'
    context.fillStyle = highlighted ? palette.bright : '#a8b7bd'
    context.shadowColor = '#03070b'
    context.shadowBlur = 5
    context.fillText(node.label.toUpperCase(), x, y + radius + 11)

    if (highlighted) {
      context.font = `500 7px ${MONO_FONT}`
      context.fillStyle = '#ff8ae5'
      context.fillText(node.detail.toUpperCase(), x, y + radius + 26)
    }
  }

  context.restore()
}

export default function MemoryGraph({
  latticeState,
  mode = 'architecture',
  nodes = [],
  categories = [],
  selectedId = null,
  selectedLinks = [],
  activeRetrievalNodeIds = [],
  onSelect,
}: MemoryGraphProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const graph = useMemo(
    () => buildVisualGraph(mode, latticeState, nodes, categories, selectedId, selectedLinks),
    [categories, latticeState, mode, nodes, selectedId, selectedLinks],
  )
  const categoryById = useMemo(
    () => new Map(categories.map((entry) => [entry.category, entry] as const)),
    [categories],
  )
  const architectureAssociationCount = useMemo(
    () => nodes.reduce((total, node) => total + node.architecture_node_ids.length, 0),
    [nodes],
  )

  useEffect(() => {
    const canvas = canvasRef.current
    if (canvas === null) return
    const initialBounds = canvas.getBoundingClientRect()
    if (initialBounds.width === 0 || initialBounds.height === 0) return
    const context = canvas.getContext('2d')
    if (context === null) return

    const rotation: Rotation = { yaw: -0.38, pitch: -0.18 }
    const drag = { active: false, moved: false, x: 0, y: 0 }
    const nodeById = new Map(graph.nodes.map((node) => [node.id, node] as const))
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    let width = initialBounds.width
    let height = initialBounds.height
    let zoom = 1
    let hoveredId: string | null = null
    let projectedNodes: ProjectedNode[] = []
    let animationFrame: number | null = null
    let previousTime = performance.now()

    const stars = Array.from({ length: 46 }, (_, index) => ({
      x: (Math.sin(index * 47.13) + 1) / 2,
      y: (Math.cos(index * 31.71) + 1) / 2,
      size: 0.35 + ((index * 17) % 9) / 12,
      phase: index * 0.37,
    }))

    const resize = () => {
      const bounds = canvas.getBoundingClientRect()
      width = Math.max(1, bounds.width)
      height = Math.max(1, bounds.height)
      const pixelRatio = Math.min(window.devicePixelRatio || 1, 2)
      canvas.width = Math.round(width * pixelRatio)
      canvas.height = Math.round(height * pixelRatio)
      context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0)
      draw(performance.now())
    }

    const draw = (time: number) => {
      context.clearRect(0, 0, width, height)
      const density = projectionDensity(mode, width)

      context.save()
      for (const star of stars) {
        const shimmer = reducedMotion ? 0.28 : 0.2 + Math.sin(time * 0.00045 + star.phase) * 0.1
        context.beginPath()
        context.arc(star.x * width, star.y * height, star.size, 0, Math.PI * 2)
        context.fillStyle = `rgba(138, 255, 234, ${Math.max(0.06, shimmer)})`
        context.fill()
      }
      context.restore()

      for (const connection of graph.connections) {
        const source = nodeById.get(connection.source)
        const target = nodeById.get(connection.target)
        if (source !== undefined && target !== undefined) {
          drawSynapse(context, source, target, connection, rotation, width, height, zoom, density, time)
        }
      }

      projectedNodes = graph.nodes
        .map((node) => {
          const projected = projectPoint(node.position, rotation, width, height, zoom, density)
          return {
            ...projected,
            node,
            radius: (11 + node.radius * 7.5) * projected.scale,
          }
        })
        .sort((left, right) => left.depth - right.depth)

      for (const node of projectedNodes) {
        const highlighted = node.node.id === hoveredId || node.node.id === selectedId
        const retrievalActive = activeRetrievalNodeIds.includes(node.node.id as ArchitectureNodeId)
        drawNeuron(
          context,
          retrievalActive ? { ...node, node: { ...node.node, palette: RETRIEVAL_PALETTE } } : node,
          highlighted || retrievalActive,
          shouldDrawNodeLabel(mode, width, highlighted || retrievalActive),
        )
      }
    }

    const requestStaticDraw = () => {
      if (reducedMotion) draw(performance.now())
    }

    const tick = (time: number) => {
      const elapsed = Math.min(48, time - previousTime)
      previousTime = time
      if (!drag.active) rotation.yaw += elapsed * 0.000035
      draw(time)
      animationFrame = window.requestAnimationFrame(tick)
    }

    const pointerPosition = (event: MouseEvent | PointerEvent) => {
      const bounds = canvas.getBoundingClientRect()
      return { x: event.clientX - bounds.left, y: event.clientY - bounds.top }
    }

    const handlePointerDown = (event: PointerEvent) => {
      const pointer = pointerPosition(event)
      drag.active = true
      drag.moved = false
      drag.x = pointer.x
      drag.y = pointer.y
      canvas.setPointerCapture(event.pointerId)
      canvas.classList.add('is-orbiting')
    }

    const handlePointerMove = (event: PointerEvent) => {
      const pointer = pointerPosition(event)
      if (drag.active) {
        if (Math.hypot(pointer.x - drag.x, pointer.y - drag.y) > 3) drag.moved = true
        rotation.yaw += (pointer.x - drag.x) * 0.007
        rotation.pitch = Math.max(-1.05, Math.min(1.05, rotation.pitch + (pointer.y - drag.y) * 0.006))
        drag.x = pointer.x
        drag.y = pointer.y
        requestStaticDraw()
        return
      }

      const hovered = [...projectedNodes]
        .reverse()
        .find((node) => Math.hypot(pointer.x - node.x, pointer.y - node.y) <= node.radius + 8)
      const nextHoveredId = hovered?.node.id ?? null
      if (nextHoveredId !== hoveredId) {
        hoveredId = nextHoveredId
        canvas.classList.toggle('has-node-hover', hoveredId !== null)
        requestStaticDraw()
      }
    }

    const stopOrbit = (event: PointerEvent) => {
      drag.active = false
      canvas.releasePointerCapture(event.pointerId)
      canvas.classList.remove('is-orbiting')
    }

    const handleWheel = (event: WheelEvent) => {
      event.preventDefault()
      zoom = Math.max(0.72, Math.min(1.38, zoom - event.deltaY * 0.0007))
      requestStaticDraw()
    }

    const handleClick = (event: MouseEvent) => {
      if (drag.moved) return
      const pointer = pointerPosition(event)
      const selected = [...projectedNodes]
        .reverse()
        .find((node) => Math.hypot(pointer.x - node.x, pointer.y - node.y) <= node.radius + 8)
      if (selected !== undefined) onSelect?.(selected.node.id)
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      const step = 0.1
      if (event.key === 'ArrowLeft') rotation.yaw -= step
      else if (event.key === 'ArrowRight') rotation.yaw += step
      else if (event.key === 'ArrowUp') rotation.pitch = Math.max(-1.05, rotation.pitch - step)
      else if (event.key === 'ArrowDown') rotation.pitch = Math.min(1.05, rotation.pitch + step)
      else if (event.key === '+' || event.key === '=') zoom = Math.min(1.38, zoom + 0.08)
      else if (event.key === '-') zoom = Math.max(0.72, zoom - 0.08)
      else return
      event.preventDefault()
      requestStaticDraw()
    }

    canvas.addEventListener('pointerdown', handlePointerDown)
    canvas.addEventListener('pointermove', handlePointerMove)
    canvas.addEventListener('pointerup', stopOrbit)
    canvas.addEventListener('pointercancel', stopOrbit)
    canvas.addEventListener('wheel', handleWheel, { passive: false })
    canvas.addEventListener('click', handleClick)
    canvas.addEventListener('keydown', handleKeyDown)
    window.addEventListener('resize', resize)
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(resize)
    observer?.observe(canvas)

    resize()
    if (!reducedMotion) animationFrame = window.requestAnimationFrame(tick)

    return () => {
      if (animationFrame !== null) window.cancelAnimationFrame(animationFrame)
      observer?.disconnect()
      window.removeEventListener('resize', resize)
      canvas.removeEventListener('pointerdown', handlePointerDown)
      canvas.removeEventListener('pointermove', handlePointerMove)
      canvas.removeEventListener('pointerup', stopOrbit)
      canvas.removeEventListener('pointercancel', stopOrbit)
      canvas.removeEventListener('wheel', handleWheel)
      canvas.removeEventListener('click', handleClick)
      canvas.removeEventListener('keydown', handleKeyDown)
    }
  }, [activeRetrievalNodeIds, graph, onSelect, selectedId])

  const isMemory = mode === 'memory'
  const instructionId = isMemory ? 'product-memory-graph-instructions' : 'neural-graph-instructions'

  return (
    <div className="memory-graph-frame">
      <div className="neural-field-vignette" aria-hidden="true" />
      <div className="graph-orbit-hint" aria-hidden="true">
        <span>DRAG TO ORBIT</span>
        <i>SCROLL TO FOCUS</i>
      </div>
      <div className="graph-classification">
        {isMemory
          ? `PRODUCT MEMORY · ${nodes.length} ${nodes.length === 1 ? 'RECORD' : 'RECORDS'}`
          : `ARCHITECTURE MEMORY · ${architectureAssociationCount} ${architectureAssociationCount === 1 ? 'ASSOCIATION' : 'ASSOCIATIONS'}`}
      </div>
      <canvas
        ref={canvasRef}
        className="memory-graph-canvas"
        role="img"
        aria-label={isMemory ? 'Product memory lattice' : 'System architecture memory map'}
        aria-describedby={instructionId}
        data-renderer="projected-3d-neural"
        tabIndex={0}
      />
      <p id={instructionId} className="sr-only">
        {isMemory
          ? `${nodes.length} product memory records in a projected three-dimensional field. Only exact wikilinks from the focused record are drawn. Drag or use arrow keys to orbit. Scroll or use plus and minus to zoom.`
          : 'Seven memory containers connected by curved synapses in a projected three-dimensional architecture. Select a container to inspect its explicitly associated memory. Drag or use arrow keys to orbit. Scroll or use plus and minus to zoom.'}
      </p>
      {isMemory ? (
        <ul className="memory-node-roster" aria-label="Product memory records">
          {nodes.map((node) => {
            const category = categoryById.get(node.category)
            return (
              <li key={node.id}>
                <button
                  type="button"
                  aria-label={`Focus ${node.title}, ${category?.label ?? node.category}`}
                  aria-pressed={node.id === selectedId}
                  onClick={() => onSelect?.(node.id)}
                  style={{ '--category-color': category?.color ?? '#93a4ad' } as CSSProperties}
                >
                  <span aria-hidden="true">{category?.symbol ?? '?'}</span>
                  <i>{node.title}</i>
                </button>
              </li>
            )
          })}
        </ul>
      ) : (
        <ul className="sr-only" aria-label="Architecture memory containers">
          {graph.nodes.map((node) => {
            const count = nodes.filter((memory) => memory.architecture_node_ids.includes(node.id as never)).length
            return (
              <li key={node.id}>
                <button
                  type="button"
                  aria-label={`Inspect ${node.label}, ${count} associated memory ${count === 1 ? 'record' : 'records'}`}
                  aria-pressed={node.id === selectedId}
                  onClick={() => onSelect?.(node.id)}
                >
                  {node.label}: {node.detail}. State {node.state}.
                  {activeRetrievalNodeIds.includes(node.id as ArchitectureNodeId) ? ' Active agent retrieval.' : ''}
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
