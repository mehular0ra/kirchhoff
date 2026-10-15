import { TriangleAlert } from 'lucide-react'
import { lazy, Suspense, useEffect, type ReactNode } from 'react'
import { useParams, useSearchParams } from 'react-router'
import { EmptyState } from '@/components/Labels'
import { LoadError } from '@/components/LoadError'
import { useProjectData } from '@/data/useProjectData'
import { useWorldProject } from '@/data/useWorld'
import type { Project } from '@/lib/types'
import { Checklist } from '@/onboarding/checklist/Checklist'
import { completeItem } from '@/onboarding/checklist/checklistStore'
import { CANVAS_TABS, useUi, type CanvasTab } from '@/store/ui'
import { AgentLanes } from './AgentLanes'
import { ArchivedSummary } from './ArchivedSummary'
import { CanvasTabs } from './CanvasTabs'
import { CoPilotPanel } from './copilot/CoPilotPanel'
import { DesktopNote } from './DesktopNote'
import { DocsTab } from './docs/DocsTab'
import { FindingDrawer } from './finding/FindingDrawer'
import { GateBanner } from './gates/GateBanner'
import { OptionCards } from './gates/OptionCards'
import { HeaderActions } from './HeaderActions'
import { ComplianceMatrix } from './matrix/ComplianceMatrix'
import { RevisionTimeline } from './RevisionTimeline'
import { RunBar } from './RunBar'
import { SldView } from './sld/SldView'
import { LIVE_TARGET, StartRunPanel } from './StartRunPanel'
import { StoryStrip } from './StoryStrip'
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

  if (data.status === 'error' && !data.bundle) return <LoadError error={data.error} notFoundTitle={runId ? 'Run not found' : 'Project not found'} />
  if (!data.bundle) return <EmptyState title="Loading workspace…" />
  // An archived project with no design revisions is read-only history, not an empty workspace (D12).
  if (data.source === 'static' && data.bundle.project.state === 'archived' && !data.bundle.revisions.length)
    return <ArchivedSummary bundle={data.bundle} />

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
      {/* One column that may shrink below its content, so a phone never widens the page: the panes scroll
          sideways inside their own frame instead, and the tour's cards stay on the visible screen (D13). */}
      <div className="grid h-full grid-cols-[minmax(0,1fr)] grid-rows-[auto_minmax(0,1fr)_auto]">
        <div className="min-w-0">
          <WorkspaceHeader actions={<HeaderActions />} />
          <DesktopNote reviewHref={data.bundle.revisions.length ? `/app/p/${pid}/review/${data.bundle.revisions[data.bundle.revisions.length - 1].id}${runId ? `?run=${runId}` : ''}` : null} />
        </div>
        <div className="grid min-h-0 grid-cols-[16rem_minmax(22rem,1fr)_20rem] overflow-x-auto">
          <aside className="flex min-h-0 flex-col border-r">
            <div className="min-h-0 flex-1">
              <AgentLanes />
            </div>
            {/* Docked in the lanes column so it never covers matrix ids or the canvas legend (M4). */}
            <div className="shrink-0 p-2">
              <Checklist docked />
            </div>
          </aside>
          <section aria-label="Canvas" className="flex min-h-0 flex-col">
            <RunBar replay={data.replay} controls={data.controls} />
            {data.status === 'error' && data.error && (
              // M2: a live listener that fails after the first snapshot is no longer silent.
              <p role="alert" className="flex items-center gap-1.5 border-b bg-amber-500/10 px-3 py-1.5 text-xs text-amber-200">
                <TriangleAlert aria-hidden className="size-3.5 shrink-0" /> Live updates stopped ({data.error}). Reload to reconnect; what is shown is the last state received.
              </p>
            )}
            <GateBanner />
            <div className="min-h-0 flex-1">
              <CanvasTabs panes={panes} aside={<StoryStrip />} />
            </div>
          </section>
          <aside aria-label="Co-pilot" className="min-h-0 overflow-y-auto border-l">
            <CoPilotPanel />
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
