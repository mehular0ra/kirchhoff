import { cn } from 'cn'
import { GitCompareArrows, Stamp } from 'lucide-react'
import { Link, useLocation } from 'react-router'
import { Switch } from '@/components/ui/switch'
import { approvalFor, findingsFor } from '@/lib/select'
import { useUi } from '@/store/ui'
import { RevisionVerdict } from './RevisionVerdict'
import { useWorkspace } from './WorkspaceContext'

export function RevisionTimeline() {
  const { bundle, rev, parent, compare } = useWorkspace()
  const setViewRev = useUi((s) => s.setViewRev)
  const setCompare = useUi((s) => s.setCompare)
  const runId = new URLSearchParams(useLocation().search).get('run')
  if (!bundle.revisions.length) {
    return (
      <footer className="flex h-10 items-center border-t px-4 text-xs text-muted-foreground">
        Revisions appear here after the Checker's first pass.
      </footer>
    )
  }
  return (
    <footer aria-label="Revisions" className="flex h-11 items-center gap-3 overflow-x-auto whitespace-nowrap border-t px-4 text-xs">
      <span className="font-medium uppercase tracking-wide text-muted-foreground">Revisions</span>
      <ol className="flex items-center gap-2">
        {bundle.revisions.map((r, i) => {
          const approval = approvalFor(bundle, r.id)
          const active = r.id === rev?.id
          return (
            <li key={r.id} className="flex items-center gap-2">
              {i > 0 && <span aria-hidden className="h-px w-6 bg-zinc-300" />}
              <button
                type="button"
                aria-pressed={active}
                // The one explicit pick (#37): what-ifs then run on this revision instead of the head.
                onClick={() => setViewRev(r.id, { source: 'user' })}
                className={cn(
                  'inline-flex items-center gap-1 rounded border px-2 py-1 font-mono',
                  active ? 'border-blue-600/50 bg-blue-50 text-foreground' : 'border-zinc-300 text-zinc-700 hover:border-zinc-400',
                )}
              >
                {r.id}{' '}
                <RevisionVerdict findings={findingsFor(bundle, r.id)} />
              </button>
              {approval && (
                <span className="inline-flex items-center gap-1 text-emerald-700">
                  <Stamp aria-hidden className="size-3.5" />
                  {`signed by ${approval.approver_name} · ${approval.role}`}
                </span>
              )}
            </li>
          )
        })}
      </ol>
      <label className="ml-auto inline-flex items-center gap-2 text-muted-foreground">
        <GitCompareArrows aria-hidden className="size-3.5" />
        Compare with parent
        <Switch checked={compare} disabled={!parent} onCheckedChange={setCompare} aria-label="Compare with parent" />
      </label>
      {rev && (
        <Link to={`/app/p/${bundle.project.id}/review/${rev.id}${runId ? `?run=${runId}` : ''}`} className="rounded border border-zinc-300 px-2 py-1 text-foreground hover:border-zinc-400">
          Open review
        </Link>
      )}
    </footer>
  )
}
