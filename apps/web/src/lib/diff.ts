// Graph diff between two revisions' models (P11 "diff the graph, not the image").
import type { DesignModel } from './types'

export type ChangeKind = 'added' | 'removed' | 'changed'
export interface FieldChange {
  field: string
  before: unknown
  after: unknown
}
export interface ElementChange {
  id: string
  collection: 'racks' | 'equipment' | 'connections' | 'cooling_nodes' | 'pipes'
  kind: ChangeKind
  fields: FieldChange[]
}
export interface ModelDiff {
  changes: ElementChange[]
  byId: Map<string, ChangeKind>
}

const FIELDS = {
  racks: ['kw', 'liquid_fraction', 'feeds', 'x', 'y'],
  equipment: ['kind', 'rating', 'unit', 'catalogue_id', 'system'],
  connections: ['kind', 'src', 'dst', 'length_m', 'catalogue_id', 'route'],
  cooling_nodes: ['kind', 'zone', 'capacity_kw', 'x', 'y'],
  pipes: ['dn', 'tier', 'route', 'flow_lps'],
} as const

type Collection = keyof typeof FIELDS
const same = (a: unknown, b: unknown) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null)

export function diffModels(before: DesignModel | null | undefined, after: DesignModel | null | undefined): ModelDiff {
  const changes: ElementChange[] = []
  if (before && after) {
    for (const collection of Object.keys(FIELDS) as Collection[]) {
      const a = new Map((before[collection] as { id: string }[]).map((x) => [x.id, x as unknown as Record<string, unknown>]))
      const b = new Map((after[collection] as { id: string }[]).map((x) => [x.id, x as unknown as Record<string, unknown>]))
      for (const [id, nb] of b) {
        const na = a.get(id)
        if (!na) {
          changes.push({ id, collection, kind: 'added', fields: [] })
          continue
        }
        const fields = FIELDS[collection]
          .filter((f) => !same(na[f], nb[f]))
          .map((f) => ({ field: f, before: na[f], after: nb[f] }))
        if (fields.length) changes.push({ id, collection, kind: 'changed', fields })
      }
      for (const id of a.keys()) if (!b.has(id)) changes.push({ id, collection, kind: 'removed', fields: [] })
    }
  }
  return { changes, byId: new Map(changes.map((c) => [c.id, c.kind])) }
}
