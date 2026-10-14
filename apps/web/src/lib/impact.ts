// What-if impact chains (spec §6.4): ordered element paths rack → busway → board → transformer
// and rack → zone → CDU, shown in two colours (electrical vs cooling).
import { elementIndex, type Discipline } from './model'
import type { DesignModel, WhatIfResult } from './types'

export function classifyChain(chain: string[], model: DesignModel | null): Discipline {
  const idx = elementIndex(model)
  return chain.some((id) => idx.get(id)?.discipline === 'cooling' || /^(Z\d+|CDU-|H-Z|BR-)/.test(id))
    ? 'cooling'
    : 'electrical'
}

/** element id → disciplines of every chain it sits on (a rack is on both). */
export function chainHighlights(result: WhatIfResult | null, model: DesignModel | null): Map<string, Discipline[]> {
  const out = new Map<string, Discipline[]>()
  if (!result) return out
  for (const chain of result.impact_chain) {
    const d = classifyChain(chain, model)
    for (const id of chain) {
      const cur = out.get(id) ?? []
      if (!cur.includes(d)) out.set(id, [...cur, d])
    }
  }
  return out
}
