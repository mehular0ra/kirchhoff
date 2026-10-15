// Derived, memoised view of the bundle for the current workspace (selected revision, statuses,
// diff and what-if overlays). Every canvas reads it through useWorkspace().
import { createContext, useContext, useMemo, type ReactNode } from 'react'
import { diffModels, type ModelDiff } from '@/lib/diff'
import { chainHighlights } from '@/lib/impact'
import type { Discipline } from '@/lib/model'
import {
  approvalFor,
  currentRun,
  findingsFor,
  latestRevision,
  parentRevision,
  revisionById,
  revisionRef,
  statusByElement,
  type DataSource,
} from '@/lib/select'
import type { Bundle, DesignModel, Finding, FindingStatus, Revision, RunRecord, WhatIfResult } from '@/lib/types'
import { useUi } from '@/store/ui'

export interface WorkspaceView {
  bundle: Bundle
  source: DataSource
  rev: Revision | null
  parent: Revision | null
  model: DesignModel | null
  findings: Finding[]
  status: Map<string, FindingStatus>
  /** "Compare with parent" as shown: the visitor's choice, else on for a signed revision with a parent (I1). */
  compare: boolean
  /** Present only while "Compare with parent" is on and the revision has a parent. */
  diff: ModelDiff | null
  /** Elements that failed in the parent revision and pass now (cold-open "turns green"). */
  resolved: Set<string>
  /** What-if overlay: the result, element → impact-chain disciplines, and what-if statuses. */
  whatIf: WhatIfResult | null
  highlights: Map<string, Discipline[]>
  whatIfStatus: Map<string, FindingStatus>
  revRef: string | null
  run: RunRecord | null
}

export function buildView(bundle: Bundle, source: DataSource, ui: Pick<ReturnType<typeof useUi.getState>, 'viewRev' | 'compare' | 'whatIf'>): WorkspaceView {
  const rev = revisionById(bundle, ui.viewRev) ?? latestRevision(bundle)
  const parent = parentRevision(bundle, rev)
  const findings = findingsFor(bundle, rev?.id)
  const status = statusByElement(findings)
  const parentStatus = statusByElement(findingsFor(bundle, parent?.id))
  const resolved = new Set([...parentStatus].filter(([id, s]) => s === 'fail' && status.get(id) === 'pass').map(([id]) => id))
  const model = rev?.model ?? null
  const whatIf = ui.whatIf?.result ?? null
  const compare = !!parent && (ui.compare ?? !!approvalFor(bundle, rev?.id))
  return {
    bundle,
    source,
    rev,
    parent,
    model,
    findings,
    status,
    compare,
    diff: compare && parent ? diffModels(parent.model, model) : null,
    resolved,
    whatIf,
    highlights: chainHighlights(whatIf, model),
    whatIfStatus: whatIf ? statusByElement(whatIf.findings) : new Map(),
    revRef: rev ? revisionRef(bundle, rev.id, source) : null,
    run: currentRun(bundle),
  }
}

const Ctx = createContext<WorkspaceView | null>(null)

export function WorkspaceProvider({ bundle, source, children }: { bundle: Bundle; source: DataSource; children: ReactNode }) {
  const viewRev = useUi((s) => s.viewRev)
  const compare = useUi((s) => s.compare)
  const whatIf = useUi((s) => s.whatIf)
  const view = useMemo(() => buildView(bundle, source, { viewRev, compare, whatIf }), [bundle, source, viewRev, compare, whatIf])
  return <Ctx.Provider value={view}>{children}</Ctx.Provider>
}

export function useWorkspace(): WorkspaceView {
  const v = useContext(Ctx)
  if (!v) throw new Error('useWorkspace outside WorkspaceProvider')
  return v
}
