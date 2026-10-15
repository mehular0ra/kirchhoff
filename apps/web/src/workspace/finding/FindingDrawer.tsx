import { Crosshair, MessageSquare } from 'lucide-react'
import { useEffect, useState } from 'react'
import { IllustrativeLabel, Num } from '@/components/Labels'
import { StatusBadge } from '@/components/StatusBadge'
import { ClauseChip, TenderChip } from '@/components/TenderChip'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { fillPlaceholders, fmtInput, fmtKeyValue } from '@/lib/format'
import { canvasesFor } from '@/lib/model'
import { ruleName } from '@/lib/status'
import type { Finding } from '@/lib/types'
import { useServices } from '@/services/services'
import { useUi } from '@/store/ui'
import { useWorkspace } from '../WorkspaceContext'
import { ValueLimitBar } from './ValueLimitBar'

export interface FixView {
  label: string
  reason: string
  deltas: [string, unknown][]
}

/**
 * Reads the engine's fix dict: {candidate|label, reason, cost_delta?, deltas: {dv_pct, ...}}. The
 * shipped bundles carry `cost_delta` beside `deltas` (not inside it); it leads the card because the
 * cost is what explains the choice ("voltage-drop margin per dollar", final review I3).
 */
export function readFix(fix: Finding['fix']): FixView | null {
  if (!fix) return null
  const inner = fix.deltas && typeof fix.deltas === 'object' ? Object.entries(fix.deltas as Record<string, unknown>) : []
  const cost = typeof fix.cost_delta === 'number' && !inner.some(([k]) => k === 'cost_delta') ? [['cost_delta', fix.cost_delta] as [string, unknown]] : []
  const deltas = [...cost, ...inner]
  return {
    label: String(fix.label ?? fix.candidate ?? 'Fix'),
    reason: typeof fix.reason === 'string' ? fix.reason : '',
    deltas,
  }
}

function FixCard({ title, fix, tone }: { title: string; fix: FixView; tone: string }) {
  return (
    <div className="flex flex-col gap-1 rounded border p-2 text-xs">
      <span className={`text-[11px] font-medium uppercase tracking-wide ${tone}`}>{title}</span>
      <span className="text-zinc-100">{fix.label}</span>
      {fix.reason && <span className="text-zinc-400">{fix.reason}</span>}
      <ul className="mt-1 flex flex-col gap-0.5 font-mono text-zinc-200">
        {fix.deltas.map(([k, v]) => (
          <li key={k}>{fmtKeyValue(k, v)}</li>
        ))}
      </ul>
    </div>
  )
}

export function FindingDrawer({ onCitation }: { onCitation?: () => void }) {
  const view = useWorkspace()
  const { api } = useServices()
  const findingId = useUi((s) => s.findingId)
  const close = useUi((s) => s.closeFinding)
  const focus = useUi((s) => s.focus)
  const [explain, setExplain] = useState<{ text: string } | { error: string } | null>(null)
  const pool = [...(view.whatIf?.findings ?? []), ...view.findings]
  const f = pool.find((x) => x.id === findingId) ?? null

  useEffect(() => setExplain(null), [findingId])

  const fix = readFix(f?.fix ?? null)
  const rejected = readFix(f?.rejected_fix ?? null)
  return (
    <Sheet open={!!f} onOpenChange={(o) => !o && close()}>
      <SheetContent side="right" className="w-[28rem] overflow-y-auto sm:max-w-[28rem]">
        {f && (
          <>
            <SheetHeader>
              <div className="flex items-center gap-2">
                <StatusBadge status={f.status} />
                <span className="font-mono text-xs text-zinc-400">{f.rule_id}</span>
                <span className="text-xs text-zinc-400">{ruleName(f.rule_id)}</span>
              </div>
              <SheetTitle>{f.title}</SheetTitle>
              <SheetDescription>
                Element <span className="font-mono text-zinc-200">{f.element_id}</span>
                {view.rev && (
                  <>
                    {' '}
                    · revision <span className="font-mono">{view.rev.id}</span>
                  </>
                )}
              </SheetDescription>
            </SheetHeader>
            <div className="flex flex-col gap-4 px-4 pb-6 text-sm">
              <Button
                variant="outline"
                size="sm"
                className="self-start"
                onClick={() => {
                  focus(f.element_id, canvasesFor(view.model, f.element_id)) // switches away from Matrix (I5)
                  close()
                }}
              >
                <Crosshair aria-hidden /> Show on canvas
              </Button>

              {(f.clause_refs?.length || f.tender_refs?.length) && (
                <section aria-label="Sources" className="flex flex-wrap gap-1.5">
                  {f.clause_refs?.map((c) => <ClauseChip key={`${c.standard}${c.clause}`} standard={c.standard} clause={c.clause} />)}
                  {f.tender_refs?.map((c) => <TenderChip key={`${c.page}${c.clause}`} citation={c} onOpen={onCitation} />)}
                </section>
              )}

              {typeof f.value === 'number' && typeof f.limit === 'number' && (
                <ValueLimitBar value={f.value} limit={f.limit} unit={f.unit} status={f.status} />
              )}

              {f.formula && (
                <section aria-label="Formula" className="flex flex-col gap-1">
                  <pre className="overflow-x-auto rounded bg-zinc-900 p-2 font-mono text-xs text-zinc-100">{f.formula}</pre>
                  {f.inputs && Object.keys(f.inputs).length > 0 && (
                    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
                      {Object.entries(f.inputs).map(([k, v]) => {
                        const input = fmtInput(k, v)
                        return (
                          <div key={k} className="contents">
                            <dt className="text-zinc-400" title={k}>
                              {input.label}
                            </dt>
                            <dd className="font-mono text-zinc-100">
                              <Num>{input.value}</Num>
                            </dd>
                          </div>
                        )
                      })}
                    </dl>
                  )}
                </section>
              )}

              <section aria-label="Explanation" className="flex flex-col gap-2">
                <p className="text-zinc-200">{fillPlaceholders(f.explanation || f.title, f)}</p>
                {view.revRef && (
                  <Button
                    variant="ghost"
                    size="xs"
                    className="self-start"
                    onClick={() =>
                      api
                        .explain(view.revRef!, f.id)
                        .then((r) => setExplain({ text: fillPlaceholders(r.text, f) }))
                        .catch(() => setExplain({ error: 'Co-pilot is unavailable; the engine explanation above is complete.' }))
                    }
                  >
                    <MessageSquare aria-hidden /> Ask the co-pilot why
                  </Button>
                )}
                {explain && 'text' in explain && <p className="rounded border border-fuchsia-400/30 bg-fuchsia-500/5 p-2 text-zinc-200">{explain.text}</p>}
                {explain && 'error' in explain && <p className="text-xs text-zinc-400">{explain.error}</p>}
              </section>

              {(fix || rejected) && (
                <section aria-label="Fix" className="grid grid-cols-2 gap-2">
                  {fix && <FixCard title="Chosen fix" fix={fix} tone="text-emerald-300" />}
                  {rejected && <FixCard title="Rejected alternative" fix={rejected} tone="text-zinc-400" />}
                </section>
              )}
              <IllustrativeLabel />
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}
