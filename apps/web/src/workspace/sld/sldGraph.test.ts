import { fixtureBundle } from '@/test/fixtures'
import { buildSldGraph, layoutSld } from './sldGraph'

test('SLD graph has a node for every equipment item plus one rack group per row', () => {
  const model = fixtureBundle().revisions[0].model!
  const g = buildSldGraph(model)
  const ids = g.nodes.map((n) => n.id)
  for (const e of model.equipment) expect(ids).toContain(e.id)
  expect(ids).toContain('RG:R1')
  const rg = g.nodes.find((n) => n.id === 'RG:R1')!
  expect(rg.label).toBe('R1 · 4 racks')
  expect(rg.sub).toBe('132 kW each')
  expect(rg.members).toEqual(['R1-01', 'R1-02', 'R1-03', 'R1-04'])
  expect(g.nodes.find((n) => n.id === 'T-A1')?.sub).toBe('3,150 kVA · TX-3150')
  expect(g.edges.find((e) => e.id === 'FA-01')).toEqual({ id: 'FA-01', source: 'CB-A1', target: 'A-01', label: 'FA-01' })
  expect(g.edges.find((e) => e.id === 'L-MV-TA1')?.label).toBeNull()
  expect(g.edges.filter((e) => e.target === 'RG:R1').map((e) => e.source).sort()).toEqual(['A-01', 'B-01'])
})

test('ELK lays out every node, top-down by level', async () => {
  const g = buildSldGraph(fixtureBundle().revisions[0].model!)
  const pos = await layoutSld(g)
  expect(pos.size).toBe(g.nodes.length)
  const y = (id: string) => pos.get(id)!.y
  expect(y('MV')).toBeLessThan(y('T-A1'))
  expect(y('T-A1')).toBeLessThan(y('A1'))
  expect(y('A1')).toBeLessThan(y('UPS-A1'))
  expect(y('CB-A1')).toBeLessThan(y('A-01'))
  expect(y('A-01')).toBeLessThan(y('RG:R1'))
})
