// Review and sign-off (spec §12 screen 7): diff vs parent, findings summary, assumptions ledger,
// Approve with stamp; after approval the PRs (ERP) and CRM stage handoff (spec §3 1:58–2:18).
import { ArrowLeft, CircleX, Download } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { EmptyState, IllustrativeLabel, Num, SandboxLabel } from '@/components/Labels'
import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { useProjectData } from '@/data/useProjectData'
import { useWorldProject } from '@/data/useWorld'
import { diffModels, type ElementChange } from '@/lib/diff'
import { fmtNum, fmtTs, shortHash } from '@/lib/format'
import { countByStatus, currentRun, exportsOf, findingsFor, latestRevision, parentRevision, revisionById, type DataSource } from '@/lib/select'
import { STATUS_META, statusRank } from '@/lib/status'
import type { Bundle, FindingStatus, PurchaseRequisition } from '@/lib/types'
import { completeItem } from '@/onboarding/checklist/checklistStore'
import { describeApiError } from '@/services/apiClient'
import { useServices } from '@/services/services'
import { LedgerList, useOpenExport } from '../docs/DocsTab'
import { ApprovalStamp } from './ApprovalStamp'

function show(v: unknown): string {
  if (typeof v === 'number') return fmtNum(v)
  if (v === null || v === undefined) return '—'
  if (Array.isArray(v)) return v.length && typeof v[0] === 'object' ? 'route' : v.join(', ')
  return String(v)
}

// PR status is always icon + text (global constraint), never colour alone: reuse STATUS_META's icons.
const PR_STATUS_ICON: Record<PurchaseRequisition['status'], FindingStatus> = { draft: 'n/a', submitted: 'pass', blocked: 'fail' }

function PrStatus({ status }: { status: PurchaseRequisition['status'] }) {
  const meta = STATUS_META[PR_STATUS_ICON[status]]
  const Icon = meta.icon
  const text = status === 'blocked' ? 'blocked: SLD, BOQ and PR lines disagree (R12)' : status
  return (
    <span className={`inline-flex items-center gap-1 ${status === 'blocked' ? 'text-rose-300' : 'text-zinc-300'}`}>
      <Icon aria-hidden className="size-3.5" /> {text}
    </span>
  )
}

function ChangeLine({ c }: { c: ElementChange }) {
  return (
    <li className="flex flex-col gap-0.5 rounded border bg-card px-2 py-1 text-xs">
      <span>
        <span className="font-mono text-zinc-100">{c.id}</span> <span className="text-zinc-400">{c.kind}</span>
      </span>
      {c.fields.map((f) => (
        <span key={f.field} className="font-mono text-zinc-300">
          {f.field}: {f.field === 'route' ? 'rerouted' : `${show(f.before)} → ${show(f.after)}`}
        </span>
      ))}
    </li>
  )
}

export function ReviewView({ bundle, source, revId, runQuery }: { bundle: Bundle; source: DataSource; revId: string; runQuery: string }) {
  const { api } = useServices()
  const openExport = useOpenExport()
  const [comment, setComment] = useState('')
  const [sent, setSent] = useState<{ ok: boolean; text: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const rev = revisionById(bundle, revId)
  if (!rev) return <EmptyState title={`Revision ${revId} not found`}>It may not have been created yet in this run.</EmptyState>
  const parent = parentRevision(bundle, rev)
  const findings = findingsFor(bundle, rev.id)
  const counts = countByStatus(findings)
  const open = findings.filter((f) => f.status !== 'pass').sort((a, b) => statusRank(b.status) - statusRank(a.status))
  const diff = parent ? diffModels(parent.model, rev.model) : null
  const approval = bundle.approvals.filter((a) => a.revision === rev.id).sort((a, b) => b.ts - a.ts)[0] ?? null
  const run = currentRun(bundle)
  const atReview = source === 'live' && run?.status === 'at_gate' && run.gate === 'review'
  // Ruling R22: the review gate signs the latest revision; Approve is disabled unless check_summary.fail is 0.
  const latest = latestRevision(bundle)
  const isLatest = latest?.id === rev.id
  const failing = rev.check_summary?.fail ?? counts.fail
  const prs = bundle.prs.filter((p) => p.revision === rev.id)
  const workspace = `/app/p/${bundle.project.id}${runQuery}`

  const decide = async (decision: 'approved' | 'rejected') => {
    if (!run) return
    setBusy(true)
    try {
      await api.reviewGate(run.id, decision, comment)
      if (decision === 'approved') completeItem('approve')
      setSent({ ok: true, text: decision === 'approved' ? 'Approval sent. Purchase requisitions and the CRM update follow.' : 'Rejection sent.' })
    } catch (e) {
      setSent({ ok: false, text: describeApiError(e) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex h-full max-w-5xl flex-col gap-6 overflow-auto p-6">
      <header className="flex flex-wrap items-center gap-3">
        <Button asChild variant="ghost" size="sm">
          <Link to={workspace}>
            <ArrowLeft aria-hidden /> Workspace
          </Link>
        </Button>
        <h1 className="text-lg font-semibold">
          Review · {bundle.project.name} · <span className="font-mono">{rev.id}</span>
        </h1>
        <span className="font-mono text-xs text-zinc-400" title={rev.hash}>
          sha256 {shortHash(rev.hash)}
        </span>
        <IllustrativeLabel className="ml-auto" />
      </header>

      <section aria-label="Findings summary" className="flex flex-col gap-2">
        <h2 className="text-xs font-medium uppercase tracking-wide text-zinc-400">Checker summary</h2>
        <p className="flex flex-wrap gap-3 text-sm">
          <span className="font-mono text-zinc-200">{findings.length} checks</span>
          {(['fail', 'warn', 'pass', 'n/a'] as const).map((s) => (
            <span key={s} className={`font-mono ${STATUS_META[s].text}`}>
              {counts[s]} {STATUS_META[s].label.toLowerCase()}
            </span>
          ))}
        </p>
        <ul className="flex flex-col gap-1">
          {open.map((f) => (
            <li key={f.id} className="flex items-center gap-2 text-sm">
              <StatusBadge status={f.status} />
              <Link className="font-mono text-zinc-200 hover:underline" to={`${workspace}${runQuery ? '&' : '?'}tab=matrix&rev=${rev.id}&finding=${encodeURIComponent(f.id)}`}>
                {f.rule_id} · {f.element_id}
              </Link>
              <span className="text-zinc-400">{f.title}</span>
            </li>
          ))}
        </ul>
      </section>

      <section aria-label="Changes from parent" className="flex flex-col gap-2">
        {parent ? (
          <>
            <h2 className="text-xs font-medium uppercase tracking-wide text-zinc-400">Changes from {parent.id}</h2>
            {diff && (diff.changes.length ? <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">{diff.changes.map((c) => <ChangeLine key={c.id} c={c} />)}</ul> : <p className="text-sm text-zinc-400">No model changes.</p>)}
          </>
        ) : (
          <EmptyState title="First revision — nothing to compare against" />
        )}
      </section>

      <section aria-label="Assumptions ledger" className="flex flex-col gap-2">
        <h2 className="text-xs font-medium uppercase tracking-wide text-zinc-400">Assumptions ledger</h2>
        <LedgerList ledger={rev.ledger ?? []} />
      </section>

      <section aria-label="Sign-off" className="flex flex-col gap-3">
        <h2 className="text-xs font-medium uppercase tracking-wide text-zinc-400">Sign-off</h2>
        {approval ? (
          <ApprovalStamp approval={approval} revision={rev} />
        ) : atReview ? (
          <div className="flex max-w-xl flex-col gap-2">
            <Textarea aria-label="Review comment" placeholder="Comment for the record (optional)" value={comment} onChange={(e) => setComment(e.target.value)} />
            {failing > 0 && (
              <p role="alert" className="text-sm text-rose-300">
                Approve is disabled: {failing} findings still fail after the fix loop. Reject, or open the findings to see why.
              </p>
            )}
            {!isLatest && failing === 0 && latest && (
              <p className="text-sm text-zinc-400">
                Sign-off applies to the latest revision, <span className="font-mono">{latest.id}</span>.
              </p>
            )}
            <div className="flex gap-2">
              <Button disabled={busy || failing > 0 || !isLatest || !!(sent && sent.ok)} onClick={() => void decide('approved')}>
                Approve and sign as You (Demo Reviewer)
              </Button>
              <Button variant="outline" disabled={busy || !!(sent && sent.ok)} onClick={() => void decide('rejected')}>
                Reject
              </Button>
            </div>
            {sent &&
              (sent.ok ? (
                <p className="text-sm text-zinc-300">{sent.text}</p>
              ) : (
                <p role="alert" className="flex items-center gap-1.5 text-sm text-rose-300">
                  <CircleX aria-hidden className="size-4 shrink-0" /> {sent.text}
                </p>
              ))}
          </div>
        ) : (
          <p className="text-sm text-zinc-400">
            Sign-off happens at the review gate of a live run. Start one on Hall B to sign as You (Demo Reviewer).
          </p>
        )}
      </section>

      {(prs.length > 0 || bundle.crm) && approval?.decision === 'approved' && (
        <section aria-label="Handoff" className="flex flex-col gap-2">
          <h2 className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-zinc-400">
            Handoff <SandboxLabel />
          </h2>
          <ul className="flex flex-col gap-1 text-sm">
            {prs.map((p) => (
              <li key={p.id} className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-zinc-100">{p.id}</span>
                <PrStatus status={p.status} />
                <span className="text-zinc-400">
                  {p.lines.map((l) => `${l.qty} × ${l.material_id}`).join(', ')} · {fmtTs(p.created_at)}
                </span>
              </li>
            ))}
            {bundle.crm && (
              <li className="text-zinc-300">
                CRM opportunity moved to <span className="text-zinc-50">{bundle.crm.stage}</span>
              </li>
            )}
          </ul>
        </section>
      )}

      {exportsOf(bundle).length > 0 && (
        <section aria-label="Exports" className="flex flex-wrap gap-2">
          {exportsOf(bundle).map((x) => (
            <Button key={x.ref} variant="outline" size="sm" onClick={() => void openExport(x.ref).catch(() => undefined)}>
              <Download aria-hidden /> {x.title}
            </Button>
          ))}
        </section>
      )}
      <p className="text-xs text-zinc-500">
        <Num>{findings.length}</Num> deterministic checks by the rule pack; the AI cannot mark its own homework.
      </p>
    </div>
  )
}

export function ReviewPage() {
  const { pid = '', rev = '' } = useParams()
  const [params] = useSearchParams()
  const runId = params.get('run')
  const project = useWorldProject(pid)
  const data = useProjectData(pid, { runId, project })
  if (!data.bundle) return <EmptyState title={data.status === 'error' ? 'This project is not available' : 'Loading review…'}>{data.error}</EmptyState>
  return <ReviewView bundle={data.bundle} source={data.source} revId={rev} runQuery={runId ? `?run=${runId}` : ''} />
}
