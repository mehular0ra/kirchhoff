// Typed co-pilot input → one of the three co-pilot tools (spec §6.5). Deterministic, no LLM:
// there is no text-chat endpoint, and typed chips must work with the backend down.
import type { WhatIfParam } from '@/lib/types'

export type Intent =
  | { tool: 'what_if'; param: WhatIfParam; value: number }
  | { tool: 'explain_finding'; element: string; rule?: string }
  | { tool: 'focus_element'; element: string }

const NUM = '(\\d+(?:\\.\\d+)?)'
const ELEMENT = /\b([A-Z]{1,3}\d?-[A-Z]?\d{1,2}(?:-\d{2})?|[A-Z]\d)\b/i
const RULE = /\b(R\d{2}b?)\b/i

export function parseIntent(text: string): Intent | null {
  const t = text.trim()
  if (/^what\s*if|^if\b/i.test(t) || /\bwhat-if\b/i.test(t)) {
    const rack = t.match(new RegExp(`rack\\w*\\D*?${NUM}\\s*kw`, 'i'))
    if (rack) return { tool: 'what_if', param: 'rack_kw', value: Number(rack[1]) }
    const liquid = t.match(new RegExp(`liquid\\D*?${NUM}`, 'i'))
    if (liquid) return { tool: 'what_if', param: 'liquid_fraction', value: Number(liquid[1]) }
    const dv = t.match(new RegExp(`(?:ΔV|dv|voltage drop)\\D*?${NUM}`, 'i'))
    if (dv) return { tool: 'what_if', param: 'dv_limit_pct', value: Number(dv[1]) }
    const tx = t.match(new RegExp(`transformer\\D*?${NUM}`, 'i'))
    if (tx) return { tool: 'what_if', param: 'tx_loading_cap_pct', value: Number(tx[1]) }
    return null
  }
  const el = t.match(ELEMENT)?.[1]?.toUpperCase()
  if (/^(why|explain)\b/i.test(t) && el) {
    const rule = t.match(RULE)?.[1]
    return { tool: 'explain_finding', element: el, rule: rule ? rule.toUpperCase().replace('B', 'b') : undefined }
  }
  if (/^(show|focus|where|zoom|find)\b/i.test(t) && el) return { tool: 'focus_element', element: el }
  return null
}

export const INTENT_HELP = 'Try: “what if racks go to 200 kW”, “why FA-01”, “show H-Z2”.'
