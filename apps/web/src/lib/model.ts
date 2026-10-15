// Element index over a DesignModel: every addressable id (equipment, connections, racks,
// cooling nodes, pipes, zones) with its discipline, for impact chains and click handling.
import type { DesignModel, EquipmentKind } from './types'

export type Discipline = 'electrical' | 'cooling'
export type ElementKind = EquipmentKind | 'feeder' | 'link' | 'pipe' | 'cdu' | 'manifold' | 'rack' | 'zone'

export interface ElementInfo {
  id: string
  kind: ElementKind
  discipline: Discipline
}

const INDEX_CACHE = new WeakMap<DesignModel, Map<string, ElementInfo>>()

/** Memoised per model object (models are immutable once loaded); the matrix asks once per row. */
export function elementIndex(m: DesignModel | null): Map<string, ElementInfo> {
  if (!m) return new Map()
  const cached = INDEX_CACHE.get(m)
  if (cached) return cached
  const idx = new Map<string, ElementInfo>()
  INDEX_CACHE.set(m, idx)
  for (const e of m.equipment) idx.set(e.id, { id: e.id, kind: e.kind, discipline: 'electrical' })
  for (const c of m.connections)
    idx.set(c.id, { id: c.id, kind: c.kind === 'internal' ? 'link' : 'feeder', discipline: 'electrical' })
  for (const r of m.racks) idx.set(r.id, { id: r.id, kind: 'rack', discipline: 'electrical' })
  for (const n of m.cooling_nodes) {
    idx.set(n.id, { id: n.id, kind: n.kind, discipline: 'cooling' })
    if (!idx.has(n.zone)) idx.set(n.zone, { id: n.zone, kind: 'zone', discipline: 'cooling' })
  }
  for (const p of m.pipes) {
    idx.set(p.id, { id: p.id, kind: 'pipe', discipline: 'cooling' })
    if (!idx.has(p.zone)) idx.set(p.zone, { id: p.zone, kind: 'zone', discipline: 'cooling' })
  }
  return idx
}

export type Canvas = 'hall' | 'sld'

/**
 * Which canvases draw `id`: boards, transformers, UPS and internal links are SLD-only; pipes, CDUs,
 * manifolds and zones are 3D-only; racks, routed feeders and busways are on both. An id that is not in
 * the model (R12's "BOQ", R06's "HALL") is drawn on neither, so focusing it never switches to an empty view.
 */
export function canvasesFor(m: DesignModel | null, id: string): Canvas[] {
  const info = elementIndex(m).get(id)
  if (!info) return []
  if (info.discipline === 'cooling') return ['hall']
  if (info.kind === 'rack' || info.kind === 'feeder' || info.kind === 'busway') return ['hall', 'sld']
  return ['sld']
}
