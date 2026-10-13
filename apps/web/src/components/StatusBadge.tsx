import { cn } from 'cn'
import { STATUS_META } from '@/lib/status'
import type { FindingStatus } from '@/lib/types'

export function StatusBadge({
  status,
  compact = false,
  className,
}: {
  status: FindingStatus
  compact?: boolean
  className?: string
}) {
  const m = STATUS_META[status]
  const Icon = m.icon
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs font-medium',
        m.text,
        m.bg,
        m.border,
        compact && 'border-transparent bg-transparent px-0',
        className,
      )}
    >
      <Icon aria-hidden className="size-3.5" />
      <span>{m.label}</span>
    </span>
  )
}
