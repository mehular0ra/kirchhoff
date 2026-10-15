import type { AgentName } from './types'

export interface AgentMeta {
  label: string
  /** CSS colour for dots, lane accents and 3D/SLD highlights (spec §6.1 colours). */
  color: string
  /** Tailwind text class for the accent. */
  text: string
}

export const AGENTS: Record<AgentName, AgentMeta> = {
  intake: { label: 'Intake', color: '#94a3b8', text: 'text-slate-400' },
  orchestrator: { label: 'Orchestrator', color: '#f4f4f5', text: 'text-zinc-100' },
  layout: { label: 'Layout', color: '#22d3ee', text: 'text-cyan-400' },
  power: { label: 'Power', color: '#fbbf24', text: 'text-amber-400' },
  cooling: { label: 'Cooling', color: '#60a5fa', text: 'text-blue-400' },
  procurement: { label: 'Procurement', color: '#4ade80', text: 'text-green-400' },
  checker: { label: 'Checker', color: '#f87171', text: 'text-red-400' },
  docs: { label: 'Docs', color: '#a78bfa', text: 'text-violet-400' },
  copilot: { label: 'Co-pilot', color: 'linear-gradient(135deg,#e879f9,#38bdf8)', text: 'text-fuchsia-300' },
  asset: { label: 'Asset', color: '#2dd4bf', text: 'text-teal-400' },
  system: { label: 'System', color: '#71717a', text: 'text-zinc-400' },
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
 * matched Warn amber and the default pipe blue, so the cooling chain vanished in 3D.
 */
export const CHAIN_COLORS = { electrical: '#fb923c', cooling: '#c084fc' } as const
