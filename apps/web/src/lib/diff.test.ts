import { fixtureBundle } from '@/test/fixtures'
import { diffModels } from './diff'
import { chainHighlights, classifyChain } from './impact'
import { elementIndex } from './model'

test('diff between r1 and r2 finds the two fixed elements and nothing else', () => {
  const [r1, r2] = fixtureBundle().revisions
  const d = diffModels(r1.model, r2.model)
  expect([...d.byId.entries()].sort()).toEqual([
    ['FA-01', 'changed'],
    ['H-Z2', 'changed'],
  ])
  const fa = d.changes.find((c) => c.id === 'FA-01')!
  expect(fa.fields.map((f) => f.field)).toEqual(['kind', 'catalogue_id'])
  expect(fa.fields[1]).toEqual({ field: 'catalogue_id', before: 'BW-1600', after: 'CBL-8x240' })
})

test('diff reports added and removed elements', () => {
  const [r1] = fixtureBundle().revisions
  const after = structuredClone(r1.model!)
  after.equipment = after.equipment.filter((e) => e.id !== 'B-01')
  after.cooling_nodes.push({ id: 'CDU-2', kind: 'cdu', zone: 'Z2', capacity_kw: 1200, x: 10, y: 30 })
  const d = diffModels(r1.model, after)
  expect(d.byId.get('B-01')).toBe('removed')
  expect(d.byId.get('CDU-2')).toBe('added')
})

test('element index covers equipment, feeders, racks, cooling and zones', () => {
  const idx = elementIndex(fixtureBundle().revisions[0].model!)
  expect(idx.get('T-A1')).toEqual({ id: 'T-A1', kind: 'transformer', discipline: 'electrical' })
  expect(idx.get('FA-01')?.kind).toBe('feeder')
  expect(idx.get('L-MV-TA1')?.kind).toBe('link')
  expect(idx.get('H-Z2')?.discipline).toBe('cooling')
  expect(idx.get('Z2')).toEqual({ id: 'Z2', kind: 'zone', discipline: 'cooling' })
})

test('impact chains are split into electrical and cooling', () => {
  const b = fixtureBundle()
  const m = b.revisions[1].model!
  const w = b.what_ifs[0]
  expect(classifyChain(w.impact_chain[0], m)).toBe('electrical')
  expect(classifyChain(w.impact_chain[1], m)).toBe('cooling')
  const h = chainHighlights(w, m)
  expect(h.get('T-A1')).toEqual(['electrical'])
  expect(h.get('CDU-1')).toEqual(['cooling'])
  expect(h.get('R1-01')).toEqual(['electrical', 'cooling'])
})
