import { IllustrativeLabel } from '@/components/Labels'
import { CHAIN_COLORS } from '@/lib/agents'
import { STATUS_META } from '@/lib/status'
import type { FindingStatus } from '@/lib/types'

/**
 * Canvas legend: status (icon + text), diff and what-if keys, plus the illustrative-values label.
 * Only the keys present in the current view are listed (UX-1 I1): a clean signed revision shows no
 * Fail or Warn key it never uses. What-if impact keys are short line swatches, so they never read as
 * a status dot (D6).
 */
export function Legend({
  statuses,
  diff,
  resolved,
  whatIf,
}: {
  statuses: ReadonlySet<FindingStatus>
  diff: boolean
  resolved: boolean
  whatIf: boolean
}) {
  const shown = (['pass', 'warn', 'fail'] as FindingStatus[]).filter((s) => statuses.has(s))
  return (
    <div className="flex flex-col gap-1 rounded-md border bg-background/90 p-2 text-[11px] text-zinc-700 shadow-sm backdrop-blur-sm">
      {(shown.length > 0 || diff || resolved) && (
        <div className="flex flex-wrap gap-2">
          {shown.map((s) => {
            const m = STATUS_META[s]
            const Icon = m.icon
            return (
              <span key={s} className={`inline-flex items-center gap-1 ${m.text}`}>
                <Icon aria-hidden className="size-3" />
                {m.label}
              </span>
            )
          })}
          {diff && <span className="rounded border border-dashed border-amber-500 px-1 text-amber-700">changed</span>}
          {resolved && <span className="rounded border border-emerald-500 px-1 text-emerald-700">✓ resolved</span>}
        </div>
      )}
      {whatIf && (
        <div className="flex gap-3">
          <span className="inline-flex items-center gap-1.5">
            <span aria-hidden className="h-0.5 w-4 rounded-full" style={{ background: CHAIN_COLORS.electrical }} /> electrical impact
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span aria-hidden className="h-0.5 w-4 rounded-full" style={{ background: CHAIN_COLORS.cooling }} /> cooling impact
          </span>
        </div>
      )}
      <IllustrativeLabel />
    </div>
  )
}
