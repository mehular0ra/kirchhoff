import { lazy, Suspense, useEffect, type ReactNode } from 'react'
import { useParams, useSearchParams } from 'react-router'
import { EmptyState } from '@/components/Labels'
import { useProjectData } from '@/data/useProjectData'
import { useWorldProject } from '@/data/useWorld'
import { CANVAS_TABS, useUi, type CanvasTab } from '@/store/ui'
import { AgentLanes } from './AgentLanes'
import { CanvasTabs } from './CanvasTabs'
import { ComplianceMatrix } from './matrix/ComplianceMatrix'
import { RequirementsPanel } from './RequirementsPanel'
import { RevisionTimeline } from './RevisionTimeline'
import { SldView } from './sld/SldView'
import { WorkspaceHeader } from './WorkspaceHeader'
import { WorkspaceProvider } from './WorkspaceContext'

const HallView = lazy(() => import('./hall/HallView'))

/** Resets UI state per project, then applies ?tab=, ?rev= and ?finding= whenever they change (tour, deep links). */
function useUrlState(pid: string) {
  const [params] = useSearchParams()
  const tab = params.get('tab')
  const rev = params.get('rev')
  const finding = params.get('finding')
  useEffect(() => {
    useUi.getState().resetWorkspaceUi()
  }, [pid])
  useEffect(() => {
    const ui = useUi.getState()
    if (tab && CANVAS_TABS.some((t) => t.id === tab)) ui.setTab(tab as CanvasTab)
    if (rev) ui.setViewRev(rev)
    if (finding) ui.openFinding(finding)
  }, [pid, tab, rev, finding])
}

export function WorkspacePage() {
  const { pid = '' } = useParams()
  const [params] = useSearchParams()
  const runId = params.get('run')
  const replay = params.get('replay') === '1'
  const project = useWorldProject(pid)
  const data = useProjectData(pid, { runId, replay, project })
  useUrlState(pid)

  if (data.status === 'error' && !data.bundle) {
    return (
      <EmptyState title="This project's data is not available">
        {data.error}. Seed projects load from static files; live runs need the backend.
      </EmptyState>
    )
  }
  if (!data.bundle) return <EmptyState title="Loading workspace…" />

  const panes: Record<CanvasTab, ReactNode> = {
    hall: (
      <Suspense fallback={<EmptyState title="Loading 3D hall…" />}>
        <HallView />
      </Suspense>
    ),
    sld: <SldView />,
    matrix: <ComplianceMatrix />,
    options: <EmptyState title="Topology options">Costed options appear here after Power and Procurement.</EmptyState>,
    docs: <EmptyState title="Documents">Tender, drawings and exports appear here.</EmptyState>,
  }

  return (
    <WorkspaceProvider bundle={data.bundle} source={data.source}>
      <div className="grid h-full grid-rows-[auto_minmax(0,1fr)_auto]">
        <WorkspaceHeader />
        <div className="grid min-h-0 grid-cols-[16rem_minmax(0,1fr)_20rem]">
          <aside className="min-h-0 border-r">
            <AgentLanes />
          </aside>
          <section aria-label="Canvas" className="min-h-0">
            <CanvasTabs panes={panes} />
          </section>
          <aside aria-label="Co-pilot" className="min-h-0 overflow-y-auto border-l">
            <RequirementsPanel />
          </aside>
        </div>
        <RevisionTimeline />
      </div>
    </WorkspaceProvider>
  )
}
