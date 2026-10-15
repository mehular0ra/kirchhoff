import { CircleX, Download, FileText } from 'lucide-react'
import { useEffect, useState } from 'react'
import { EmptyState, IllustrativeLabel } from '@/components/Labels'
import { Button } from '@/components/ui/button'
import { loadIntegrationsSnapshot } from '@/data/staticData'
import { buildLanes, exportsOf } from '@/lib/select'
import type { DocumentRecord, LedgerEntry } from '@/lib/types'
import { useServices } from '@/services/services'
import { useUi, type CitationKind } from '@/store/ui'
import { docLabel } from '../finding/docLabel'
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
          <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{LEDGER_TITLES[k]}</h4>
          <ul className="flex flex-col gap-1 text-xs text-zinc-700">
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

/** The project's files in the static integrations snapshot (recorded designs carry no brief or export events, M9). */
function useSnapshotDocuments(projectId: string, enabled: boolean): DocumentRecord[] {
  const { getJson } = useServices()
  const [docs, setDocs] = useState<DocumentRecord[]>([])
  useEffect(() => {
    if (!enabled) return
    let alive = true
    loadIntegrationsSnapshot(getJson)
      .then((s) => alive && setDocs(s.documents.filter((d) => d.project_id === projectId)))
      .catch(() => undefined) // no snapshot: the tab simply shows less
    return () => {
      alive = false
    }
  }, [projectId, enabled, getJson])
  return docs
}

const PDF_STEM = /^\/demo\/docs\/([^/]+)\.pdf$/

export function DocsTab() {
  const { bundle, rev, run, source } = useWorkspace()
  const openCitation = useUi((s) => s.openCitation)
  const openExport = useOpenExport()
  const briefDocs = [...new Set((bundle.brief?.requirements ?? []).map((r) => r.citation.doc_id))]
  const recorded = exportsOf(bundle)
  const snapshot = useSnapshotDocuments(bundle.project.id, source !== 'live' && (!briefDocs.length || !recorded.length))
  // Inputs open in the citation viewer (served from /demo/docs); outputs are plain links.
  const docs: { id: string; kind: CitationKind | null }[] = briefDocs.length
    ? briefDocs.map((id) => ({ id, kind: null }))
    : snapshot.flatMap((d) => {
        const stem = PDF_STEM.exec(d.url)?.[1]
        return stem && (d.kind === 'tender' || d.kind === 'drawing') ? [{ id: stem, kind: d.kind }] : []
      })
  const exports = recorded.length
    ? recorded
    : snapshot.filter((d) => d.kind !== 'tender' && d.kind !== 'drawing').map((d) => ({ title: d.name, ref: d.url }))
  // The Docs agent's export step may have failed on a live run; the copy then says so instead of
  // claiming it still publishes "before the review gate" (the data decides, not a fixed sentence).
  const docsFailed = source === 'live' && buildLanes(bundle).find((l) => l.agent === 'docs')?.status === 'failed'
  if (!docs.length && !exports.length && !rev) return <EmptyState title="No documents yet">The tender, drawings and exports appear as the run progresses.</EmptyState>
  // The interactive plan gate already appears in GateBanner above the canvas; here it is always
  // read-only, so the engineer can still see how the open question was resolved after the gate passes.
  const atLivePlanGate = source === 'live' && run?.status === 'at_gate' && run.gate === 'plan'
  return (
    <div className="flex h-full flex-col gap-5 overflow-auto p-3 text-sm">
      {run && !atLivePlanGate && <PlanGate run={run} interactive={false} />}
      <section aria-label="Inputs" className="flex flex-col gap-2">
        <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Inputs</h3>
        {!docs.length && <p className="text-xs text-muted-foreground">The tender and drawing appear here once Intake has read them.</p>}
        {docs.map((d) => (
          <Button
            key={d.id}
            variant="outline"
            size="sm"
            className="self-start"
            onClick={() => openCitation({ doc_id: d.id, page: 1, quote: '', bbox: null, clause: null }, d.kind)}
          >
            <FileText aria-hidden /> {docLabel(d.id, d.kind)} · {d.id}.pdf
          </Button>
        ))}
      </section>
      <section aria-label="Exports" className="flex flex-col gap-2">
        <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Exports</h3>
        {exports.length ? (
          exports.map((x) =>
            x.ref.startsWith('/') || x.ref.startsWith('http') ? (
              <Button key={x.ref} asChild variant="outline" size="sm" className="self-start">
                <a href={x.ref} target="_blank" rel="noreferrer">
                  <Download aria-hidden /> {x.title}
                </a>
              </Button>
            ) : (
              <Button key={x.ref} variant="outline" size="sm" className="self-start" onClick={() => void openExport(x.ref).catch(() => undefined)}>
                <Download aria-hidden /> {x.title}
              </Button>
            ),
          )
        ) : docsFailed ? (
          <p role="alert" className="flex items-center gap-1.5 text-xs text-rose-700">
            <CircleX aria-hidden className="size-3.5 shrink-0" /> The Docs agent couldn't publish the calc report and BOQ for this run.
          </p>
        ) : (
          <p className="text-xs text-muted-foreground">
            {source === 'live' ? 'The Docs agent publishes the calc report and BOQ before the review gate.' : 'No exports are recorded for this design.'}
          </p>
        )}
      </section>
      {rev && (
        <section aria-label="Assumptions ledger" className="flex flex-col gap-2">
          <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Assumptions ledger · {rev.id}</h3>
          <LedgerList ledger={rev.ledger ?? []} />
        </section>
      )}
      <IllustrativeLabel />
    </div>
  )
}
