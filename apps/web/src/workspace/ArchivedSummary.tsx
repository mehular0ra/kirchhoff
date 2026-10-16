import { Archive, ChevronRight } from 'lucide-react'
import { Link } from 'react-router'
import { Num, SandboxLabel } from '@/components/Labels'
import { Button } from '@/components/ui/button'
import { fmtTs } from '@/lib/format'
import type { Bundle } from '@/lib/types'

/**
 * An archived project with no design revisions (Vindhya Steel's mill LV upgrade): a read-only summary with its
 * purchase requisitions instead of an empty, interactive data-hall workspace (UX-1 D12).
 */
export function ArchivedSummary({ bundle }: { bundle: Bundle }) {
  const p = bundle.project
  return (
    <div className="mx-auto flex h-full max-w-5xl flex-col gap-5 overflow-auto p-6">
      <nav aria-label="Breadcrumb" className="flex items-center gap-1 text-sm text-muted-foreground">
        <Link to="/app" className="hover:text-foreground">
          Kirchhoff
        </Link>
        <ChevronRight aria-hidden className="size-3.5" />
        <span className="text-zinc-700">Archived project</span>
      </nav>
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-semibold text-foreground">{p.name}</h1>
        <span className="inline-flex items-center gap-1.5 rounded bg-zinc-100 px-2 py-0.5 text-xs text-zinc-700">
          <Archive aria-hidden className="size-3.5" /> Archived · read-only
        </span>
      </header>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        <dt className="text-muted-foreground">Client</dt>
        <dd className="text-foreground">{p.client}</dd>
        <dt className="text-muted-foreground">Last updated</dt>
        <dd className="text-foreground">{fmtTs(p.updated_at)}</dd>
      </dl>
      <p className="text-sm text-muted-foreground">
        This archived project has no design revisions in the workspace; its purchase requisitions are kept for reference.
      </p>
      {bundle.prs.length > 0 && (
        <section aria-labelledby="archived-prs" className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <h2 id="archived-prs" className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Purchase requisitions
            </h2>
            <SandboxLabel className="ml-auto" />
          </div>
          <div className="overflow-x-auto rounded-lg border">
            <table aria-label="Purchase requisitions" className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-muted-foreground">
                  {['PR', 'Revision', 'Lines', 'Status', 'Created'].map((h) => (
                    <th key={h} className="border-b px-3 py-2 font-medium">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {bundle.prs.map((pr) => (
                  <tr key={pr.id} className="align-top">
                    <td className="border-b border-border px-3 py-2 font-mono text-foreground">{pr.id}</td>
                    <td className="border-b border-border px-3 py-2 font-mono text-zinc-700">{pr.revision}</td>
                    <td className="border-b border-border px-3 py-2">
                      <Num className="text-xs text-foreground">{pr.lines.map((l) => `${l.qty} × ${l.material_id}`).join(', ')}</Num>
                    </td>
                    <td className="border-b border-border px-3 py-2 text-zinc-700">{pr.status}</td>
                    <td className="whitespace-nowrap border-b border-border px-3 py-2 text-muted-foreground">{fmtTs(pr.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      <Button asChild variant="outline" size="sm" className="self-start">
        <Link to="/app">Back to projects</Link>
      </Button>
    </div>
  )
}
