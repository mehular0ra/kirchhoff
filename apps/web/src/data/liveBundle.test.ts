import { fixtureBundle } from '@/test/fixtures'
import type { Bundle, Project } from '@/lib/types'
import type { CollectionQuery, DocSnap, LiveSource } from './liveSource'
import { subscribeLiveBundle } from './liveBundle'
import { leaseIsStale } from './useLeaseWatchdog'

/** In-memory LiveSource: tests push Firestore-like snapshots into watched paths. */
function fakeSource() {
  const docs = new Map<string, (d: DocSnap | null) => void>()
  const cols = new Map<string, { cb: (d: DocSnap[]) => void; q?: CollectionQuery }>()
  const stored = new Map<string, Record<string, unknown>>()
  const src: LiveSource = {
    watchDoc: (path, cb) => {
      docs.set(path, cb)
      return () => docs.delete(path)
    },
    watchCollection: (path, cb, q) => {
      cols.set(path, { cb, q })
      return () => cols.delete(path)
    },
    getDoc: async (path) => (stored.has(path) ? { id: path.split('/').pop()!, data: stored.get(path)! } : null),
  }
  return {
    src,
    docs,
    cols,
    stored,
    doc: (path: string, data: Record<string, unknown>) => docs.get(path)!({ id: path.split('/').pop()!, data }),
    col: (path: string, items: Record<string, unknown>[]) =>
      cols.get(path)!.cb(items.map((data, i) => ({ id: String(data.id ?? data.seq ?? i), data }))),
  }
}

const project: Project = {
  id: 'hall-b',
  name: 'Deccan AI Campus · Hall B',
  client: 'Deccan Compute',
  asset_pack: 'datahall',
  state: 'not_started',
  sample: true,
  updated_at: 0,
}

test('assembles a live bundle from workspace snapshots', async () => {
  const fx = fixtureBundle()
  const f = fakeSource()
  const seen: Bundle[] = []
  const base = 'workspaces/u1'
  const run = `${base}/runs/run-1`
  const briefRef = `${run}/outputs/p1.intake` // WS2 step-outputs doc {step, json} (ruling R7)
  const off = subscribeLiveBundle(f.src, { uid: 'u1', runId: 'run-1', project, loadJson: async () => null }, (b) => seen.push(b))

  expect(f.cols.get(`${run}/events`)?.q).toEqual({ orderBy: 'seq' })
  expect(f.cols.get(`${base}/revisions`)?.q).toEqual({ where: ['project_id', '==', 'hall-b'] })

  f.doc(run, { ...fx.runs[0], id: 'run-1', project_id: 'hall-b', status: 'running', gate: null })
  f.col(`${run}/steps`, fx.steps as unknown as Record<string, unknown>[])
  const events = fx.events.map((e) =>
    e.kind === 'artifact' && (e.payload as { type?: string }).type === 'brief'
      ? { ...e, payload: { type: 'brief', ref: briefRef } }
      : e,
  )
  f.col(`${run}/events`, events as unknown as Record<string, unknown>[]) // the outputs doc is not committed yet
  await new Promise((r) => setTimeout(r, 0)) // let the first (empty) read settle
  expect(seen[seen.length - 1].brief).toBeNull()
  f.stored.set(briefRef, { step: 'p1.intake', json: JSON.stringify({ brief: fx.brief }) }) // the step commits
  f.col(`${run}/steps`, fx.steps as unknown as Record<string, unknown>[]) // its snapshot triggers the retry
  f.col(`${base}/revisions`, fx.revisions.map((r) => ({ ...r, project_id: 'hall-b' })) as unknown as Record<string, unknown>[])
  expect(f.cols.has(`${base}/revisions/r1/findings`)).toBe(true)
  f.col(`${base}/revisions/r1/findings`, fx.findings.r1 as unknown as Record<string, unknown>[])
  await new Promise((r) => setTimeout(r, 0))

  const b = seen[seen.length - 1]
  expect(b.project.state).toBe('running')
  expect(b.runs[0].id).toBe('run-1')
  expect(b.events.map((e) => e.seq)).not.toContain(14) // stale attempt filtered
  expect(b.revisions.map((r) => r.id)).toEqual(['r1', 'r2'])
  expect(b.findings.r1).toHaveLength(6)
  expect(b.findings.r2).toEqual([])
  expect(b.brief?.requirements).toHaveLength(3)

  f.col(`${base}/approvals`, [{ ...fx.approvals[0] }])
  expect(seen[seen.length - 1].project.state).toBe('signed')

  off()
  expect(f.cols.size).toBe(0)
  expect(f.docs.size).toBe(0)
})

test('lease is stale only for running runs with an old heartbeat', () => {
  const run = { ...fixtureBundle().runs[0], status: 'running' as const, lease: { owner: 'w', attempt: 1, heartbeat_at: 1000 } }
  expect(leaseIsStale(run, 1059)).toBe(false)
  expect(leaseIsStale(run, 1061)).toBe(true)
  expect(leaseIsStale({ ...run, status: 'at_gate' }, 5000)).toBe(false)
})
