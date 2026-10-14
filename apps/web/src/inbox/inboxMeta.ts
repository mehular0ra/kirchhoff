// Labels and icons for the bids inbox. Status is always icon + text; colour is a third, redundant cue (spec §12).
import { CircleCheck, CircleMinus, CircleQuestionMark, CircleX, ScanLine, TriangleAlert, type LucideIcon } from 'lucide-react'
import type { AssetPack, AttachmentKind, InboxAppetite, TriageResult, Verification } from '@/lib/types'

interface Meta {
  label: string
  icon: LucideIcon
  cls: string
}

export const VERDICT_META: Record<'pursue' | 'clarify' | 'decline' | 'none', Meta> = {
  pursue: { label: 'Pursue', icon: CircleCheck, cls: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300' },
  clarify: { label: 'Clarify', icon: CircleQuestionMark, cls: 'border-amber-400/50 bg-amber-500/10 text-amber-300' },
  decline: { label: 'Decline', icon: CircleX, cls: 'border-rose-500/50 bg-rose-500/10 text-rose-300' },
  none: { label: 'Not a bid', icon: CircleMinus, cls: 'border-zinc-600 bg-zinc-500/10 text-zinc-300' },
}

export function verdictMeta(t: TriageResult): Meta {
  return VERDICT_META[t.fit.verdict ?? 'none']
}

export const VERIFICATION_META: Record<Verification, Meta> = {
  verified: { label: 'quote verified', icon: CircleCheck, cls: 'text-emerald-400' },
  unverified_scan: { label: 'unverified (scan)', icon: ScanLine, cls: 'text-amber-300' },
  unverified: { label: 'not verified', icon: TriangleAlert, cls: 'text-amber-300' },
}

export const KIND_ORDER: AttachmentKind[] = ['tender', 'drawing', 'addendum', 'boq', 'brochure', 'other']
export const KIND_LABEL: Record<AttachmentKind, string> = {
  tender: 'Tender',
  drawing: 'Drawing',
  addendum: 'Addendum',
  boq: 'BOQ',
  brochure: 'Brochure',
  other: 'Other',
}

const PACK_LABEL: Record<AssetPack, string> = { datahall: 'AI data halls', grid: 'grid', solar: 'solar' }

/** One line describing the fit rules. Every number comes from the inbox data (world.yaml). */
export function appetiteLine(a: InboxAppetite): string {
  const packs = a.asset_types.map((p) => PACK_LABEL[p]).join(', ')
  const regions = a.regions.map((r) => r.name).join(', ')
  return `Appetite: ${packs} · ${a.mw[0]}–${a.mw[1]} MW · ${regions} · at least ${a.min_days_to_bid_due} days to the bid deadline`
}
