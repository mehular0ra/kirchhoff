import { CircleCheck, CircleMinus, CircleX, TriangleAlert, type LucideIcon } from 'lucide-react'
import type { FindingStatus } from './types'

export interface StatusMeta {
  label: string
  icon: LucideIcon
  text: string // tailwind text colour class
  bg: string // tailwind background class (subtle)
  border: string
  hex: string // for canvas/3D materials
}

// Status is always icon + text; colour is a third, redundant cue (spec §12). Text is the -700 shade, WCAG AA
// (≥ 4.5:1) on white and on its own -50 tint; `hex` is the saturated mid shade for canvas strokes and 3D materials.
export const STATUS_META: Record<FindingStatus, StatusMeta> = {
  pass: { label: 'Pass', icon: CircleCheck, text: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-200', hex: '#059669' },
  fail: { label: 'Fail', icon: CircleX, text: 'text-rose-700', bg: 'bg-rose-50', border: 'border-rose-300', hex: '#e11d48' },
  warn: { label: 'Warn', icon: TriangleAlert, text: 'text-amber-700', bg: 'bg-amber-50', border: 'border-amber-300', hex: '#f59e0b' },
  'n/a': { label: 'N/A', icon: CircleMinus, text: 'text-muted-foreground', bg: 'bg-zinc-100', border: 'border-zinc-200', hex: '#8b919c' },
}

const RANK: Record<FindingStatus, number> = { 'n/a': 0, pass: 1, warn: 2, fail: 3 }

export function worstStatus(statuses: Iterable<FindingStatus>): FindingStatus | null {
  let worst: FindingStatus | null = null
  for (const s of statuses) if (worst === null || RANK[s] > RANK[worst]) worst = s
  return worst
}

export function statusRank(s: FindingStatus): number {
  return RANK[s]
}

/** Rule pack v0.1 columns (spec §8.3). Names only; limits always come from finding records. */
export const RULES: { id: string; name: string }[] = [
  { id: 'R01', name: 'Transformer loading' },
  { id: 'R02', name: 'Busway / feeder rating' },
  { id: 'R03', name: 'Breaker coordination' },
  { id: 'R04', name: 'Breaker Icu' },
  { id: 'R04b', name: 'Busway withstand' },
  { id: 'R05', name: 'Voltage drop' },
  { id: 'R06', name: 'Single points of failure' },
  { id: 'R07', name: 'UPS capacity' },
  { id: 'R08', name: 'CDU capacity' },
  { id: 'R09', name: 'Rack flow' },
  { id: 'R10', name: 'Pipe velocity' },
  { id: 'R11', name: 'Liquid above electrical' },
  { id: 'R12', name: 'SLD = BOQ = PR' },
  { id: 'R13', name: 'CDU pump supply' },
  { id: 'R14', name: 'Index-circuit Δp' },
  { id: 'R15', name: 'Lead time' },
]

export function ruleName(ruleId: string): string {
  return RULES.find((r) => r.id === ruleId)?.name ?? ruleId
}
