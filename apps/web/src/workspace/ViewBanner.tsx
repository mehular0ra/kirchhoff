import { FlaskConical, History, Undo2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { latestRevision, revisionLabel, signedRevision } from '@/lib/select'
import { useUi } from '@/store/ui'
import { chipLabel } from './copilot/useWhatIf'
import { useWorkspace } from './WorkspaceContext'

/**
 * Over the canvas (3D hall, SLD, matrix): says when what is drawn is not the approved design, because a what-if is laid
 * over it or another revision is on screen, and gives one way back. Without it the only way out of a what-if was a small
 * ✕ in the side panel, and a visitor who did not see it reloaded the page.
 */
export function ViewBanner() {
  const { bundle, rev } = useWorkspace()
  const whatIf = useUi((s) => s.whatIf)
  const setWhatIf = useUi((s) => s.setWhatIf)
  const setViewRev = useUi((s) => s.setViewRev)
  const head = latestRevision(bundle)
  // The approved design: the signed revision when there is one, else the latest.
  const signed = signedRevision(bundle)
  const target = signed ?? head
  if (!target || !rev) return null
  const away = rev.id !== target.id
  if (!whatIf && !away) return null

  const back = () => {
    setViewRev(target.id === head?.id ? null : target.id, { source: 'auto' })
    setWhatIf(null)
  }
  const Icon = whatIf ? FlaskConical : History
  return (
    <div role="status" className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b bg-amber-500/10 px-3 py-1.5 text-xs text-amber-900">
      <span className="inline-flex items-center gap-1.5">
        <Icon aria-hidden className="size-3.5 shrink-0" />
        {whatIf
          ? `What-if on screen: ${chipLabel(whatIf.result)} on ${revisionLabel(rev)} · not saved`
          : `Showing ${revisionLabel(rev)}, not the ${signed ? 'signed' : 'latest'} design.`}
      </span>
      <Button size="xs" variant="outline" className="ml-auto" onClick={back}>
        <Undo2 aria-hidden /> Back to {revisionLabel(target)}
      </Button>
    </div>
  )
}
