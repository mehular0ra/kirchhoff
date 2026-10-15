import { Stamp } from 'lucide-react'
import { fmtTs, shortHash } from '@/lib/format'
import type { Approval, Revision } from '@/lib/types'

/** Reviewer stamp (spec §12 screen 7): name, role, time and the revision hash it signs. */
export function ApprovalStamp({ approval, revision }: { approval: Approval; revision: Revision }) {
  const approved = approval.decision === 'approved'
  return (
    <figure
      aria-label="Approval stamp"
      className={`flex max-w-md flex-col gap-1 rounded-lg border-2 p-4 ${approved ? 'border-emerald-500/70 bg-emerald-500/5' : 'border-rose-500/70 bg-rose-500/5'}`}
    >
      <span className={`inline-flex items-center gap-2 text-sm font-semibold uppercase tracking-widest ${approved ? 'text-emerald-700' : 'text-rose-700'}`}>
        <Stamp aria-hidden className="size-5" /> {approved ? 'Approved' : 'Rejected'}
      </span>
      <span className="text-base text-foreground">{approval.approver_name}</span>
      <span className="text-sm text-zinc-700">{approval.role}</span>
      <span className="text-xs text-muted-foreground">{fmtTs(approval.ts)}</span>
      <span className="font-mono text-xs text-muted-foreground" title={revision.hash}>
        Revision {revision.id} · sha256 {shortHash(revision.hash)}
      </span>
      {approval.comment && <figcaption className="mt-1 text-sm text-zinc-700">“{approval.comment}”</figcaption>}
    </figure>
  )
}
