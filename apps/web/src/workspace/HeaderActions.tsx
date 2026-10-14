import { Stamp } from 'lucide-react'
import { Link, useSearchParams } from 'react-router'
import { Button } from '@/components/ui/button'
import { latestRevision } from '@/lib/select'
import { useUi } from '@/store/ui'
import { AutonomySwitch } from './gates/AutonomySwitch'
import { useWorkspace } from './WorkspaceContext'

/** Header right side: [Ask|Auto] and [Request sign-off] (spec §12 workspace header). */
export function HeaderActions() {
  const { bundle, run } = useWorkspace()
  const autonomy = useUi((s) => s.autonomy)
  const setAutonomy = useUi((s) => s.setAutonomy)
  const [params] = useSearchParams()
  const latest = latestRevision(bundle)
  const atReview = run?.status === 'at_gate' && run.gate === 'review'
  const runQ = params.get('run') ? `?run=${params.get('run')}` : ''
  return (
    <>
      <AutonomySwitch value={run?.autonomy ?? autonomy} onChange={setAutonomy} locked={!!run} />
      {latest ? (
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
