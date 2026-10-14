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
  // Played: seq 1–13, 15 (revision r1 artifact), 16 (R05 finding). The stale attempt (seq 14) is
  // not in a normalised bundle at all (visibility rule, I12).
  const f = frameAt(full, 15)
  expect(f.brief).not.toBeNull()
  expect((f.runs[0].options ?? []).map((o) => o.id)).toEqual(['2N', 'DR'])
  expect(f.revisions.map((r) => r.id)).toEqual(['r1'])
  expect(f.steps.find((s) => s.id === 'p3.check')?.status).toBe('running')
  // I8: a finding with its own event appears when that event plays; checks without an event (WS2
  // emits one per failing finding only) appear with the revision, so "N checks" is never 1–2.
  const ids = f.findings.r1.map((x) => x.id).sort()
  expect(ids).toEqual(['R02:A-01', 'R05:FA-01', 'R10:BR-R1', 'R15:T-A1'])
  expect(ids).not.toContain('R11:H-Z2') // its event (seq 17) has not played yet
})

test('I8: with WS2\'s shape (finding events for failures only) the matrix shows every check once the revision is revealed', () => {
  const full = fixtureBundle()
  full.events = full.events.filter((e) => e.kind !== 'finding' || (e.payload as { status?: string }).status === 'fail')
  const atReveal = frameAt(full, full.events.findIndex((e) => e.seq === 15) + 1)
  const r1 = full.findings.r1
  expect(atReveal.findings.r1).toHaveLength(r1.length - 2) // both fails still to come
  const afterFirstFail = frameAt(full, full.events.findIndex((e) => e.seq === 16) + 1)
  expect(afterFirstFail.findings.r1.filter((x) => x.status === 'fail').map((x) => x.id)).toEqual(['R05:FA-01'])
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
