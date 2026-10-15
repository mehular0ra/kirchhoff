import { cn } from 'cn'
import { Num } from '@/components/Labels'
import { fmtNum, fmtQty, isCountRule } from '@/lib/format'
import { STATUS_META } from '@/lib/status'
import type { FindingStatus } from '@/lib/types'

/** Value vs limit, both from the finding record. Bar geometry is visual only; no number is derived for display. */
export function ValueLimitBar({
  value,
  limit,
  unit,
  status,
}: {
  value: number
  limit: number
  unit: string | null | undefined
  status: FindingStatus
}) {
  const m = STATUS_META[status]
  if (isCountRule(unit, limit)) {
    // A count against a count (R11: 1 crossing, limit 0): words, not a bar (D9).
    const Icon = m.icon
    return (
      <p className="flex items-center gap-1.5 text-sm">
        <Icon aria-hidden className={cn('size-4 shrink-0', m.text)} />
        <span className={m.text}>{m.label}</span>{' '}
        <span className="text-zinc-200">
          · <Num>{fmtQty(value, unit)}</Num> (limit <Num>{fmtNum(limit)}</Num>)
        </span>
      </p>
    )
  }
  const max = Math.max(Math.abs(value), Math.abs(limit)) * 1.25 || 1
  const pct = (n: number) => `${Math.min(100, (Math.abs(n) / max) * 100)}%`
  return (
    <div className="flex flex-col gap-1.5">
      <div
        role="img"
        aria-label={`Value ${fmtQty(value, unit)} against limit ${fmtQty(limit, unit)}: ${m.label}`}
        className="relative h-2.5 rounded-full bg-zinc-800"
      >
        <div
          className={cn('absolute inset-y-0 left-0 rounded-full', status === 'fail' ? 'bg-rose-500' : status === 'warn' ? 'bg-amber-400' : 'bg-emerald-500')}
          style={{ width: pct(value) }}
        />
        <div className="absolute -inset-y-1 w-0.5 bg-zinc-100" style={{ left: pct(limit) }} />
      </div>
      <div className="flex justify-between text-xs">
        <span className={m.text}>
          Value <Num>{fmtQty(value, unit)}</Num>
        </span>
        <span className="text-zinc-300">
          Limit <Num>{fmtQty(limit, unit)}</Num>
        </span>
      </div>
    </div>
  )
}
