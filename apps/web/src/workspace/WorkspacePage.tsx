import { lazy, Suspense, useEffect, type ReactNode } from 'react'
import { useParams, useSearchParams } from 'react-router'
import { EmptyState } from '@/components/Labels'
import { useProjectData } from '@/data/useProjectData'
import { useWorldProject } from '@/data/useWorld'
import type { Project } from '@/lib/types'
import { completeItem } from '@/onboarding/checklist/checklistStore'
import { CANVAS_TABS, useUi, type CanvasTab } from '@/store/ui'
import { AgentLanes } from './AgentLanes'
import { CanvasTabs } from './CanvasTabs'
import { DocsTab } from './docs/DocsTab'
import { FindingDrawer } from './finding/FindingDrawer'
import { GateBanner } from './gates/GateBanner'
import { OptionCards } from './gates/OptionCards'
import { HeaderActions } from './HeaderActions'
import { ComplianceMatrix } from './matrix/ComplianceMatrix'
import { RequirementsPanel } from './RequirementsPanel'
import { RevisionTimeline } from './RevisionTimeline'
import { RunBar } from './RunBar'
import { SldView } from './sld/SldView'
import { LIVE_TARGET, StartRunPanel } from './StartRunPanel'
import { WorkspaceHeader } from './WorkspaceHeader'
import { WorkspaceProvider } from './WorkspaceContext'

// three.js and pdf.js are large: load them only when the 3D tab or a citation opens.
const HallView = lazy(() => import('./hall/HallView'))
const PdfViewer = lazy(() => import('./finding/PdfViewer'))

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
  if (pid === LIVE_TARGET && !runId && !replay) return <StartRunPanel project={project} />
  return <LoadedWorkspace key={`${pid}:${runId}:${replay}`} pid={pid} runId={runId} replay={replay} project={project} />
}

function LoadedWorkspace({ pid, runId, replay, project }: { pid: string; runId: string | null; replay: boolean; project: Project | null }) {
  const data = useProjectData(pid, { runId, replay, project })
  useUrlState(pid)
  const signed = (data.bundle?.approvals.length ?? 0) > 0
  useEffect(() => {
    if (signed) completeItem('open_signed')
  }, [signed])

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
    options: <OptionCards />,
    docs: <DocsTab />,
  }

  return (
    <WorkspaceProvider bundle={data.bundle} source={data.source}>
      <div className="grid h-full grid-rows-[auto_minmax(0,1fr)_auto]">
        <WorkspaceHeader actions={<HeaderActions />} />
        <div className="grid min-h-0 grid-cols-[16rem_minmax(0,1fr)_20rem]">
          <aside className="min-h-0 border-r">
            <AgentLanes />
          </aside>
          <section aria-label="Canvas" className="flex min-h-0 flex-col">
            <RunBar replay={data.replay} controls={data.controls} />
            <GateBanner />
            <div className="min-h-0 flex-1">
              <CanvasTabs panes={panes} />
            </div>
          </section>
          <aside aria-label="Co-pilot" className="min-h-0 overflow-y-auto border-l">
            <RequirementsPanel />
          </aside>
        </div>
        <RevisionTimeline />
      </div>
      <FindingDrawer />
      <Suspense fallback={null}>
        <PdfViewer />
      </Suspense>
    </WorkspaceProvider>
  )
}
