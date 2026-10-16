// The engine's fix dict as the drawer and the co-pilot show it. Formatting only: values come from the record.
// Ported to services/api/kirchhoff/agents/fix_text.py (read_fix), so voice words a fix the same way.
import { describeKey, tidyTokens } from '@/lib/format'
import type { Finding } from '@/lib/types'

export interface FixView {
  label: string
  reason: string
  /** Every delta in the record, ordered by meaning: the cost, the rule's resulting metric, its limit, then the rest. */
  deltas: [string, unknown][]
  /** The one-line summary (co-pilot and voice "why" answers): the cost and the resulting metric, never a limit. */
  headline: [string, unknown][]
}

/**
 * The resulting metric each rule's fix is judged on (engine/fixes.py `_metrics`): R05 the voltage drop after the
 * fix, R11 the crossings left. A rule not listed here falls back to the first delta that is neither a cost nor a limit.
 */
const PRIMARY_DELTA: Record<string, string> = { R05: 'dv_pct', R11: 'crossings' }

const isCostKey = (k: string) => describeKey(k).usd === true
const isLimitKey = (k: string) => /(^|_)limit(_|$)/.test(k)

/**
 * Orders a fix's deltas by key, never by position: recorded bundles store them key-sorted (the golden capture
 * puts `dv_limit_pct` before `dv_pct` and `cost_delta` among the metrics), so "the first two" was the limit.
 */
export function orderDeltas(entries: [string, unknown][], ruleId?: string | null): Pick<FixView, 'deltas' | 'headline'> {
  const costs = entries.filter(([k]) => isCostKey(k)).sort(([a], [b]) => Number(b === 'cost_delta') - Number(a === 'cost_delta'))
  const metrics = entries.filter(([k]) => !isCostKey(k))
  const want = ruleId ? PRIMARY_DELTA[ruleId] : undefined
  const primary = metrics.find(([k]) => k === want) ?? metrics.find(([k]) => !isLimitKey(k))
  const limits = metrics.filter(([k]) => isLimitKey(k))
  const rest = metrics.filter((e) => e !== primary && !isLimitKey(e[0]))
  return {
    deltas: [...costs, ...(primary ? [primary] : []), ...limits, ...rest],
    headline: [...costs.slice(0, 1), ...(primary ? [primary] : [])],
  }
}

/**
 * Reads the engine's fix dict: {candidate|label, reason, cost_delta?, deltas: {dv_pct, ...}}. `cost_delta` sits
 * beside `deltas` in the provisional bundles and inside it in the recorded ones; either way it leads, because the
 * cost is what explains the choice ("voltage-drop margin per dollar", final review I3).
 */
export function readFix(fix: Finding['fix'], ruleId?: string | null): FixView | null {
  if (!fix) return null
  const inner = fix.deltas && typeof fix.deltas === 'object' ? Object.entries(fix.deltas as Record<string, unknown>) : []
  const cost = typeof fix.cost_delta === 'number' && !inner.some(([k]) => k === 'cost_delta') ? [['cost_delta', fix.cost_delta] as [string, unknown]] : []
  return {
    label: tidyTokens(String(fix.label ?? fix.candidate ?? 'Fix')),
    reason: typeof fix.reason === 'string' ? tidyTokens(fix.reason) : '',
    ...orderDeltas([...cost, ...inner], ruleId),
  }
}
