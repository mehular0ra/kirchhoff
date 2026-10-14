// What-if (spec §6.4): precomputed results from the static bundle first (works with the backend
// down), then POST /api/what-if. Results are shown, never saved.
import { useState } from 'react'
import { fmtQty } from '@/lib/format'
import { findWhatIf, sameInput } from '@/lib/select'
import type { WhatIfParam, WhatIfResult } from '@/lib/types'
import { completeItem } from '@/onboarding/checklist/checklistStore'
import { ApiError, describeApiError } from '@/services/apiClient'
import { useServices } from '@/services/services'
import { useUi } from '@/store/ui'
import { useWorkspace } from '../WorkspaceContext'

export interface WhatIfChip {
  param: WhatIfParam
  value: number
}

/** The engine's chip set (WS1 precomputes these for Hall A). Values are user inputs, not results. */
export const WHAT_IF_PRESETS: WhatIfChip[] = [
  { param: 'rack_kw', value: 200 },
  { param: 'rack_kw', value: 150 },
  { param: 'liquid_fraction', value: 0.9 },
  { param: 'dv_limit_pct', value: 1.5 },
  { param: 'tx_loading_cap_pct', value: 35 },
]

const PARAM_LABEL: Record<WhatIfParam, { label: string; unit: string | null }> = {
  rack_kw: { label: 'Racks', unit: 'kW' },
  liquid_fraction: { label: 'Liquid fraction', unit: null },
  dv_limit_pct: { label: 'ΔV limit', unit: '%' },
  tx_loading_cap_pct: { label: 'Transformer loading cap', unit: '%' },
}

/** Mirrors the engine's `PARAM_BOUNDS` (kirchhoff/engine) so the custom input is validated before
 * any API round-trip; out-of-range or unknown values raise ValueError server-side (422). */
export const PARAM_BOUNDS: Record<WhatIfParam, [number, number]> = {
  rack_kw: [1, 400],
  liquid_fraction: [0, 1],
  dv_limit_pct: [0.1, 10],
  tx_loading_cap_pct: [1, 150],
}

export function paramOutOfRange(param: WhatIfParam, value: number): boolean {
  const [lo, hi] = PARAM_BOUNDS[param]
  return !Number.isFinite(value) || value < lo || value > hi
}

export function chipLabel(c: WhatIfChip): string {
  const p = PARAM_LABEL[c.param]
  return `${p.label} → ${fmtQty(c.value, p.unit)}`
}

export function paramLabel(p: WhatIfParam): string {
  return PARAM_LABEL[p].label
}

export function chipsFor(precomputed: WhatIfResult[]): WhatIfChip[] {
  const all = [...WHAT_IF_PRESETS, ...precomputed.map((w) => ({ param: w.param, value: w.value }))]
  return all.filter((c, i) => all.findIndex((d) => d.param === c.param && sameInput(d.value, c.value)) === i)
}

const UNREACHABLE_TEXT = 'The engine is unreachable right now; the sample hall’s precomputed chips still work.'

export function useWhatIf() {
  const view = useWorkspace()
  const { api } = useServices()
  const setWhatIf = useUi((s) => s.setWhatIf)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = async (param: WhatIfParam, value: number): Promise<WhatIfResult | null> => {
    if (!view.revRef) return null
    setError(null)
    if (paramOutOfRange(param, value)) {
      const [lo, hi] = PARAM_BOUNDS[param]
      const p = PARAM_LABEL[param]
      setError(`${p.label} must be between ${fmtQty(lo, p.unit)} and ${fmtQty(hi, p.unit)}.`)
      return null
    }
    const ui = useUi.getState()
    if (ui.tab === 'options' || ui.tab === 'docs') ui.setTab('sld')
    const pre = findWhatIf(view.bundle, view.revRef, param, value)
    if (pre) {
      setWhatIf({ result: pre, origin: 'precomputed' })
      completeItem('run_whatif')
      return pre
    }
    setLoading(true)
    try {
      const result = await api.whatIf(view.revRef, param, value)
      setWhatIf({ result, origin: 'engine' })
      completeItem('run_whatif')
      return result
    } catch (e) {
      setError(e instanceof ApiError && e.status === 422 ? describeApiError(e) : UNREACHABLE_TEXT)
      return null
    } finally {
      setLoading(false)
    }
  }
  return { run, loading, error, clear: () => setWhatIf(null) }
}
