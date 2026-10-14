import { Download, FileText } from 'lucide-react'
import { EmptyState, IllustrativeLabel } from '@/components/Labels'
import { Button } from '@/components/ui/button'
import { exportsOf } from '@/lib/select'
import type { LedgerEntry } from '@/lib/types'
import { useServices } from '@/services/services'
import { useUi } from '@/store/ui'
import { PlanGate } from '../gates/PlanGate'
import { useWorkspace } from '../WorkspaceContext'

const LEDGER_TITLES: Record<LedgerEntry['kind'], string> = {
  did: 'Did',
  assumed: 'Assumed',
  not_checked: 'Not checked in v0.1',
}

export function LedgerList({ ledger }: { ledger: LedgerEntry[] }) {
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
      {(Object.keys(LEDGER_TITLES) as LedgerEntry['kind'][]).map((k) => (
        <section key={k} aria-label={LEDGER_TITLES[k]} className="flex flex-col gap-1">
          <h4 className="text-xs font-medium uppercase tracking-wide text-zinc-400">{LEDGER_TITLES[k]}</h4>
          <ul className="flex flex-col gap-1 text-xs text-zinc-300">
            {ledger
              .filter((e) => e.kind === k)
              .map((e, i) => (
                <li key={i} className="rounded border bg-card px-2 py-1">
                  {e.text}
                </li>
              ))}
          </ul>
        </section>
      ))}
    </div>
  )
}

/** Exports are public URLs for seed projects or storage paths served via GET /api/files/{path}. */
export function useOpenExport() {
  const { api } = useServices()
  return async (ref: string) => {
    if (ref.startsWith('/') || ref.startsWith('http')) {
      window.open(ref, '_blank', 'noopener')
      return
    }
    const blob = await api.fileBlob(ref)
    window.open(URL.createObjectURL(blob), '_blank', 'noopener')
  }
}

export function DocsTab() {
  const { bundle, rev, run, source } = useWorkspace()
  const openCitation = useUi((s) => s.openCitation)
  const openExport = useOpenExport()
  const docs = [...new Set((bundle.brief?.requirements ?? []).map((r) => r.citation.doc_id))]
  const exports = exportsOf(bundle)
  if (!docs.length && !exports.length && !rev) return <EmptyState title="No documents yet">The tender, drawings and exports appear as the run progresses.</EmptyState>
  // The interactive plan gate already appears in GateBanner above the canvas; here it is always
  // read-only, so the engineer can still see how the open question was resolved after the gate passes.
  const atLivePlanGate = source === 'live' && run?.status === 'at_gate' && run.gate === 'plan'
  return (
    <div className="flex h-full flex-col gap-5 overflow-auto p-3 text-sm">
      {run && !atLivePlanGate && <PlanGate run={run} interactive={false} />}
      <section aria-label="Inputs" className="flex flex-col gap-2">
        <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-400">Inputs</h3>
        {docs.map((d) => (
          <Button key={d} variant="outline" size="sm" className="self-start" onClick={() => openCitation({ doc_id: d, page: 1, quote: '', bbox: null, clause: null })}>
            <FileText aria-hidden /> {d}.pdf
          </Button>
        ))}
      </section>
      <section aria-label="Exports" className="flex flex-col gap-2">
        <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-400">Exports</h3>
        {exports.length ? (
          exports.map((x) => (
            <Button key={x.ref} variant="outline" size="sm" className="self-start" onClick={() => void openExport(x.ref).catch(() => undefined)}>
              <Download aria-hidden /> {x.title}
            </Button>
          ))
        ) : (
          <p className="text-xs text-zinc-500">The Docs agent publishes the calc report and BOQ before the review gate.</p>
        )}
      </section>
      {rev && (
        <section aria-label="Assumptions ledger" className="flex flex-col gap-2">
          <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-400">Assumptions ledger · {rev.id}</h3>
          <LedgerList ledger={rev.ledger ?? []} />
        </section>
      )}
      <IllustrativeLabel />
    </div>
  )
}
