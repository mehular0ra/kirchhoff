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

export function elementIndex(m: DesignModel | null): Map<string, ElementInfo> {
  const idx = new Map<string, ElementInfo>()
  if (!m) return idx
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
