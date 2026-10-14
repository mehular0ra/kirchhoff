// One email of the bids inbox (spec §20): header, attachment chips by class, body, the Inbox agent's triage (CRM
// link, extracted fields with their verification marks), the deterministic fit card with the day-zero supply line,
// and Pursue. The live Triage button (Hall B only) is added in a [cut] step.
import { cn } from 'cn'
import { ArrowLeft, ArrowRight, CircleCheck, Handshake, LoaderCircle, Paperclip, ScanLine, Truck } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { SandboxLabel } from '@/components/Labels'
import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { useWorldProject } from '@/data/useWorld'
import { fmtTs } from '@/lib/format'
import type { CrmLink, InboxEmail, PursueResult, TriageResult } from '@/lib/types'
import { describeApiError } from '@/services/apiClient'
import { useServices } from '@/services/services'
import { KIND_LABEL, KIND_ORDER, VERIFICATION_META, verdictMeta } from './inboxMeta'
import { applyPursue } from './useInbox'

const PACKS = ['datahall', 'grid', 'solar']

export function VerdictBadge({ triage, className }: { triage: TriageResult; className?: string }) {
  const m = verdictMeta(triage)
  const Icon = m.icon
  return (
    <span className={cn('inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs font-medium', m.cls, className)}>
      <Icon aria-hidden className="size-3.5" />
      {m.label}
    </span>
  )
}

function AttachmentChips({ email, triage }: { email: InboxEmail; triage: TriageResult | null }) {
  if (!email.attachments.length) return <p className="text-xs text-zinc-500">No attachments.</p>
  const byId = new Map((triage?.attachments ?? []).map((a) => [a.attachment_id, a]))
  const rank = (id: string) => KIND_ORDER.indexOf(byId.get(id)?.kind ?? 'other')
  const sorted = [...email.attachments].sort((a, b) => rank(a.id) - rank(b.id))
  return (
    <ul aria-label="Attachments" className="flex flex-wrap gap-2">
      {sorted.map((a) => {
        const t = byId.get(a.id)
        return (
          <li key={a.id}>
            <a
              href={a.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded border border-zinc-700 bg-zinc-800/60 px-2 py-1 text-xs text-zinc-200 hover:border-zinc-500 focus-visible:outline-2 focus-visible:outline-sky-400"
            >
              <Paperclip aria-hidden className="size-3.5" />
              <span className="font-medium">{t ? KIND_LABEL[t.kind] : 'Unclassified'}</span>
              <span className="text-zinc-400">{a.name}</span>
              {t?.scanned && (
                <span className="inline-flex items-center gap-0.5 text-amber-300">
                  <ScanLine aria-hidden className="size-3" />
                  scan
                </span>
              )}
            </a>
          </li>
        )
      })}
    </ul>
  )
}

function crmText(crm: CrmLink): string {
  if (crm.opportunity_id) return `${crm.account} · ${crm.opportunity_name}${crm.stage ? ` (${crm.stage})` : ''}`
  if (crm.proposed) return `New opportunity proposed for ${crm.account}: ${crm.proposed_name}`
  return crm.account ? `${crm.account}, no matching opportunity` : 'No CRM record'
}

function CrmLine({ crm }: { crm: CrmLink }) {
  return (
    <p className="flex flex-wrap items-center gap-2 text-sm">
      <Handshake aria-hidden className="size-4 text-zinc-400" />
      <span className="text-zinc-400">CRM:</span>
      <Link to="/app/integrations" className="text-sky-300 underline-offset-2 hover:underline">
        {crmText(crm)}
      </Link>
      <SandboxLabel />
    </p>
  )
}

function FieldsTable({ triage }: { triage: TriageResult }) {
  return (
    <table aria-label="Extracted fields" className="w-full text-left text-sm">
      <thead className="text-xs text-zinc-400">
        <tr>
          <th className="py-1 pr-3 font-medium">Field</th>
          <th className="py-1 pr-3 font-medium">Value</th>
          <th className="py-1 pr-3 font-medium">Check</th>
          <th className="py-1 font-medium">Source</th>
        </tr>
      </thead>
      <tbody>
        {triage.fields.map((f) => {
          const m = VERIFICATION_META[f.verification]
          const Icon = m.icon
          return (
            <tr key={f.key} className="border-t border-zinc-800 align-top">
              <th scope="row" className="py-1.5 pr-3 font-normal text-zinc-400">
                {f.label}
              </th>
              <td className="py-1.5 pr-3 font-mono tabular-nums text-zinc-100">{f.display}</td>
              <td className="py-1.5 pr-3">
                <span className={cn('inline-flex items-center gap-1 text-xs', m.cls)}>
                  <Icon aria-hidden className="size-3.5" />
                  {m.label}
                </span>
              </td>
              <td className="py-1.5 text-xs text-zinc-400">
                {f.source_label}
                {f.quote && <q className="mt-0.5 block text-zinc-300">{f.quote}</q>}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

function FitCard({ triage }: { triage: TriageResult }) {
  return (
    <section aria-label="Fit verdict" className="flex flex-col gap-2 rounded-lg border bg-card p-4">
      <div className="flex flex-wrap items-center gap-2">
        <VerdictBadge triage={triage} />
        <p className="text-sm font-medium text-zinc-100">{triage.fit.headline}</p>
      </div>
      <ul className="flex flex-col gap-1.5 text-sm">
        {triage.fit.reasons.map((r) => (
          <li
            key={r.rule}
            className={cn('flex items-start gap-2', r.rule === 'supply' && 'rounded border border-sky-500/30 bg-sky-500/5 p-2')}
          >
            <StatusBadge status={r.status} compact className="shrink-0" />
            {r.rule === 'supply' && <Truck aria-hidden className="mt-0.5 size-4 shrink-0 text-sky-300" />}
            <span className="text-zinc-300">
              {r.rule === 'supply' && <span className="font-medium text-zinc-100">Day-zero supply: </span>}
              {r.text}
            </span>
          </li>
        ))}
      </ul>
      <p className="text-[11px] text-zinc-500">Deterministic rules from the firm's appetite, the engine and the ERP; no AI in the verdict.</p>
    </section>
  )
}

function PursueCard({ result, name }: { result: PursueResult; name: string }) {
  const was = result.previous_stage && result.previous_stage !== result.stage ? ` (was ${result.previous_stage})` : ''
  return (
    <section aria-label="Pursued" className="flex flex-col gap-1.5 rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3 text-sm">
      <p className="flex items-center gap-1.5 font-medium text-emerald-300">
        <CircleCheck aria-hidden className="size-4" />
        Pursued
      </p>
      <p className="flex flex-wrap items-center gap-2 text-zinc-300">
        CRM: {result.opportunity_name} → {result.stage}
        {was}
        {result.opportunity_created ? ' · new opportunity' : ''}
        <SandboxLabel />
      </p>
      <p className="text-zinc-300">
        {result.project_created ? `Project created in your workspace: ${result.project_name} (draft)` : `Project: ${name}`}
      </p>
      {result.open && (
        <Button asChild size="sm" className="self-start">
          <Link to={result.open}>
            Open {name} and run intake <ArrowRight aria-hidden />
          </Link>
        </Button>
      )}
    </section>
  )
}

function PursueAction({ email, triage }: { email: InboxEmail; triage: TriageResult }) {
  const { api } = useServices()
  const world = useWorldProject(email.project_id ?? undefined)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const name = world?.name ?? email.project_id ?? ''
  if (email.pursue) return <PursueCard result={email.pursue} name={email.pursue.project_name ?? name} />
  const asset = triage.fields.find((f) => f.key === 'asset_type' && f.verification === 'verified')
  const pursuable = (triage.fit.verdict === 'pursue' || triage.fit.verdict === 'clarify') && PACKS.includes(String(asset?.value))
  if (!pursuable)
    return (
      <p className="text-xs text-zinc-500">
        {triage.fit.verdict === null ? 'Not a bid: nothing to pursue.' : triage.fit.verdict === 'decline' ? 'Declined by the fit rules.' : 'Pursue needs a verified asset type in one of our packs.'}
      </p>
    )
  const pursue = async () => {
    setBusy(true)
    setNote(null)
    try {
      applyPursue(email.id, await api.pursue(email.id))
    } catch (e) {
      setNote(describeApiError(e))
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="flex flex-col gap-2">
      <Button onClick={pursue} disabled={busy} className="self-start">
        {busy ? <LoaderCircle aria-hidden className="animate-spin motion-reduce:animate-none" /> : <Handshake aria-hidden />}
        Pursue
      </Button>
      {note && (
        <p role="status" className="text-xs text-amber-200">
          {note}
          {email.project_id ? ' You can still open the project; the CRM was not updated.' : ''}
        </p>
      )}
      {note && email.project_id && (
        <Link to={`/app/p/${email.project_id}`} className="inline-flex items-center gap-1 text-sm text-sky-300 hover:underline">
          Open {name} <ArrowRight aria-hidden className="size-3.5" />
        </Link>
      )}
    </div>
  )
}

export function EmailDetail({ email }: { email: InboxEmail }) {
  const triage = email.triage
  return (
    <article aria-labelledby={`subject-${email.id}`} className="flex flex-col gap-5 p-6">
      <Link to="/app/inbox" className="inline-flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-200 lg:hidden">
        <ArrowLeft aria-hidden className="size-3.5" /> All emails
      </Link>
      <header className="flex flex-col gap-1">
        <h2 id={`subject-${email.id}`} className="text-base font-semibold text-zinc-100">
          {email.subject}
        </h2>
        <p className="text-sm text-zinc-300">
          {email.from_name} &lt;{email.from_addr}&gt; · {email.from_org}
        </p>
        <p className="text-xs text-zinc-500">
          To {email.to} · {fmtTs(email.received_at)}
        </p>
      </header>
      <AttachmentChips email={email} triage={triage} />
      <div className="whitespace-pre-wrap rounded-lg border bg-zinc-900/50 p-4 text-sm text-zinc-300">{email.body}</div>
      {triage ? (
        <>
          <section aria-label="Triage" className="flex flex-col gap-3">
            <p className="text-xs text-zinc-400">
              Inbox agent · {triage.source === 'live' ? 'live triage' : 'recorded triage'} · {triage.quotes_verified}/
              {triage.quotes_total} quotes verified
            </p>
            <p className="text-sm text-zinc-200">{triage.summary}</p>
            <CrmLine crm={triage.crm} />
            {triage.fields.length > 0 && <FieldsTable triage={triage} />}
          </section>
          <FitCard triage={triage} />
        </>
      ) : (
        <p className="text-sm text-zinc-400">Not triaged yet. The recorded triage arrives with the golden capture.</p>
      )}
      <div className="flex flex-wrap items-start gap-6">
        {triage && <PursueAction email={email} triage={triage} />}
      </div>
    </article>
  )
}
