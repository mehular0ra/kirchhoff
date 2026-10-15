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

export type CitationKind = 'tender' | 'drawing'

export interface WhatIfView {
  result: WhatIfResult
  /** "precomputed" when served from the static bundle (spec §6.4), "engine" when from /api/what-if. */
  origin: 'precomputed' | 'engine'
}

interface UiState {
  tab: CanvasTab
  viewRev: string | null // null = latest revision
  /** null = default: on for a signed revision that has a parent, so Hall A opens on its fix story (UX-1 I1). */
  compare: boolean | null
  findingId: string | null
  focusId: string | null
  citation: Citation | null
  /** What the cited PDF is, when the opener knows (the Docs tab); else PdfViewer reads it from the doc id. */
  citationKind: CitationKind | null
  whatIf: WhatIfView | null
  autonomy: Autonomy
  setTab(tab: CanvasTab): void
  setViewRev(rev: string | null): void
  setCompare(on: boolean): void
  openFinding(id: string): void
  closeFinding(): void
  /**
   * Focuses an element on a canvas. From Matrix/Options/Docs (or a canvas that does not draw it, per
   * `drawnOn`) the tab switches to one that does, so "Show on canvas" always shows something (I5).
   */
  focus(id: string | null, drawnOn?: ('hall' | 'sld')[]): void
  openCitation(c: Citation, kind?: CitationKind | null): void
  closeCitation(): void
  setWhatIf(w: WhatIfView | null): void
  setAutonomy(a: Autonomy): void
  resetWorkspaceUi(): void
}

const initial = {
  tab: 'hall' as CanvasTab,
  viewRev: null,
  compare: null,
  findingId: null,
  focusId: null,
  citation: null,
  citationKind: null,
  whatIf: null,
}

export const useUi = create<UiState>()((set) => ({
  ...initial,
  autonomy: 'ask',
  setTab: (tab) => set({ tab }),
  // A what-if was computed for the revision on screen; switching revision drops it (M13).
  setViewRev: (viewRev) => set((s) => (viewRev === s.viewRev ? s : { viewRev, whatIf: null })),
  setCompare: (compare) => set({ compare }),
  openFinding: (findingId) => set({ findingId }),
  closeFinding: () => set({ findingId: null }),
  focus: (focusId, drawnOn = ['hall', 'sld']) =>
    set((s) => {
      if (!focusId) return { focusId }
      if (!drawnOn.length) return {} // no canvas draws it: never switch to an empty view
      const shows = (t: CanvasTab) => (t === 'hall' || t === 'sld') && drawnOn.includes(t)
      return { focusId, tab: shows(s.tab) ? s.tab : (drawnOn[0] ?? 'hall') }
    }),
  openCitation: (citation, citationKind = null) => set({ citation, citationKind }),
  closeCitation: () => set({ citation: null, citationKind: null }),
  setWhatIf: (whatIf) => set({ whatIf }),
  setAutonomy: (autonomy) => set({ autonomy }),
  resetWorkspaceUi: () => set(initial),
}))
