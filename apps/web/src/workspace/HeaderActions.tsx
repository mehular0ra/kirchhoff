import { PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen, RotateCcw, Stamp } from 'lucide-react'
import { Link, useSearchParams } from 'react-router'
import { Button } from '@/components/ui/button'
import { approvalFor, latestRevision } from '@/lib/select'
import { COPILOT_W, LANES_W, useLayout } from '@/store/layout'
import { useUi } from '@/store/ui'
import { AutonomySwitch } from './gates/AutonomySwitch'
import { useWorkspace } from './WorkspaceContext'

/**
 * Shows or hides the agents lane and the co-pilot, so the canvas can have the whole width. A hidden panel stays mounted
 * (its conversation and voice session keep going); "Reset panel layout" appears only once the layout is not the usual one.
 */
function PaneToggles() {
  const { lanesOpen, copilotOpen, lanesW, copilotW, toggleLanes, toggleCopilot, reset } = useLayout()
  const changed = !lanesOpen || !copilotOpen || lanesW !== LANES_W.def || copilotW !== COPILOT_W.def
  return (
    <div role="group" aria-label="Panels" className="flex items-center gap-1">
      <Button
        variant="outline"
        size="icon-sm"
        aria-label="Agents lane"
        aria-pressed={lanesOpen}
        title={lanesOpen ? 'Hide the agents lane' : 'Show the agents lane'}
        onClick={toggleLanes}
      >
        {lanesOpen ? <PanelLeftClose aria-hidden /> : <PanelLeftOpen aria-hidden />}
      </Button>
      <Button
        variant="outline"
        size="icon-sm"
        aria-label="Co-pilot"
        aria-pressed={copilotOpen}
        title={copilotOpen ? 'Hide the co-pilot' : 'Show the co-pilot'}
        onClick={toggleCopilot}
      >
        {copilotOpen ? <PanelRightClose aria-hidden /> : <PanelRightOpen aria-hidden />}
      </Button>
      {changed && (
        <Button variant="ghost" size="icon-sm" aria-label="Reset panel layout" title="Reset panel layout" onClick={reset}>
          <RotateCcw aria-hidden />
        </Button>
      )}
    </div>
  )
}

/**
 * Header right side: [Ask|Auto] and [Request sign-off] (spec §12 workspace header). A latest revision
 * that is already signed shows "Signed · view review" instead (UX-1 D4: never ask to sign a signed design).
 */
export function HeaderActions() {
  const { bundle, run } = useWorkspace()
  const autonomy = useUi((s) => s.autonomy)
  const setAutonomy = useUi((s) => s.setAutonomy)
  const [params] = useSearchParams()
  const latest = latestRevision(bundle)
  const atReview = run?.status === 'at_gate' && run.gate === 'review'
  const runQ = params.get('run') ? `?run=${params.get('run')}` : ''
  const signed = !!latest && !!approvalFor(bundle, latest.id)
  return (
    <>
      <PaneToggles />
      <AutonomySwitch value={run?.autonomy ?? autonomy} onChange={setAutonomy} locked={!!run} />
      {latest && signed ? (
        <Button asChild size="sm" variant="outline" data-tour="sign-off" className="text-emerald-700">
          <Link to={`/app/p/${bundle.project.id}/review/${latest.id}${runQ}`}>
            <Stamp aria-hidden /> Signed · view review
          </Link>
        </Button>
      ) : latest ? (
        <Button asChild size="sm" variant={atReview ? 'default' : 'outline'} data-tour="sign-off">
          <Link to={`/app/p/${bundle.project.id}/review/${latest.id}${runQ}`}>
            <Stamp aria-hidden /> {atReview ? 'Review and sign' : 'Request sign-off'}
          </Link>
        </Button>
      ) : (
        <Button size="sm" variant="outline" disabled>
          <Stamp aria-hidden /> Request sign-off
        </Button>
      )}
    </>
  )
}
