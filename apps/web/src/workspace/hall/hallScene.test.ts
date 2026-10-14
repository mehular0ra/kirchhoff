import { fixtureBundle } from '@/test/fixtures'
import { buildHallScene, crossingPoint, resample } from './hallScene'

const r1 = () => fixtureBundle().revisions[0].model!

test('scene has one instanced rack per model rack, columns, keep-out and rooms', () => {
  const s = buildHallScene(r1())
  expect(s.racks.map((r) => r.id)).toEqual(['R1-01', 'R1-02', 'R1-03', 'R1-04'])
  expect(s.racks[0].size).toEqual([1.2, 0.6, 2.2])
  expect(s.columns).toHaveLength(4)
  expect(s.keepouts[0]).toMatchObject({ center: [14, 18, 1.5], size: [8, 16, 3] })
  expect(s.rooms.map((r) => r.label)).toEqual(['LV room A', 'LV room B'])
  expect(s.bays).toHaveLength(1)
})

test('feeders, row busways and pipes become tubes on their tiers', () => {
  const s = buildHallScene(r1())
  const byId = new Map(s.tubes.map((t) => [t.id, t]))
  expect(byId.get('FA-01')?.kind).toBe('busway-feeder')
  expect(byId.get('FA-01')?.points.every((p) => p[2] === 3.2)).toBe(true)
  expect(byId.get('A-01')).toMatchObject({ kind: 'row-busway', points: [[5.7, 15.6, 3.2], [5.7, 18, 3.2]] })
  expect(byId.get('B-01')?.points[0][0]).toBeCloseTo(6.3)
  expect(byId.get('H-Z2')).toMatchObject({ kind: 'pipe', discipline: 'cooling' })
  expect(byId.get('H-Z2')?.points[0][2]).toBe(3.8)
  expect(byId.get('BR-R1')?.points[0][2]).toBe(2.6)
  expect(byId.has('L-MV-TA1')).toBe(false)
})

test('the R11 crossing is found in plan at the pipe height', () => {
  const s = buildHallScene(r1())
  const t = new Map(s.tubes.map((x) => [x.id, x.points]))
  expect(crossingPoint(t.get('H-Z2')!, t.get('FB-03')!)).toEqual([6.3, 24, 3.8])
  expect(crossingPoint(t.get('BR-R1')!, t.get('FB-03')!)).toBeNull()
})

test('resample keeps endpoints and spacing', () => {
  const pts = resample(
    [
      [0, 0, 0],
      [10, 0, 0],
    ],
    5,
  )
  expect(pts.map((p) => p[0])).toEqual([0, 2.5, 5, 7.5, 10])
})
