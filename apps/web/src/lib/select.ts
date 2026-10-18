// Pure selectors over a Bundle. Counting records is allowed (spec §3 "counted live", §6.3
// "N/M quotes verified", §13.5 "n counted from the bundle"); arithmetic on engineering values is not.
import { LANE_ORDER } from './agents'
import { artifactPayload, visibleEvents } from './events'
import { worstStatus } from './status'
import type {
  AgentName,
  Approval,
  Bundle,
  Finding,
  FindingStatus,
  Revision,
  RunEvent,
  RunRecord,
  WhatIfParam,
  WhatIfResult,
} from './types'

export type DataSource = 'static' | 'live' | 'replay'

export function latestRevision(b: Bundle): Revision | null {
  return b.revisions.length ? b.revisions[b.revisions.length - 1] : null
}

export function revisionById(b: Bundle, id: string | null | undefined): Revision | null {
  return (id && b.revisions.find((r) => r.id === id)) || null
}

export function parentRevision(b: Bundle, rev: Revision | null): Revision | null {
  return rev?.parent ? revisionById(b, rev.parent) : null
}

export function findingsFor(b: Bundle, revId: string | null | undefined): Finding[] {
  return (revId && b.findings[revId]) || []
}

export function findingById(b: Bundle, revId: string | null | undefined, id: string | null): Finding | null {
  return (id && findingsFor(b, revId).find((f) => f.id === id)) || null
}

export function statusByElement(findings: Finding[]): Map<string, FindingStatus> {
  const groups = new Map<string, FindingStatus[]>()
  for (const f of findings) groups.set(f.element_id, [...(groups.get(f.element_id) ?? []), f.status])
  const out = new Map<string, FindingStatus>()
  for (const [id, ss] of groups) out.set(id, worstStatus(ss)!)
  return out
}

export function countByStatus(findings: Finding[]): Record<FindingStatus, number> {
  const c: Record<FindingStatus, number> = { pass: 0, fail: 0, warn: 0, 'n/a': 0 }
  for (const f of findings) c[f.status] += 1
  return c
}

export function currentRun(b: Bundle): RunRecord | null {
  return b.runs.length ? [...b.runs].sort((x, y) => x.started_at - y.started_at)[b.runs.length - 1] : null
}

export function approvalFor(b: Bundle, revId: string | null | undefined): Approval | null {
  return b.approvals.find((a) => a.revision === revId && a.decision === 'approved') ?? null
}

export function signedRevision(b: Bundle): Revision | null {
  return [...b.revisions].reverse().find((r) => approvalFor(b, r.id)) ?? null
}

/** Distinct agents that emitted events (system excluded) — tour step 4 "{n} agents designed this". */
export function agentsInvolved(b: Bundle): AgentName[] {
  const seen = new Set<AgentName>()
  for (const e of b.events) if (e.agent !== 'system') seen.add(e.agent)
  return LANE_ORDER.filter((a) => seen.has(a))
}

/** The engine's revision reference for /api/what-if and /api/explain (spec §6.4). */
export function revisionRef(b: Bundle, revId: string, source: DataSource): string {
  return source === 'live' ? `ws:${revId}` : `seed:${b.project.id}@${revId}`
}

/**
 * The revision a what-if runs on (#37), typed, chip or voice: the one picked in the revision bar, else the head
 * (latest) revision, whatever an automatic switch (D1's "why" answer, a deep link) left on screen.
 */
export function whatIfRevision(b: Bundle, onScreen: Revision | null, picked: boolean): Revision | null {
  return (picked && onScreen) || latestRevision(b)
}

/**
 * "r2 (signed)": how an answer names the revision it ran on (#37), from the bundle's id and status only. A live run's
 * revision ids carry the run's own id ("d99bb3b19525-r2"); the label leaves that off.
 */
export function revisionLabel(rev: Pick<Revision, 'id' | 'status'>): string {
  return `${rev.id.replace(/^[0-9a-f]{12}-/, '')} (${rev.status})`
}

/** Input values (not results) compared with a relative tolerance, so 0.9 matches a serialised 0.9000000000000001. */
export function sameInput(a: number, b: number): boolean {
  return Math.abs(a - b) <= 1e-9 * Math.max(1, Math.abs(a), Math.abs(b))
}

export function findWhatIf(b: Bundle, ref: string, param: WhatIfParam, value: number): WhatIfResult | null {
  return b.what_ifs.find((w) => w.revision_ref === ref && w.param === param && sameInput(w.value, value)) ?? null
}

export function exportsOf(b: Bundle): { title: string; ref: string }[] {
  return b.events
    .map((e) => ({ e, a: artifactPayload(e) }))
    .filter((x) => x.a?.type === 'export')
    .map((x) => ({ title: x.e.title, ref: x.a!.ref }))
}

/** Element ids a finding touches: its element plus any string input naming another element (e.g. R11 `over`). */
export function relatedElementIds(f: Finding, known: Set<string>): string[] {
  const ids = [f.element_id]
  for (const v of Object.values(f.inputs ?? {})) if (typeof v === 'string' && known.has(v) && !ids.includes(v)) ids.push(v)
  return ids
}

export type LaneStatus = 'idle' | 'running' | 'waiting' | 'done' | 'failed'
export interface Lane {
  agent: AgentName
  status: LaneStatus
  events: RunEvent[]
  counters: string[]
}

export function buildLanes(b: Bundle): Lane[] {
  const events = visibleEvents(b.events, b.steps)
  const run = currentRun(b)
  const lastSeq = events.length ? events[events.length - 1].seq : -1
  const stepStatus = new Map(b.steps.map((s) => [s.id, s.status]))
  const rev = latestRevision(b)
  const findings = findingsFor(b, rev?.id)
  const selected = run?.options?.find((o) => o.id === run.selected_option)

  return LANE_ORDER.filter((a) => a !== 'asset').map((agent) => {
    const evs = events.filter((e) => e.agent === agent)
    let status: LaneStatus = 'idle'
    if (evs.length) {
      const states = [...new Set(evs.map((e) => e.step))].map((s) => stepStatus.get(s))
      const last = evs[evs.length - 1]
      if (states.includes('failed')) status = 'failed'
      else if (states.includes('running')) status = 'running'
      else if (run?.status === 'running' && last.seq === lastSeq && !stepStatus.has(last.step)) status = 'running'
      else if (run?.status === 'at_gate' && last.kind === 'gate' && last.seq === lastSeq) status = 'waiting'
      else status = 'done'
    }
    const counters: string[] = []
    if (agent === 'intake' && b.brief) {
      const reqs = b.brief.requirements
      counters.push(`${reqs.filter((r) => r.verified).length}/${reqs.length} quotes verified`)
      const dc = b.brief.drawing_check ?? {}
      if (dc.agrees === true) counters.push('Drawing read · DXF agrees')
      else if (Array.isArray(dc.differences)) counters.push(`Drawing read · ${dc.differences.length} differences`)
    }
    if (agent === 'layout' && rev?.model) counters.push(`${rev.model.racks.length} racks placed`)
    if (agent === 'power' && run?.selected_option) counters.push(`Topology ${run.selected_option}`)
    if (agent === 'cooling' && rev?.model)
      counters.push(`${rev.model.cooling_nodes.filter((n) => n.kind === 'cdu').length} CDUs`)
    if (agent === 'procurement')
      for (const s of selected?.swaps ?? []) counters.push(`${String(s.from)} → ${String(s.to)} (${String(s.reason)})`)
    if (agent === 'checker' && findings.length) {
      const c = countByStatus(findings)
      counters.push(`${findings.length} checks`)
      if (c.fail) counters.push(`${c.fail} fail`)
    }
    if (agent === 'docs') {
      const n = exportsOf(b).length
      if (n) counters.push(`${n} exports`)
    }
    return { agent, status, events: evs, counters }
  })
}
