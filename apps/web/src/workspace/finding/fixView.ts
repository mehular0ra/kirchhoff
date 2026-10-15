// The engine's fix dict as the drawer and the co-pilot show it. Formatting only: values come from the record.
import type { Finding } from '@/lib/types'

export interface FixView {
  label: string
  reason: string
  deltas: [string, unknown][]
}

/**
 * Reads the engine's fix dict: {candidate|label, reason, cost_delta?, deltas: {dv_pct, ...}}. The
 * shipped bundles carry `cost_delta` beside `deltas` (not inside it); it leads the card because the
 * cost is what explains the choice ("voltage-drop margin per dollar", final review I3).
 */
export function readFix(fix: Finding['fix']): FixView | null {
  if (!fix) return null
  const inner = fix.deltas && typeof fix.deltas === 'object' ? Object.entries(fix.deltas as Record<string, unknown>) : []
  const cost = typeof fix.cost_delta === 'number' && !inner.some(([k]) => k === 'cost_delta') ? [['cost_delta', fix.cost_delta] as [string, unknown]] : []
  const deltas = [...cost, ...inner]
  return {
    label: String(fix.label ?? fix.candidate ?? 'Fix'),
    reason: typeof fix.reason === 'string' ? fix.reason : '',
    deltas,
  }
}
