import type { AgentName } from './types'

export interface AgentMeta {
  label: string
  /** CSS colour for dots, lane accents and 3D/SLD highlights (spec §6.1 colours). */
  color: string
  /** Tailwind text class for the accent. */
  text: string
}

export const AGENTS: Record<AgentName, AgentMeta> = {
  intake: { label: 'Intake', color: '#64748b', text: 'text-slate-600' },
  orchestrator: { label: 'Orchestrator', color: '#0b0d10', text: 'text-foreground' },
  layout: { label: 'Layout', color: '#0891b2', text: 'text-cyan-700' },
  power: { label: 'Power', color: '#f59e0b', text: 'text-amber-700' },
  cooling: { label: 'Cooling', color: '#3b82f6', text: 'text-blue-700' },
  procurement: { label: 'Procurement', color: '#16a34a', text: 'text-green-700' },
  checker: { label: 'Checker', color: '#ef4444', text: 'text-red-700' },
  docs: { label: 'Docs', color: '#8b5cf6', text: 'text-violet-700' },
  copilot: { label: 'Co-pilot', color: 'linear-gradient(135deg,#d946ef,#0ea5e9)', text: 'text-fuchsia-700' },
  asset: { label: 'Asset', color: '#0d9488', text: 'text-teal-700' },
  system: { label: 'System', color: '#71717a', text: 'text-muted-foreground' },
}

/** Lane order in the workspace (spec §12 layout). */
export const LANE_ORDER: AgentName[] = [
  'intake',
  'orchestrator',
  'layout',
  'power',
  'cooling',
  'procurement',
  'checker',
  'docs',
  'asset',
]

/**
 * Impact-chain colours (spec §3 what-if beat). Orange and violet (UX-1 D6): the earlier amber/blue pair
 * matched Warn amber and the default pipe blue, so the cooling chain vanished in 3D. On white (light theme)
 * both step to their -600 shades: a red-orange well clear of Warn's yellow-amber #f59e0b, and a violet well
 * clear of the sky-blue pipes #0ea5e9; each is ≥ 3:1 against white as a line or a fill.
 */
export const CHAIN_COLORS = { electrical: '#ea580c', cooling: '#7c3aed' } as const
