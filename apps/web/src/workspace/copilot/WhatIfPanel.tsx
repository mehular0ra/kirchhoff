import { LoaderCircle, TriangleAlert, X } from 'lucide-react'
import { useState } from 'react'
import { Num } from '@/components/Labels'
import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { CHAIN_COLORS } from '@/lib/agents'
import { fmtQty } from '@/lib/format'
import { classifyChain } from '@/lib/impact'
import type { WhatIfParam } from '@/lib/types'
import { useUi } from '@/store/ui'
import { useWorkspace } from '../WorkspaceContext'
import { chipLabel, chipsFor, paramLabel, useWhatIf, WHAT_IF_PRESETS } from './useWhatIf'

const PARAMS: WhatIfParam[] = ['rack_kw', 'liquid_fraction', 'dv_limit_pct', 'tx_loading_cap_pct']

/** What-if chips + custom input + result with the two-colour impact chain (spec §3 1:40–1:58). */
export function WhatIfPanel() {
  const view = useWorkspace()
  const active = useUi((s) => s.whatIf)
  const { run, loading, error, clear } = useWhatIf()
  const [param, setParam] = useState<WhatIfParam>('rack_kw')
  const [value, setValue] = useState('')
  const chips = chipsFor(view.bundle.what_ifs.filter((w) => w.revision_ref === view.revRef))
  if (!view.rev) return null

  return (
    <section aria-label="What-if" className="flex flex-col gap-2 border-b p-3">
      <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-500">What if…</h3>
      <div className="flex flex-wrap gap-1.5">
        {chips.map((c, i) => (
          <Button
            key={`${c.param}:${c.value}`}
            size="xs"
            variant="outline"
            data-tour={i === 0 ? 'whatif-chip' : undefined}
            disabled={loading}
            onClick={() => void run(c.param, c.value)}
          >
            {chipLabel(c)}
          </Button>
        ))}
      </div>
      <form
        className="flex items-center gap-1.5"
        onSubmit={(e) => {
          e.preventDefault()
          const v = Number(value)
          if (value.trim() && Number.isFinite(v)) void run(param, v)
        }}
      >
        <select
          aria-label="What-if parameter"
          value={param}
          onChange={(e) => setParam(e.target.value as WhatIfParam)}
          className="h-7 rounded border bg-transparent px-1 text-xs"
        >
          {PARAMS.map((p) => (
            <option key={p} value={p} className="bg-zinc-900">
              {paramLabel(p)}
            </option>
          ))}
        </select>
        <Input
          aria-label="What-if value"
          inputMode="decimal"
          placeholder={String(WHAT_IF_PRESETS.find((c) => c.param === param)?.value ?? '')}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="h-7 w-20 text-xs"
        />
        <Button size="xs" type="submit" disabled={loading}>
          {loading ? <LoaderCircle aria-hidden className="animate-spin" /> : null} Run
        </Button>
      </form>
      {error && (
        <p role="alert" className="flex items-start gap-1.5 text-xs text-amber-200">
          <TriangleAlert aria-hidden className="size-3.5 shrink-0" />
          <span>{error}</span>
        </p>
      )}
      {active && (
        <div className="flex flex-col gap-2 rounded border border-amber-400/40 bg-amber-500/5 p-2 text-xs" aria-live="polite">
          <div className="flex items-center gap-2">
            <span className="font-medium text-amber-100">{chipLabel(active.result)}</span>
            <span className="text-zinc-400">not saved · {active.origin === 'precomputed' ? 'precomputed by the engine' : 'engine, just now'}</span>
            <Button size="icon-xs" variant="ghost" className="ml-auto" aria-label="Clear what-if" onClick={clear}>
              <X aria-hidden />
            </Button>
          </div>
          <ul className="flex flex-col gap-1" aria-label="What-if failures">
            {active.result.findings.map((f) => (
              <li key={f.id} className="flex flex-wrap items-center gap-1.5">
                <StatusBadge status={f.status} compact />
                <span className="font-mono text-zinc-100">
                  {f.rule_id} · {f.element_id}
                </span>
                {typeof f.value === 'number' && (
                  <span className="text-zinc-400">
                    <Num>{fmtQty(f.value, f.unit)}</Num> vs limit <Num>{fmtQty(f.limit ?? null, f.unit)}</Num>
                  </span>
                )}
              </li>
            ))}
          </ul>
          <ol className="flex flex-col gap-1" aria-label="Impact chain">
            {active.result.impact_chain.map((chain) => {
              const d = classifyChain(chain, view.model)
              return (
                <li key={chain.join('>')} className="flex items-center gap-1.5">
                  <span aria-hidden className="size-2 shrink-0 rounded-full" style={{ background: CHAIN_COLORS[d] }} />
                  <span className="text-zinc-400">{d === 'electrical' ? 'Electrical' : 'Cooling'}:</span>
                  <span className="font-mono text-zinc-200">{chain.join(' → ')}</span>
                </li>
              )
            })}
          </ol>
        </div>
      )}
    </section>
  )
}
