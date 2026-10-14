// Workspace UI state shared by canvas tabs, drawer, co-pilot and tour.
import { create } from 'zustand'
import type { Autonomy, Citation, WhatIfResult } from '@/lib/types'

export type CanvasTab = 'hall' | 'sld' | 'matrix' | 'options' | 'docs'
export const CANVAS_TABS: { id: CanvasTab; label: string }[] = [
  { id: 'hall', label: '3D Hall' },
  { id: 'sld', label: 'SLD' },
  { id: 'matrix', label: 'Matrix' },
  { id: 'options', label: 'Options' },
  { id: 'docs', label: 'Docs' },
]

export interface WhatIfView {
  result: WhatIfResult
  /** "precomputed" when served from the static bundle (spec §6.4), "engine" when from /api/what-if. */
  origin: 'precomputed' | 'engine'
}

interface UiState {
  tab: CanvasTab
  viewRev: string | null // null = latest revision
  compare: boolean
  findingId: string | null
  focusId: string | null
  citation: Citation | null
  whatIf: WhatIfView | null
  autonomy: Autonomy
  setTab(tab: CanvasTab): void
  setViewRev(rev: string | null): void
  setCompare(on: boolean): void
  openFinding(id: string): void
  closeFinding(): void
  focus(id: string | null): void
  openCitation(c: Citation): void
  closeCitation(): void
  setWhatIf(w: WhatIfView | null): void
  setAutonomy(a: Autonomy): void
  resetWorkspaceUi(): void
}

const initial = {
  tab: 'hall' as CanvasTab,
  viewRev: null,
  compare: false,
  findingId: null,
  focusId: null,
  citation: null,
  whatIf: null,
}

export const useUi = create<UiState>()((set) => ({
  ...initial,
  autonomy: 'ask',
  setTab: (tab) => set({ tab }),
  setViewRev: (viewRev) => set({ viewRev }),
  setCompare: (compare) => set({ compare }),
  openFinding: (findingId) => set({ findingId }),
  closeFinding: () => set({ findingId: null }),
  focus: (focusId) => set({ focusId }),
  openCitation: (citation) => set({ citation }),
  closeCitation: () => set({ citation: null }),
  setWhatIf: (whatIf) => set({ whatIf }),
  setAutonomy: (autonomy) => set({ autonomy }),
  resetWorkspaceUi: () => set(initial),
}))
