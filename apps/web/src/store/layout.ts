// Where the workspace's side panels are: how wide the agent lanes and the co-pilot are, and whether each one is open.
// Kept in localStorage (like the getting-started checklist), so a reload does not undo a layout the visitor chose.
import { create } from 'zustand'
import { readJson, writeJson } from '@/lib/storage'

interface Range {
  min: number
  max: number
  def: number
}

/** Widths in pixels. The canvas in the middle takes whatever is left (and never less than 22rem, see WorkspacePage). */
export const LANES_W: Range = { min: 160, max: 480, def: 256 }
export const COPILOT_W: Range = { min: 260, max: 600, def: 320 }

const KEY = 'layout'
const clamp = (n: number, r: Range) => Math.min(r.max, Math.max(r.min, Math.round(n)))

interface Stored {
  lanesOpen: boolean
  copilotOpen: boolean
  lanesW: number
  copilotW: number
}

interface LayoutState extends Stored {
  setLanesW(px: number): void
  setCopilotW(px: number): void
  toggleLanes(): void
  toggleCopilot(): void
  /** Shows both panels again, at the widths the visitor chose (the guided tour points into them). */
  openAll(): void
  reset(): void
}

const DEFAULTS: Stored = { lanesOpen: true, copilotOpen: true, lanesW: LANES_W.def, copilotW: COPILOT_W.def }

function restore(): Stored {
  const raw = readJson<Partial<Record<keyof Stored, unknown>> | null>(KEY, null)
  if (!raw || typeof raw !== 'object') return DEFAULTS
  const width = (v: unknown, r: Range) => (typeof v === 'number' && Number.isFinite(v) ? clamp(v, r) : r.def)
  const open = (v: unknown) => (typeof v === 'boolean' ? v : true)
  return { lanesOpen: open(raw.lanesOpen), copilotOpen: open(raw.copilotOpen), lanesW: width(raw.lanesW, LANES_W), copilotW: width(raw.copilotW, COPILOT_W) }
}

export const useLayout = create<LayoutState>()((set) => ({
  ...restore(),
  setLanesW: (px) => set({ lanesW: clamp(px, LANES_W) }),
  setCopilotW: (px) => set({ copilotW: clamp(px, COPILOT_W) }),
  toggleLanes: () => set((s) => ({ lanesOpen: !s.lanesOpen })),
  toggleCopilot: () => set((s) => ({ copilotOpen: !s.copilotOpen })),
  openAll: () => set({ lanesOpen: true, copilotOpen: true }),
  reset: () => set(DEFAULTS),
}))

useLayout.subscribe((s) =>
  writeJson(KEY, { lanesOpen: s.lanesOpen, copilotOpen: s.copilotOpen, lanesW: s.lanesW, copilotW: s.copilotW } satisfies Stored),
)
