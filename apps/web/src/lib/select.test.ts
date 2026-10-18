import { chipsFor } from '@/workspace/copilot/useWhatIf'
import { fixtureBundle } from '@/test/fixtures'
import hallMini from '@/test/fixtures/hall-mini.json'
import { normalizeBundle, type ProjectBundle } from './types'
import { visibleEvents } from './events'
import {
  agentsInvolved,
  approvalFor,
  buildLanes,
  countByStatus,
  exportsOf,
  findWhatIf,
  findingsFor,
  latestRevision,
  relatedElementIds,
  revisionLabel,
  revisionRef,
  statusByElement,
} from './select'

test('a revision is named by its short id and status, also for a live run whose ids carry the run id', () => {
  expect(revisionLabel({ id: 'r2', status: 'signed' })).toBe('r2 (signed)')
  expect(revisionLabel({ id: 'd99bb3b19525-r2', status: 'checked' })).toBe('r2 (checked)')
  // only a run id prefix is dropped, never part of a real name
  expect(revisionLabel({ id: 'hall-b-r2', status: 'draft' })).toBe('hall-b-r2 (draft)')
})

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

test('backlog [6]: precomputed what-ifs match a float value within tolerance (0.9 vs 0.9000000000000001)', () => {
  const b = fixtureBundle()
  const w = b.what_ifs[0]
  expect(findWhatIf(b, w.revision_ref, w.param, w.value + 1e-12)).toBe(w)
  expect(findWhatIf(b, w.revision_ref, w.param, w.value + 0.5)).toBeNull()
  expect(chipsFor([{ ...w, param: 'liquid_fraction', value: 0.9000000000000001 }]).filter((c) => c.param === 'liquid_fraction')).toHaveLength(1)
})

test('I12: normalizeBundle applies the visibility rule, so a stale attempt never reaches exports, counts or replay', () => {
  const raw = structuredClone(hallMini) as unknown as ProjectBundle
  raw.events = [
    ...(raw.events ?? []),
    { seq: 99, phase: 'p3', step: 'p3.check', attempt: 1, agent: 'docs', kind: 'artifact', title: 'stale export', detail: '', payload: { type: 'export', ref: '/stale.pdf' }, ts: 1760000999 },
  ]
  const b = normalizeBundle(raw)
  expect(b.events.map((e) => e.seq)).not.toContain(14)
  expect(b.events.map((e) => e.seq)).not.toContain(99)
  expect(exportsOf(b).map((x) => x.ref)).not.toContain('/stale.pdf')
})
