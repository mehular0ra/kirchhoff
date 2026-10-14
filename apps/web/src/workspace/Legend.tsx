import { IllustrativeLabel } from '@/components/Labels'
import { CHAIN_COLORS } from '@/lib/agents'
import { STATUS_META } from '@/lib/status'
import type { FindingStatus } from '@/lib/types'

/** Canvas legend: status (icon + text), diff and what-if colours, plus the illustrative-values label. */
export function Legend({ diff, whatIf }: { diff: boolean; whatIf: boolean }) {
  return (
    <div className="flex flex-col gap-1 rounded-md border bg-zinc-950/90 p-2 text-[11px] text-zinc-300">
      <div className="flex flex-wrap gap-2">
        {(['pass', 'warn', 'fail'] as FindingStatus[]).map((s) => {
          const m = STATUS_META[s]
          const Icon = m.icon
          return (
            <span key={s} className={`inline-flex items-center gap-1 ${m.text}`}>
              <Icon aria-hidden className="size-3" />
              {m.label}
            </span>
          )
        })}
        {diff && <span className="rounded border border-dashed border-amber-400 px-1 text-amber-200">changed</span>}
        {diff && <span className="rounded border border-emerald-400 px-1 text-emerald-200">✓ resolved</span>}
      </div>
      {whatIf && (
        <div className="flex gap-2">
          <span className="inline-flex items-center gap-1">
            <span aria-hidden className="size-2 rounded-full" style={{ background: CHAIN_COLORS.electrical }} /> electrical impact
          </span>
          <span className="inline-flex items-center gap-1">
            <span aria-hidden className="size-2 rounded-full" style={{ background: CHAIN_COLORS.cooling }} /> cooling impact
          </span>
        </div>
      )}
      <IllustrativeLabel />
    </div>
  )
}
