// Integrations (spec §13.3): ERP/CRM sandbox via /api/enterprise/*, documents and notifications from
// the static snapshot; falls back to /demo/integrations.json with a "showing cached snapshot" note.
import { Bell, Boxes, CircleCheck, Cloud, CloudOff, Handshake, Info, LoaderCircle, Puzzle, type LucideIcon } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { EmptyState, Num, SandboxLabel } from '@/components/Labels'
import { LoadError } from '@/components/LoadError'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { loadIntegrationsSnapshot } from '@/data/staticData'
import { useWorld } from '@/data/useWorld'
import { fmtQty, fmtRelative, fmtTs, fmtUsd } from '@/lib/format'
import type { IntegrationsSnapshot } from '@/lib/types'
import { useServices } from '@/services/services'

export interface IntegrationsState {
  data: IntegrationsSnapshot | null
  live: boolean
  /** True while the live ERP/CRM calls are still in flight (the cached snapshot is already shown). */
  connecting: boolean
  syncedAt: number | null
  error: string | null
}

/**
 * Static first (spec §11, §13.3; final review I4): the cached snapshot renders as soon as it loads,
 * and the live ERP/CRM data replaces it only if /api/enterprise/* answers — a cold Cloud Run start
 * or a hanging sign-in never leaves the page (or the tour's step 6 anchor) on "Loading…".
 */
export function useIntegrations(): IntegrationsState {
  const { api, getJson } = useServices()
  const [state, setState] = useState<IntegrationsState>({ data: null, live: false, connecting: true, syncedAt: null, error: null })
  useEffect(() => {
    let alive = true
    let upgraded = false
    const snapshot = loadIntegrationsSnapshot(getJson)
    snapshot
      .then((snap) => alive && !upgraded && setState((s) => ({ ...s, data: snap, syncedAt: snap.synced_at ?? null })))
      .catch((e: Error) => alive && !upgraded && setState((s) => ({ ...s, error: e.message })))
    Promise.all([api.erpMaterials(), api.erpPrs(), api.crmOpportunities(), snapshot])
      .then(([materials, prs, opportunities, snap]) => {
        if (!alive) return
        upgraded = true
        setState({ data: { ...snap, erp: { materials, prs }, crm: { opportunities } }, live: true, connecting: false, syncedAt: Date.now() / 1000, error: null })
      })
      .catch(() => alive && setState((s) => ({ ...s, connecting: false })))
    return () => {
      alive = false
    }
  }, [api, getJson])
  return state
}

// The card's own status line is icon + text, never colour alone (M1): "ok" for connected (live or always-on
// stores), "offline" for a cached/unreachable fallback, "info" for a feature that isn't live yet.
const STATUS_TONE: Record<'ok' | 'offline' | 'info', { icon: LucideIcon; cls: string }> = {
  ok: { icon: CircleCheck, cls: 'text-emerald-400' },
  offline: { icon: CloudOff, cls: 'text-amber-300' },
  info: { icon: Info, cls: 'text-zinc-400' },
}

function Card({
  icon: Icon,
  title,
  kind,
  sandbox,
  status,
  statusTone,
  counts,
  children,
  tour,
}: {
  icon: LucideIcon
  title: string
  kind: string
  sandbox: boolean
  status: string
  statusTone: 'ok' | 'offline' | 'info'
  counts: string[]
  children?: ReactNode
  tour?: string
}) {
  const StatusIcon = STATUS_TONE[statusTone].icon
  return (
    <article aria-label={title} data-tour={tour} className="flex flex-col gap-2 rounded-lg border bg-card p-4">
      {/* The badge wraps under a long title instead of being squashed (D18). */}
      <header className="flex flex-wrap items-center gap-2">
        <Icon aria-hidden className="size-4 text-zinc-400" />
        <h2 className="font-medium text-zinc-100">{title}</h2>
        {sandbox && <SandboxLabel className="ml-auto shrink-0 whitespace-nowrap" />}
      </header>
      <p className="text-xs text-zinc-400">{kind}</p>
      <p className={`flex items-center gap-1.5 text-xs ${STATUS_TONE[statusTone].cls}`}>
        <StatusIcon aria-hidden className="size-3.5 shrink-0" /> {status}
      </p>
      <ul className="flex flex-wrap gap-1.5 text-xs">
        {counts.map((c) => (
          <li key={c} className="rounded bg-zinc-800 px-1.5 py-0.5 font-mono text-zinc-200">
            {c}
          </li>
        ))}
      </ul>
      <div className="mt-auto">{children}</div>
    </article>
  )
}

function DataSheet({ title, label, children }: { title: string; label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button size="xs" variant="outline" onClick={() => setOpen(true)} aria-label={`View data: ${title}`}>
        View data
      </Button>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="right" className="w-[42rem] overflow-y-auto sm:max-w-[42rem]">
          <SheetHeader>
            <SheetTitle>{title}</SheetTitle>
            <SheetDescription>{label}</SheetDescription>
          </SheetHeader>
          <div className="px-4 pb-6">{children}</div>
        </SheetContent>
      </Sheet>
    </>
  )
}

const th = 'border-b px-2 py-1 text-left font-medium text-zinc-400'
const td = 'border-b border-zinc-800/70 px-2 py-1'

/** "6 × TX-3150, 30 × UPS-500" — the PR's own lines, as the review page shows them (D5). */
const prLines = (lines: { qty: number; material_id: string }[]) => lines.map((l) => `${l.qty} × ${l.material_id}`).join(', ')

export function IntegrationsPage() {
  const { data, live, connecting, syncedAt, error } = useIntegrations()
  const { world } = useWorld()
  const projectName = (id: string) => world?.projects.find((p) => p.id === id)?.name ?? id
  if (error && !data) return <LoadError error={error} what="the integrations" notFoundTitle="Integrations snapshot not found" />
  if (!data) return <EmptyState title="Loading integrations…" />
  const status = live
    ? `Connected · last sync ${syncedAt ? fmtRelative(syncedAt) : 'now'}`
    : `Cached snapshot · ${syncedAt ? fmtTs(syncedAt) : ''}`
  const handoffPrs = data.erp.prs.filter((p) => p.project_id === 'hall-a' || p.project_id === 'hall-b')
  const handoffOpps = data.crm.opportunities.filter((o) => /hall [ab]/i.test(o.name))
  return (
    <div className="mx-auto flex h-full max-w-6xl flex-col gap-5 overflow-auto p-6">
      <div className="flex flex-wrap items-baseline gap-3">
        <h1 className="text-lg font-semibold">Integrations</h1>
        {!live && (
          <span role="status" className="inline-flex items-center gap-1.5 rounded bg-amber-500/10 px-2 py-0.5 text-xs text-amber-200">
            {connecting ? (
              <>
                <LoaderCircle aria-hidden className="size-3.5 animate-spin motion-reduce:animate-none" /> Connecting to the live sandbox… showing the cached
                snapshot
              </>
            ) : (
              <>
                <CloudOff aria-hidden className="size-3.5" /> API unreachable — showing cached snapshot
              </>
            )}
          </span>
        )}
      </div>
      <section aria-label="Latest handoff" data-tour="integrations-prs" className="flex flex-col gap-2 rounded-lg border bg-card p-4">
        {/* One sandbox label for the section, not one per row (D5). */}
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-xs font-medium uppercase tracking-wide text-zinc-400">Latest handoff from signed designs</h2>
          <SandboxLabel className="ml-auto" />
        </div>
        <ul className="flex flex-col gap-1.5 text-sm">
          {handoffPrs.map((p) => (
            <li key={p.id} className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
              <span className="font-mono text-zinc-100">{p.id}</span>
              <span className="text-zinc-300">
                {projectName(p.project_id)} · <span className="font-mono">{p.revision}</span>
              </span>
              <span className="font-mono text-xs text-zinc-200">{prLines(p.lines)}</span>
              <span className="text-xs text-zinc-400">{p.status}</span>
            </li>
          ))}
          {handoffOpps.map((o) => (
            <li key={o.id} className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
              <span className="text-zinc-100">{o.name}</span>
              <span className="text-zinc-400">CRM stage: {o.stage}</span>
            </li>
          ))}
        </ul>
      </section>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        <Card
          icon={Boxes}
          title="ERP (SAP-style)"
          kind="Materials, stock, lead times and purchase requisitions"
          sandbox
          status={status}
          statusTone={live ? 'ok' : 'offline'}
          counts={[`${data.erp.materials.length} materials`, `${data.erp.prs.length} purchase requisitions`]}
        >
          <DataSheet title="ERP (SAP-style)" label="sandbox (simulated) · kirchhoff-enterprise">
            <table className="w-full text-xs" aria-label="Materials">
              <thead>
                <tr>
                  {['Material', 'Description', 'Stock', 'Lead time', 'Unit price', 'Vendor'].map((h) => (
                    <th key={h} className={th}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.erp.materials.map((m) => (
                  <tr key={m.id}>
                    <td className={`${td} font-mono`}>{m.id}</td>
                    <td className={td}>{m.description}</td>
                    <td className={td}>
                      <Num>{m.stock}</Num>
                    </td>
                    <td className={td}>
                      <Num>{fmtQty(m.lead_time_weeks, 'weeks')}</Num>
                    </td>
                    <td className={td}>
                      <Num>{fmtUsd(m.unit_price)}</Num>
                    </td>
                    <td className={td}>{m.vendor}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <table className="mt-4 w-full text-xs" aria-label="Purchase requisitions">
              <thead>
                <tr>
                  {['PR', 'Project', 'Revision', 'Lines', 'Status', 'Created'].map((h) => (
                    <th key={h} className={th}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.erp.prs.map((p) => (
                  <tr key={p.id}>
                    <td className={`${td} font-mono`}>{p.id}</td>
                    <td className={td}>{projectName(p.project_id)}</td>
                    <td className={`${td} font-mono`}>{p.revision}</td>
                    <td className={td}>{p.lines.map((l) => `${l.qty} × ${l.material_id}`).join(', ')}</td>
                    <td className={td}>{p.status}</td>
                    <td className={td}>{fmtTs(p.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </DataSheet>
        </Card>
        <Card
          icon={Handshake}
          title="CRM (Salesforce-style)"
          kind="Accounts and opportunities"
          sandbox
          status={status}
          statusTone={live ? 'ok' : 'offline'}
          counts={[`${new Set(data.crm.opportunities.map((o) => o.account)).size} accounts`, `${data.crm.opportunities.length} opportunities`]}
        >
          <DataSheet title="CRM (Salesforce-style)" label="sandbox (simulated) · kirchhoff-enterprise">
            <table className="w-full text-xs" aria-label="Opportunities">
              <thead>
                <tr>
                  {['Account', 'Opportunity', 'Stage', 'Value', 'Next step'].map((h) => (
                    <th key={h} className={th}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.crm.opportunities.map((o) => (
                  <tr key={o.id}>
                    <td className={td}>{o.account}</td>
                    <td className={td}>{o.name}</td>
                    <td className={td}>{o.stage}</td>
                    <td className={td}>
                      <Num>{fmtUsd(o.value)}</Num>
                    </td>
                    <td className={td}>{o.next_step}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </DataSheet>
        </Card>
        <Card
          icon={Cloud}
          title="Document store"
          kind="Google Cloud Storage: tenders, drawings, calc reports, BOQs"
          sandbox={false}
          status="Connected (Cloud Storage)"
          statusTone="ok"
          counts={[`${data.documents.length} documents`]}
        >
          <DataSheet title="Document store" label="Google Cloud Storage">
            <ul className="flex flex-col gap-1 text-sm">
              {data.documents.map((d) => (
                <li key={d.id} className="flex items-center gap-2">
                  <a href={d.url} target="_blank" rel="noreferrer" className="text-sky-300 hover:underline">
                    {d.name}
                  </a>
                  <span className="text-xs text-zinc-400">
                    {d.project_id} · {d.kind}
                  </span>
                </li>
              ))}
            </ul>
          </DataSheet>
        </Card>
        <Card icon={Bell} title="Notifications" kind="In-app inbox of approvals and findings" sandbox status={status} statusTone={live ? 'ok' : 'offline'} counts={[`${data.notifications.length} notifications`]}>
          <DataSheet title="Notifications" label="sandbox (simulated)">
            <ul className="flex flex-col gap-2 text-sm">
              {data.notifications.map((n) => (
                <li key={n.id}>
                  <p className="text-zinc-100">{n.title}</p>
                  <p className="text-xs text-zinc-400">{fmtTs(n.ts)}</p>
                </li>
              ))}
            </ul>
          </DataSheet>
        </Card>
        <Card icon={Puzzle} title="PLM" kind="Product lifecycle management" sandbox={false} status="Coming soon" statusTone="info" counts={[]} />
      </div>
    </div>
  )
}
