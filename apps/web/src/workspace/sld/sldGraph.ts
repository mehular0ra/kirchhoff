// DesignModel → single-line-diagram graph, laid out with ELK "layered" (top-down by level).
import ELK from 'elkjs/lib/elk.bundled.js'
import { fmtQty } from '@/lib/format'
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
  busway: { w: 120, h: 60 },
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
  }))
  const ids = new Set(nodes.map((n) => n.id))
  const edges: SldEdgeSpec[] = model.connections
    .filter((c) => ids.has(c.src) && ids.has(c.dst))
    .map((c) => ({ id: c.id, source: c.src, target: c.dst, label: c.kind === 'internal' ? null : c.id }))

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
      })
      const feeders = new Set(racks.flatMap((r) => r.feeds))
      for (const busway of feeders) if (ids.has(busway)) edges.push({ id: `${busway}->${id}`, source: busway, target: id, label: null })
    }
  }
  return { nodes, edges }
}

const elk = new ELK()

export async function layoutSld(g: SldGraph): Promise<Map<string, { x: number; y: number }>> {
  const res = await elk.layout({
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': 'DOWN',
      'elk.edgeRouting': 'ORTHOGONAL',
      'elk.partitioning.activate': 'true',
      'elk.layered.spacing.nodeNodeBetweenLayers': '56',
      'elk.spacing.nodeNode': '28',
      'elk.layered.nodePlacement.strategy': 'BRANDES_KOEPF',
    },
    children: g.nodes.map((n) => ({
      id: n.id,
      width: NODE_SIZE[n.kind].w,
      height: NODE_SIZE[n.kind].h,
      layoutOptions: { 'elk.partitioning.partition': String(n.level) },
    })),
    edges: g.edges.map((e) => ({ id: e.id, sources: [e.source], targets: [e.target] })),
  })
  return new Map((res.children ?? []).map((c) => [c.id, { x: c.x ?? 0, y: c.y ?? 0 }]))
}
