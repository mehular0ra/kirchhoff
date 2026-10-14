// Typed readers for RunEvent payloads (event vocabulary in plans/2026-10-13-interfaces.md).
import type { FindingStatus, LedgerEntry, OpenQuestion, PlanStep, RunEvent, StepRecord } from './types'

const obj = (v: unknown): Record<string, unknown> | null =>
  v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : null

export interface FindingPayload {
  finding_id: string
  rule_id: string
  element_id: string
  status: FindingStatus
  rev?: string
}
export function findingPayload(ev: RunEvent): FindingPayload | null {
  const p = obj(ev.payload)
  if (ev.kind !== 'finding' || !p || typeof p.finding_id !== 'string') return null
  return {
    finding_id: p.finding_id,
    rule_id: String(p.rule_id ?? ''),
    element_id: String(p.element_id ?? ''),
    status: (p.status as FindingStatus) ?? 'n/a',
    rev: typeof p.rev === 'string' ? p.rev : undefined,
  }
}

export type ArtifactType = 'brief' | 'options' | 'revision' | 'export'
export function artifactPayload(ev: RunEvent): { type: ArtifactType; ref: string } | null {
  const p = obj(ev.payload)
  if (ev.kind !== 'artifact' || !p || typeof p.ref !== 'string') return null
  return { type: p.type as ArtifactType, ref: p.ref }
}

export type GateName = 'plan' | 'option' | 'review'
export function gatePayload(ev: RunEvent): GateName | null {
  const p = obj(ev.payload)
  return ev.kind === 'gate' && p && typeof p.gate === 'string' ? (p.gate as GateName) : null
}

export function ledgerPayload(ev: RunEvent): LedgerEntry | null {
  const e = obj(obj(ev.payload)?.entry)
  return ev.kind === 'ledger' && e ? (e as unknown as LedgerEntry) : null
}

export function toolPayload(
  ev: RunEvent,
): { tool: string; args: Record<string, unknown>; summary: Record<string, unknown> } | null {
  const p = obj(ev.payload)
  if ((ev.kind !== 'tool_call' && ev.kind !== 'tool_result') || !p) return null
  return { tool: String(p.tool ?? ev.title), args: obj(p.args) ?? {}, summary: obj(p.summary) ?? {} }
}

export function planPayload(ev: RunEvent): { plan: PlanStep[]; open_questions: OpenQuestion[] } | null {
  const p = obj(ev.payload)
  if (ev.kind !== 'plan' || !p) return null
  return {
    plan: Array.isArray(p.plan) ? (p.plan as PlanStep[]) : [],
    open_questions: Array.isArray(p.open_questions) ? (p.open_questions as OpenQuestion[]) : [],
  }
}

/** Artifact refs may be bare ids ("r1") or Firestore paths ("workspaces/u/revisions/r1"). */
export function refTail(ref: string): string {
  const parts = ref.split('/')
  return parts[parts.length - 1]
}

/**
 * Spec §6.2: for a completed step show only events from the attempt that committed it; for the
 * running step, events from its current attempt. Steps without a record show their latest attempt.
 */
export function visibleEvents(events: RunEvent[], steps: StepRecord[]): RunEvent[] {
  const recorded = new Map(steps.map((s) => [s.id, s.attempt]))
  const latest = new Map<string, number>()
  for (const e of events) latest.set(e.step, Math.max(latest.get(e.step) ?? 0, e.attempt ?? 1))
  return events
    .filter((e) => (e.attempt ?? 1) === (recorded.get(e.step) ?? latest.get(e.step)))
    .sort((a, b) => a.seq - b.seq)
}
