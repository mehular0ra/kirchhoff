import { Stamp } from 'lucide-react'
import { Fragment } from 'react'
import { approvalFor, findingsFor, signedRevision } from '@/lib/select'
import { RevisionVerdict } from './RevisionVerdict'
import { useWorkspace } from './WorkspaceContext'

/**
 * One line that tells the design's story under the canvas tabs (UX-1 I1):
 * "r1 · 149 checks · 2 fail → r2 · 150 checks · all pass · signed by Priya Raman".
 * Check counts are counted finding records; the signer comes from the approval record.
 */
export function StoryStrip() {
  const { bundle } = useWorkspace()
  const signed = signedRevision(bundle)
  if (bundle.revisions.length < 2 && !signed) return null
  const approval = signed ? approvalFor(bundle, signed.id) : null
  return (
    <div role="group" aria-label="Revision story" className="flex min-w-0 flex-wrap items-center gap-y-0.5 whitespace-pre text-xs text-zinc-300">
      {bundle.revisions.map((r, i) => {
        const findings = findingsFor(bundle, r.id)
        return (
          <Fragment key={r.id}>
            {i > 0 && <span className="text-zinc-500"> → </span>}
            <span className="font-mono text-zinc-100">{r.id}</span>
            <span className="text-zinc-400">{findings.length > 0 ? ` · ${findings.length} checks · ` : ' · '}</span>
            <RevisionVerdict findings={findings} />
          </Fragment>
        )
      })}
      {approval && (
        <>
          <span className="text-zinc-400"> · </span>
          <span className="inline-flex items-center gap-1 text-emerald-300">
            <Stamp aria-hidden className="size-3.5" />
            {`signed by ${approval.approver_name}`}
          </span>
        </>
      )}
    </div>
  )
}
