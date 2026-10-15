import { Stamp } from 'lucide-react'
import { Link, useSearchParams } from 'react-router'
import { Button } from '@/components/ui/button'
import { approvalFor, latestRevision } from '@/lib/select'
import { useUi } from '@/store/ui'
import { AutonomySwitch } from './gates/AutonomySwitch'
import { useWorkspace } from './WorkspaceContext'

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
      <AutonomySwitch value={run?.autonomy ?? autonomy} onChange={setAutonomy} locked={!!run} />
      {latest && signed ? (
        <Button asChild size="sm" variant="outline" data-tour="sign-off" className="text-emerald-200">
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
