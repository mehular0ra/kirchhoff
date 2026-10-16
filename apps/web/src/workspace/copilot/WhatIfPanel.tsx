import { LoaderCircle, TriangleAlert, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Num } from '@/components/Labels'
import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { CHAIN_COLORS } from '@/lib/agents'
import { fmtQty } from '@/lib/format'
import { classifyChain } from '@/lib/impact'
import { revisionLabel } from '@/lib/select'
import { statusRank } from '@/lib/status'
import type { WhatIfParam } from '@/lib/types'
import { useUi } from '@/store/ui'
import { useWorkspace } from '../WorkspaceContext'
import { chipLabel, chipsFor, paramLabel, useWhatIf, WHAT_IF_PRESETS } from './useWhatIf'

const COLLAPSED = 6
const PARAMS: WhatIfParam[] = ['rack_kw', 'liquid_fraction', 'dv_limit_pct', 'tx_loading_cap_pct']

/** What-if chips + custom input + result with the two-colour impact chain (spec §3 1:40–1:58). */
export function WhatIfPanel() {
  const view = useWorkspace()
  const active = useUi((s) => s.whatIf)
  const { run, revRef, loading, error, clear } = useWhatIf()
  const [param, setParam] = useState<WhatIfParam>('rack_kw')
  const [value, setValue] = useState('')
  // The chips run on the head revision unless one was picked in the revision bar (#37): its seed what-ifs.
  const chips = chipsFor(view.bundle.what_ifs.filter((w) => w.revision_ref === revRef))
  // "Show all" belongs to one what-if result; a new result starts collapsed again.
  const [expanded, setExpanded] = useState<object | null>(null)
  const showAll = !!active && expanded === active.result
  const setShowAll = (on: boolean) => setExpanded(on && active ? active.result : null)
  const [expandedChains, setExpandedChains] = useState<object | null>(null)
  const showAllChains = !!active && expandedChains === active.result
  const setShowAllChains = (on: boolean) => setExpandedChains(on && active ? active.result : null)
  // Up to three chains per discipline first, so both colours of the story are visible at once.
  const chains = useMemo(
    () => (active?.result.impact_chain ?? []).map((chain) => ({ chain, d: classifyChain(chain, view.model) })),
    [active, view.model],
  )
  const shortChains = useMemo(
    () => [...chains.filter((c) => c.d === 'electrical').slice(0, 3), ...chains.filter((c) => c.d !== 'electrical').slice(0, 3)],
    [chains],
  )
  const sorted = useMemo(
    () => [...(active?.result.findings ?? [])].sort((a, b) => statusRank(b.status) - statusRank(a.status)),
    [active],
  )
  if (!view.rev) return null

  return (
    <section aria-label="What-if" className="flex flex-col gap-2 border-b p-3">
      <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">What if…</h3>
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
            <option key={p} value={p} className="bg-background">
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
        <p role="alert" className="flex items-start gap-1.5 text-xs text-amber-700">
          <TriangleAlert aria-hidden className="size-3.5 shrink-0" />
          <span>{error}</span>
        </p>
      )}
      {active && (
        <div className="flex flex-col gap-2 rounded border border-amber-500/40 bg-amber-500/5 p-2 text-xs" aria-live="polite">
          <div className="flex items-center gap-2">
            <span className="whitespace-nowrap font-medium text-amber-700">{chipLabel(active.result)}</span>
            {/* The overlay is always drawn on the revision it was computed for (M13, #37), so this names that one. */}
            <span className="text-muted-foreground">
              {revisionLabel(view.rev)} · not saved · {active.origin === 'precomputed' ? 'precomputed by the engine' : 'engine, just now'}
            </span>
            <Button size="icon-xs" variant="ghost" className="ml-auto" aria-label="Clear what-if" onClick={clear}>
              <X aria-hidden />
            </Button>
          </div>
          {/* The chain first: it is the story ("lights up across power and cooling"); the list follows (M13). */}
          <ol className="flex flex-col gap-1" aria-label="Impact chain">
            {(showAllChains ? chains : shortChains).map(({ chain, d }) => {
              return (
                <li key={chain.join('>')} className="flex items-center gap-1.5">
                  <span aria-hidden className="size-2 shrink-0 rounded-full" style={{ background: CHAIN_COLORS[d] }} />
                  <span className="text-muted-foreground">{d === 'electrical' ? 'Electrical' : 'Cooling'}:</span>
                  <span className="font-mono text-foreground">{chain.join(' → ')}</span>
                </li>
              )
            })}
          </ol>
          {chains.length > shortChains.length && (
            <Button size="xs" variant="ghost" className="self-start" onClick={() => setShowAllChains(!showAllChains)}>
              {showAllChains ? 'Show fewer chains' : `Show all ${chains.length} impact chains`}
            </Button>
          )}
          <ul className="flex flex-col gap-1" aria-label="What-if failures">
            {(showAll ? sorted : sorted.slice(0, COLLAPSED)).map((f) => (
              <li key={f.id} className="flex flex-wrap items-center gap-x-1.5">
                <StatusBadge status={f.status} compact />
                <span className="font-mono text-foreground">
                  {f.rule_id} · {f.element_id}
                </span>
                {typeof f.value === 'number' && (
                  <span className="text-muted-foreground">
                    <Num>{fmtQty(f.value, f.unit)}</Num> vs limit <Num>{fmtQty(f.limit ?? null, f.unit)}</Num>
                  </span>
                )}
              </li>
            ))}
          </ul>
          {sorted.length > COLLAPSED && (
            <Button size="xs" variant="ghost" className="self-start" onClick={() => setShowAll(!showAll)}>
              {showAll ? 'Show fewer' : `Show all ${sorted.length} findings`}
            </Button>
          )}
        </div>
      )}
    </section>
  )
}
