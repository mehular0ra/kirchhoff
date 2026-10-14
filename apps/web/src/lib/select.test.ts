import { fixtureBundle } from '@/test/fixtures'
import { visibleEvents } from './events'
import {
  agentsInvolved,
  approvalFor,
  buildLanes,
  countByStatus,
  findWhatIf,
  findingsFor,
  latestRevision,
  relatedElementIds,
  revisionRef,
  statusByElement,
} from './select'

test('normalised fixture bundle exposes revisions in order and findings per revision', () => {
  const b = fixtureBundle()
  expect(latestRevision(b)?.id).toBe('r2')
  expect(countByStatus(findingsFor(b, 'r1'))).toEqual({ pass: 3, fail: 2, warn: 1, 'n/a': 0 })
  expect(approvalFor(b, 'r2')?.approver_name).toBe('Priya Raman')
})

test('worst status per element', () => {
  const s = statusByElement(findingsFor(fixtureBundle(), 'r1'))
  expect(s.get('FA-01')).toBe('fail')
  expect(s.get('T-A1')).toBe('pass')
  expect(s.get('BR-R1')).toBe('warn')
})

test('completed steps show only the committing attempt (spec §6.2)', () => {
  const b = fixtureBundle()
  const seqs = visibleEvents(b.events, b.steps).map((e) => e.seq)
  expect(seqs).not.toContain(14) // p3.check attempt 1 is stale
  expect(seqs).toContain(15)
  expect(seqs).toContain(19) // step without a record keeps its latest attempt
})

test('lanes carry per-agent status and counted record summaries', () => {
  const lanes = buildLanes(fixtureBundle())
  const intake = lanes.find((l) => l.agent === 'intake')!
  expect(intake.status).toBe('done')
  expect(intake.counters).toEqual(['2/3 quotes verified', 'Drawing read · DXF agrees'])
  const checker = lanes.find((l) => l.agent === 'checker')!
  expect(checker.counters).toEqual(['6 checks'])
  expect(checker.events.every((e) => e.attempt === 2)).toBe(true)
  expect(lanes.find((l) => l.agent === 'procurement')!.counters).toEqual(['TX-2500 → TX-3150 (R15)'])
})

test('agents involved are counted from events', () => {
  expect(agentsInvolved(fixtureBundle())).toEqual([
    'intake',
    'orchestrator',
    'layout',
    'power',
    'cooling',
    'procurement',
    'checker',
    'docs',
  ])
})

test('revision refs and precomputed what-ifs', () => {
  const b = fixtureBundle()
  expect(revisionRef(b, 'r2', 'static')).toBe('seed:hall-a@r2')
  expect(revisionRef(b, 'r2', 'live')).toBe('ws:r2')
  expect(findWhatIf(b, 'seed:hall-a@r2', 'rack_kw', 200)?.impact_chain).toHaveLength(2)
  expect(findWhatIf(b, 'seed:hall-a@r2', 'rack_kw', 150)).toBeNull()
})

test('related elements include string inputs that name model elements', () => {
  const b = fixtureBundle()
  const f = findingsFor(b, 'r1').find((x) => x.id === 'R11:H-Z2')!
  expect(relatedElementIds(f, new Set(['H-Z2', 'FB-03']))).toEqual(['H-Z2', 'FB-03'])
})
