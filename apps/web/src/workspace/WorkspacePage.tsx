import { TriangleAlert } from 'lucide-react'
import { lazy, Suspense, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { useParams, useSearchParams } from 'react-router'
import { EmptyState } from '@/components/Labels'
import { LoadError } from '@/components/LoadError'
import { PaneSplitter } from '@/components/PaneSplitter'
import { useProjectData, type ProjectData } from '@/data/useProjectData'
import { useWorldProject } from '@/data/useWorld'
import type { Project } from '@/lib/types'
import { Checklist } from '@/onboarding/checklist/Checklist'
import { completeItem } from '@/onboarding/checklist/checklistStore'
import { COPILOT_W, LANES_W, useLayout } from '@/store/layout'
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
import { ViewBanner } from './ViewBanner'
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

/** The canvas never gets narrower than this (22rem): a side panel stops growing before it would take that. */
const CANVAS_MIN_PX = 352
const SPLITTER_PX = 6

/**
 * The agent lanes, the canvas and the co-pilot side by side. The two side panels can be dragged wider or narrower
 * (their edges are separators), hidden from the top bar, and keep their size across reloads (store/layout.ts). A
 * hidden panel stays mounted, so the co-pilot's conversation and voice session are not lost by hiding it.
 * Each child names its own grid column, so a hidden one does not shift the others.
 */
function WorkspacePanes({ data, panes }: { data: ProjectData; panes: Record<CanvasTab, ReactNode> }) {
  const { lanesOpen, copilotOpen, lanesW, copilotW, setLanesW, setCopilotW } = useLayout()
  const gridRef = useRef<HTMLDivElement>(null)
  const [gridW, setGridW] = useState(0)
  useLayoutEffect(() => {
    const el = gridRef.current
    if (!el) return
    const measure = () => setGridW(el.clientWidth)
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  // How wide a panel may get before the canvas would drop below its minimum (unknown until measured).
  const room = (other: number) => (gridW > 0 ? gridW - CANVAS_MIN_PX - SPLITTER_PX - other : Infinity)
  const lanesMax = Math.max(LANES_W.min, Math.min(LANES_W.max, room(copilotOpen ? copilotW + SPLITTER_PX : 0)))
  const copilotMax = Math.max(COPILOT_W.min, Math.min(COPILOT_W.max, room(lanesOpen ? lanesW + SPLITTER_PX : 0)))
  // A saved width that no longer fits a smaller window is shown at the width that does, so the canvas keeps its minimum.
  const lanesShown = Math.min(lanesW, lanesMax)
  const copilotShown = Math.min(copilotW, copilotMax)
  const setCopilotUsed = useLayout((s) => s.setCopilotUsed)
  useEffect(() => setCopilotUsed(copilotShown), [copilotShown, setCopilotUsed])
  const columns = [
    lanesOpen ? `${lanesShown}px ${SPLITTER_PX}px` : '0px 0px',
    'minmax(22rem,1fr)',
    copilotOpen ? `${SPLITTER_PX}px ${copilotShown}px` : '0px 0px',
  ].join(' ')
  return (
    <div ref={gridRef} className="grid min-h-0 overflow-x-auto" style={{ gridTemplateColumns: columns }}>
      <aside hidden={!lanesOpen} style={{ gridColumn: 1 }} className={`${lanesOpen ? 'flex' : ''} min-h-0 min-w-0 flex-col overflow-hidden border-r border-[var(--glass-edge)] bg-[var(--glass)] backdrop-blur-md`}>
        <div className="min-h-0 flex-1">
          <AgentLanes />
        </div>
        {/* Docked in the lanes column so it never covers matrix ids or the canvas legend (M4). */}
        <div className="shrink-0 p-2">
          <Checklist docked />
        </div>
      </aside>
      {lanesOpen && (
        <PaneSplitter
          label="Resize the agents lane"
          value={lanesShown}
          min={LANES_W.min}
          max={lanesMax}
          grow={1}
          onChange={setLanesW}
          onReset={() => setLanesW(LANES_W.def)}
          className="[grid-column:2]"
        />
      )}
      <section aria-label="Canvas" style={{ gridColumn: 3 }} className="flex min-h-0 min-w-0 flex-col">
        <RunBar replay={data.replay} controls={data.controls} />
        {data.status === 'error' && data.error && (
          // M2: a live listener that fails after the first snapshot is no longer silent.
          <p role="alert" className="flex items-center gap-1.5 border-b bg-amber-500/10 px-3 py-1.5 text-xs text-amber-800">
            <TriangleAlert aria-hidden className="size-3.5 shrink-0" /> Live updates stopped ({data.error}). Reload to reconnect; what is shown is the last state received.
          </p>
        )}
        <GateBanner />
        <ViewBanner />
        <div className="min-h-0 flex-1">
          <CanvasTabs panes={panes} aside={<StoryStrip />} />
        </div>
      </section>
      {copilotOpen && (
        <PaneSplitter
          label="Resize the co-pilot"
          value={copilotShown}
          min={COPILOT_W.min}
          max={copilotMax}
          grow={-1}
          onChange={setCopilotW}
          onReset={() => setCopilotW(COPILOT_W.def)}
          className="[grid-column:4]"
        />
      )}
      <aside aria-label="Co-pilot" hidden={!copilotOpen} style={{ gridColumn: 5 }} className="min-h-0 min-w-0 overflow-y-auto border-l border-[var(--glass-edge)] bg-[var(--glass)] backdrop-blur-md">
        <CoPilotPanel />
      </aside>
    </div>
  )
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
        <WorkspacePanes data={data} panes={panes} />
        <RevisionTimeline />
      </div>
      <FindingDrawer />
      <Suspense fallback={null}>
        <PdfViewer />
      </Suspense>
    </WorkspaceProvider>
  )
}
