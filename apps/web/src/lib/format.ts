// Formatting only. Nothing here computes an engineering value: every number shown in the UI
// comes from bundle/API data and passes through these functions unchanged except for
// rounding, grouping and units (Global Constraints).
import type { Finding } from './types'

const NUM = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 })
const USD = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
const DATE = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  timeZone: 'Asia/Kolkata',
})
const REL = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })

export const DASH = '—'

export function fmtNum(v: number | null | undefined): string {
  return v === null || v === undefined || Number.isNaN(v) ? DASH : NUM.format(v)
}

export function fmtQty(v: number | null | undefined, unit?: string | null): string {
  if (v === null || v === undefined) return DASH
  if (!unit) return fmtNum(v)
  return unit === '%' ? `${fmtNum(v)}%` : `${fmtNum(v)} ${unit}`
}

export function fmtUsd(v: number | null | undefined, signed = false): string {
  if (v === null || v === undefined) return DASH
  const s = USD.format(v)
  return signed && v > 0 ? `+${s}` : s
}

/** `ts` is unix seconds (Python `time.time()`), rendered in IST. */
export function fmtTs(ts: number | null | undefined): string {
  return ts === null || ts === undefined ? DASH : DATE.format(new Date(ts * 1000))
}

export function fmtRelative(ts: number, nowMs: number = Date.now()): string {
  const diffS = ts - nowMs / 1000
  const abs = Math.abs(diffS)
  if (abs < 60) return REL.format(Math.round(diffS), 'second')
  if (abs < 3600) return REL.format(Math.round(diffS / 60), 'minute')
  if (abs < 86400) return REL.format(Math.round(diffS / 3600), 'hour')
  if (abs < 86400 * 14) return REL.format(Math.round(diffS / 86400), 'day')
  return REL.format(Math.round(diffS / (86400 * 7)), 'week')
}

/** Recorded elapsed time for replay clocks: 75 → "01:15", 3725 → "1:02:05". */
export function fmtElapsed(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const ss = s % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  return h > 0 ? `${h}:${pad(m)}:${pad(ss)}` : `${pad(m)}:${pad(ss)}`
}

export function shortHash(hash: string): string {
  return hash.length > 12 ? `${hash.slice(0, 12)}…` : hash
}

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/**
 * Fills `{value}` and `{limit}` in engine/LLM text from the finding record (spec §6.3). WS1's templates
 * already write the unit after the placeholder ("{value}% against {limit}%"), agent text usually does not;
 * the unit is appended only when it is not already there (ruling R20, same rule as WS2's fill_finding).
 */
export function fillPlaceholders(text: string, f: Pick<Finding, 'value' | 'limit' | 'unit'>): string {
  const unit = f.unit ?? null
  const unitNext = unit ? new RegExp(`^ ?${escapeRe(unit)}(?![A-Za-z0-9])`) : null
  return text.replace(/\{(value|limit)\}/g, (_m, name: string, offset: number) => {
    const v = (name === 'value' ? f.value : f.limit) ?? null
    const rest = text.slice(offset + name.length + 2)
    return unitNext && unitNext.test(rest) ? fmtNum(v) : fmtQty(v, unit)
  })
}

const KEY_LABELS: Record<string, { label: string; unit?: string; usd?: boolean }> = {
  dv_pct: { label: 'ΔV', unit: '%' },
  dv_limit_pct: { label: 'ΔV limit', unit: '%' },
  index_dp_kpa: { label: 'Index-circuit Δp', unit: 'kPa' },
  added_pipe_m: { label: 'Added pipe', unit: 'm' },
  changed_pipes: { label: 'Changed pipes' },
  rating_a: { label: 'Rating', unit: 'A' },
  cost_delta: { label: 'Cost Δ', usd: true },
  cost_usd: { label: 'Cost', usd: true },
  cost: { label: 'Cost', usd: true },
  capex_usd: { label: 'Capex', usd: true },
  lifecycle_usd: { label: 'Lifecycle cost', usd: true },
  margin_pct: { label: 'Margin', unit: '%' },
  loading_pct: { label: 'Loading', unit: '%' },
  losses_kw: { label: 'Losses', unit: 'kW' },
  lead_time_weeks: { label: 'Lead time', unit: 'weeks' },
  finding_id: { label: 'Finding' },
  ok: { label: 'OK' },
  i_a: { label: 'Current I', unit: 'A' },
  n1_current_a: { label: 'N-1 current', unit: 'A' },
  dc_kwp: { label: 'DC capacity', unit: 'kWp' },
  dc_ac: { label: 'DC/AC ratio' },
  voc_max_v: { label: 'Voc max', unit: 'V' },
  vmp_min_v: { label: 'Vmp min', unit: 'V' },
  annual_mwh: { label: 'Annual energy', unit: 'MWh' },
  annual_loss_mwh: { label: 'Annual loss', unit: 'MWh' },
}

const SUFFIX_UNITS: [string, string][] = [
  ['_pct', '%'],
  ['_kva', 'kVA'],
  ['_mva', 'MVA'],
  ['_mwh', 'MWh'],
  ['_kw', 'kW'],
  ['_mw', 'MW'],
  ['_kv', 'kV'],
  ['_ka', 'kA'],
  ['_kpa', 'kPa'],
  ['_lps', 'L/s'],
  ['_ms', 'm/s'],
  ['_km', 'km'],
  ['_weeks', 'weeks'],
  ['_usd', 'USD'],
  ['_a', 'A'],
  ['_v', 'V'],
  ['_m', 'm'],
]

/** Turns an engine dict key into a label and unit: "ampacity_a" → { label: "Ampacity", unit: "A" }. */
export function describeKey(key: string): { label: string; unit?: string; usd?: boolean } {
  const known = KEY_LABELS[key]
  if (known) return known
  const lower = key.toLowerCase()
  for (const [suffix, unit] of SUFFIX_UNITS) {
    if (lower.endsWith(suffix) && lower.length > suffix.length) {
      return { label: humanize(key.slice(0, -suffix.length)), unit }
    }
  }
  return { label: humanize(key) }
}

function humanize(key: string): string {
  const words = key.replace(/_/g, ' ').trim()
  return words.charAt(0).toUpperCase() + words.slice(1)
}

const isScalar = (v: unknown): v is string | number | boolean => ['string', 'number', 'boolean'].includes(typeof v)

/** "clashes" → "clash", "options" → "option" (for a count of one). */
function singular(word: string): string {
  if (/(ches|shes|sses|xes)$/.test(word)) return word.slice(0, -2)
  return word.endsWith('s') ? word.slice(0, -1) : word
}

/** A list of ids reads as a short list; anything else as a count of its entries (counting is allowed). */
function fmtCollection(label: string, value: unknown[] | Record<string, unknown>): string {
  if (Array.isArray(value) && value.length && value.every((x) => typeof x === 'string' || typeof x === 'number')) {
    const shown = value.slice(0, 4).map((x) => (typeof x === 'number' ? fmtNum(x) : x))
    return `${label} ${shown.join(', ')}${value.length > 4 ? ` +${value.length - 4} more` : ''}`
  }
  const n = Array.isArray(value) ? value.length : Object.keys(value).length
  const noun = label.toLowerCase()
  return `${n} ${n === 1 ? singular(noun) : noun}`
}

/**
 * Formats one engine key/value pair for display, e.g. ("dv_pct", 0.84) → "ΔV 0.84%". WS2's tool
 * summaries also carry lists and dicts (options, pipes, clashes, candidates): those read as a
 * count or a short id list, never "[object Object]" (final review I2).
 */
export function fmtKeyValue(key: string, value: unknown): string {
  const d = describeKey(key)
  if (typeof value === 'number') {
    if (d.usd) return `${d.label} ${fmtUsd(value, key.endsWith('delta'))}`
    return `${d.label} ${fmtQty(value, d.unit === 'USD' ? null : d.unit)}${d.unit === 'USD' ? ' USD' : ''}`
  }
  if (typeof value === 'boolean') return `${d.label} ${value ? '✓' : '✗'}`
  if (value === null || value === undefined) return `${d.label} ${DASH}`
  if (typeof value === 'object') return fmtCollection(d.label, value as unknown[] | Record<string, unknown>)
  return `${d.label} ${String(value)}`
}

/** A finding's formula input as label and value with its unit ("i_a", 1546.43 → "Current I", "1,546.43 A"). */
export function fmtInput(key: string, value: unknown): { label: string; value: string } {
  const d = describeKey(key)
  if (typeof value === 'number') return { label: d.label, value: d.usd ? fmtUsd(value) : fmtQty(value, d.unit === 'USD' ? null : d.unit) }
  if (Array.isArray(value) && value.every(isScalar)) return { label: d.label, value: value.map((x) => (typeof x === 'number' ? fmtNum(x) : String(x))).join(', ') }
  if (value !== null && typeof value === 'object') {
    const n = Array.isArray(value) ? value.length : Object.keys(value).length
    return { label: d.label, value: `${n} ${n === 1 ? 'entry' : 'entries'}` }
  }
  return { label: d.label, value: value === null || value === undefined ? DASH : String(value) }
}
