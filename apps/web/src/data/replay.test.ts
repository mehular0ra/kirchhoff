import { fixtureBundle } from '@/test/fixtures'
import { createReplay, frameAt } from './replay'

test('frame 0 shows nothing recorded yet', () => {
  const f = frameAt(fixtureBundle(), 0)
  expect(f.events).toEqual([])
  expect(f.revisions).toEqual([])
  expect(f.brief).toBeNull()
  expect(f.runs[0].status).toBe('running')
  expect(f.approvals).toEqual([])
})

test('revisions and findings appear as their events play', () => {
  const full = fixtureBundle()
  const f = frameAt(full, 16) // through seq 16: revision r1 artifact + first finding
  expect(f.brief).not.toBeNull()
  expect((f.runs[0].options ?? []).map((o) => o.id)).toEqual(['2N', 'DR'])
  expect(f.revisions.map((r) => r.id)).toEqual(['r1'])
  expect(f.findings.r1.map((x) => x.id)).toEqual(['R05:FA-01'])
  expect(f.steps.find((s) => s.id === 'p3.check')?.status).toBe('running')
})

test('the final frame is the recorded bundle', () => {
  const full = fixtureBundle()
  expect(frameAt(full, full.events.length)).toBe(full)
})

test('createReplay plays events on a compressed timer and reports elapsed recorded time', () => {
  vi.useFakeTimers()
  const full = fixtureBundle()
  const frames: number[] = []
  const c = createReplay(full, { speed: 1000, onFrame: (_b, s) => frames.push(s.cursor) })
  expect(c.state().playing).toBe(true)
  vi.advanceTimersByTime(300)
  expect(c.state().cursor).toBe(1)
  vi.advanceTimersByTime(60_000)
  expect(c.state().cursor).toBe(full.events.length)
  expect(c.state().playing).toBe(false)
  expect(c.state().elapsedS).toBe(520)
  expect(frames[0]).toBe(0)
  c.seek(5)
  expect(c.state().cursor).toBe(5)
  c.dispose()
})
