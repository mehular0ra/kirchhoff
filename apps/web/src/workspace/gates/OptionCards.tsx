import { cn } from 'cn'
import { ArrowRight, Check, CircleX, Hand } from 'lucide-react'
import { useState } from 'react'
import { EmptyState, IllustrativeLabel, Num } from '@/components/Labels'
import { Button } from '@/components/ui/button'
import { fmtNum, fmtQty, fmtUsd } from '@/lib/format'
import type { TopologyOption } from '@/lib/types'
import { describeApiError } from '@/services/apiClient'
import { useServices } from '@/services/services'
import { useWorkspace } from '../WorkspaceContext'

const NAMES: Record<TopologyOption['id'], string> = {
  '2N': '2N',
  DR: 'Distributed redundant (4-to-make-3)',
  BLOCK: 'Block redundant (3 + 1)',
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2 text-xs">
      <dt className="text-muted-foreground">{label}</dt>
      <dd>
        <Num className="text-foreground">{value}</Num>
      </dd>
    </div>
  )
}

/** Option gate (spec §12 screen 5): costed topology cards; selectable at a live option gate. */
export function OptionCards() {
  const { run, source, bundle } = useWorkspace()
  const { api } = useServices()
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const options = run?.options ?? []
  if (!run || !options.length) {
    // A signed recorded sample without a recorded option gate (D10): say what it is, not "not yet".
    if (source === 'static' && bundle.approvals.length > 0)
      return (
        <EmptyState title="Topology options are not part of this sample">
          This sample includes the checked design, findings and sign-off. Run Hall B live to see Power weigh the topologies.
        </EmptyState>
      )
    return <EmptyState title="No options yet">Power enumerates topologies and Procurement checks lead times; options appear here.</EmptyState>
  }
  const atGate = source === 'live' && run.status === 'at_gate' && run.gate === 'option'

  const select = async (id: TopologyOption['id']) => {
    setBusy(id)
    setError(null)
    try {
      await api.optionGate(run.id, id)
    } catch (e) {
      setError(describeApiError(e))
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="flex h-full flex-col gap-3 overflow-auto p-3" data-tour="options">
      {atGate && (
        <p className="flex items-center gap-2 text-sm text-amber-700">
          <Hand aria-hidden className="size-4" /> Option gate · pick the topology to route and check
        </p>
      )}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        {options.map((o) => {
          const chosen = run.selected_option === o.id
          return (
            <article
              key={o.id}
              aria-label={`Option ${NAMES[o.id]}`}
              className={cn('flex flex-col gap-2 rounded-lg border bg-card p-4 shadow-xs', chosen && 'border-emerald-500/60 ring-1 ring-emerald-500/20')}
            >
              <header className="flex items-center justify-between">
                <h3 className="font-medium text-foreground">{NAMES[o.id]}</h3>
                {chosen && (
                  <span className="inline-flex items-center gap-1 text-xs text-emerald-700">
                    <Check aria-hidden className="size-3.5" /> Selected
                  </span>
                )}
              </header>
              <dl className="flex flex-col gap-1">
                <Metric label="Installed" value={fmtQty(o.installed_mva, 'MVA')} />
                <Metric label="Loading normal / failover" value={`${fmtQty(o.normal_loading_pct, '%')} / ${fmtQty(o.failover_loading_pct, '%')}`} />
                <Metric label="Cost" value={fmtUsd(o.cost)} />
                <Metric label="Losses" value={fmtQty(o.losses_kw, 'kW')} />
                <Metric label="Max lead time" value={fmtQty(o.max_lead_time_weeks, 'weeks')} />
                <Metric label="Single points of failure" value={fmtNum(o.spof_count)} />
              </dl>
              {(o.swaps ?? []).length > 0 && (
                <ul className="flex flex-col gap-1 border-t pt-2 text-xs" aria-label="Swaps applied">
                  {(o.swaps ?? []).map((s, i) => (
                    <li key={i} className="flex items-center gap-1 font-mono text-green-700">
                      {String(s.from)} <ArrowRight aria-hidden className="size-3" /> {String(s.to)}
                      <span className="text-muted-foreground">({String(s.reason)}, line {String(s.line)})</span>
                    </li>
                  ))}
                </ul>
              )}
              {atGate && (
                <Button size="sm" className="mt-auto" disabled={!!busy} onClick={() => void select(o.id)}>
                  Select {o.id}
                </Button>
              )}
            </article>
          )
        })}
      </div>
      {error && (
        <p role="alert" className="flex items-center gap-1.5 text-xs text-rose-700">
          <CircleX aria-hidden className="size-3.5" /> {error}
        </p>
      )}
      <IllustrativeLabel />
    </div>
  )
}
