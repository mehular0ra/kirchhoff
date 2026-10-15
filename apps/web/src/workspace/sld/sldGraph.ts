// DesignModel → single-line-diagram graph, laid out with ELK "layered" (top-down by level).
import type { ElkNode } from 'elkjs/lib/elk-api'
import { fmtQty } from '@/lib/format'
import { withTimeout } from '@/lib/timeout'
import type { DesignModel, EquipmentKind } from '@/lib/types'

export type SldKind = 'mv' | 'transformer' | 'board' | 'ups' | 'sts' | 'busway' | 'rackgroup'

export interface SldNodeSpec {
  id: string
  kind: SldKind
  label: string
  sub: string
  level: number
  /** Element ids whose findings colour this node (a rack group carries its racks). */
  members: string[]
  /** Feeders that end at this node: edges are mouse-only, so their findings are reached from here by keyboard. */
  feeders: string[]
}
export interface SldEdgeSpec {
  id: string
  source: string
  target: string
  /** Feeder id shown on the edge (null for internal links). */
  label: string | null
}
export interface SldGraph {
  nodes: SldNodeSpec[]
  edges: SldEdgeSpec[]
}

const KIND: Record<EquipmentKind, SldKind> = {
  mv_board: 'mv',
  transformer: 'transformer',
  lv_board: 'board',
  ups: 'ups',
  critical_board: 'board',
  sts: 'sts',
  busway: 'busway',
  rack_group: 'rackgroup',
}

/** Staged reveal order (spec §12): MV → transformers → boards → UPS → critical boards/STS → busways → rack groups. */
export const LEVEL: Record<EquipmentKind, number> = {
  mv_board: 0,
  transformer: 1,
  lv_board: 2,
  ups: 3,
  critical_board: 4,
  sts: 4,
  busway: 5,
  rack_group: 6,
}
export const MAX_LEVEL = 6

export const NODE_SIZE: Record<SldKind, { w: number; h: number }> = {
  mv: { w: 220, h: 64 },
  transformer: { w: 132, h: 76 },
  board: { w: 132, h: 64 },
  ups: { w: 132, h: 64 },
  sts: { w: 120, h: 60 },
  busway: { w: 118, h: 60 },
  rackgroup: { w: 132, h: 64 },
}

export function buildSldGraph(model: DesignModel): SldGraph {
  const nodes: SldNodeSpec[] = model.equipment.map((e) => ({
    id: e.id,
    kind: KIND[e.kind],
    label: e.id,
    sub: [e.rating != null ? fmtQty(e.rating, e.unit) : null, e.catalogue_id].filter(Boolean).join(' · '),
    level: LEVEL[e.kind],
    members: [e.id],
    feeders: [] as string[],
  }))
  const ids = new Set(nodes.map((n) => n.id))
  const edges: SldEdgeSpec[] = model.connections
    .filter((c) => ids.has(c.src) && ids.has(c.dst))
    .map((c) => ({ id: c.id, source: c.src, target: c.dst, label: c.kind === 'internal' ? null : c.id }))
  for (const e of edges) if (e.label) nodes.find((n) => n.id === e.target)?.feeders.push(e.id)

  // Racks grouped per row when the model has no explicit rack_group equipment (spec §12 "racks grouped").
  if (!model.equipment.some((e) => e.kind === 'rack_group')) {
    const rows = new Map<string, DesignModel['racks']>()
    for (const r of model.racks) rows.set(r.row, [...(rows.get(r.row) ?? []), r])
    for (const [row, racks] of rows) {
      const id = `RG:${row}`
      const kws = [...new Set(racks.map((r) => r.kw))]
      nodes.push({
        id,
        kind: 'rackgroup',
        label: `${row} · ${racks.length} racks`,
        sub: kws.length === 1 ? `${fmtQty(kws[0], 'kW')} each` : '',
        level: MAX_LEVEL,
        members: racks.map((r) => r.id),
        feeders: [],
      })
      const feeders = new Set(racks.flatMap((r) => r.feeds))
      for (const busway of feeders) if (ids.has(busway)) edges.push({ id: `${busway}->${id}`, source: busway, target: id, label: null })
    }
  }
  return { nodes, edges }
}

interface ElkLayouter {
  layout(graph: ElkNode): Promise<ElkNode>
}

// ELK is ~1.4 MB: load it only when the SLD tab lays out, and run it in a Web Worker so the layout
// never blocks the main thread (final review I9). Without Worker support (tests, old browsers) or if
// the worker fails, the in-thread bundled build is used instead.
let workerElk: Promise<ElkLayouter> | null = null
let bundledElk: Promise<ElkLayouter> | null = null

function inThreadElk(): Promise<ElkLayouter> {
  bundledElk ??= import('elkjs/lib/elk.bundled.js').then(({ default: ELK }) => new ELK())
  return bundledElk
}

function elk(): Promise<ElkLayouter> {
  if (typeof Worker === 'undefined') return inThreadElk()
  workerElk ??= Promise.all([import('elkjs/lib/elk-api.js'), import('elkjs/lib/elk-worker.min.js?url')]).then(
    ([{ default: ELK }, { default: workerUrl }]) => new ELK({ workerUrl }),
  )
  return workerElk
}

export async function layoutSld(g: SldGraph): Promise<Map<string, { x: number; y: number }>> {
  const graph: ElkNode = {
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': 'DOWN',
      'elk.edgeRouting': 'ORTHOGONAL',
      'elk.partitioning.activate': 'true',
      // Compact spacing so the first fit renders node text at a readable size (M11).
      'elk.layered.spacing.nodeNodeBetweenLayers': '40',
      'elk.spacing.nodeNode': '12',
      'elk.layered.nodePlacement.strategy': 'BRANDES_KOEPF',
    },
    children: g.nodes.map((n) => ({
      id: n.id,
      width: NODE_SIZE[n.kind].w,
      height: NODE_SIZE[n.kind].h,
      layoutOptions: { 'elk.partitioning.partition': String(n.level) },
    })),
    edges: g.edges.map((e) => ({ id: e.id, sources: [e.source], targets: [e.target] })),
  }
  let res: ElkNode
  try {
    res = await withTimeout((await elk()).layout(graph), 20_000, () => new Error('ELK worker did not answer'))
  } catch {
    workerElk = null
    res = await (await inThreadElk()).layout(graph)
  }
  return new Map((res.children ?? []).map((c) => [c.id, { x: c.x ?? 0, y: c.y ?? 0 }]))
}
