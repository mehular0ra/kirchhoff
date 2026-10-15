import { cn } from 'cn'
import { CircleCheck, CircleDashed, CircleX, TriangleAlert } from 'lucide-react'
import { countByStatus } from '@/lib/select'
import type { Finding } from '@/lib/types'

/** Worst outcome of a revision's checks, icon + text (M7: warnings and "not checked yet" are not "all pass"). */
export function RevisionVerdict({ findings }: { findings: Finding[] }) {
  const c = countByStatus(findings)
  const v = !findings.length
    ? { icon: CircleDashed, cls: 'text-muted-foreground', text: 'not checked yet' }
    : c.fail > 0
      ? { icon: CircleX, cls: 'text-rose-700', text: `${c.fail} fail` }
      : c.warn > 0
        ? { icon: TriangleAlert, cls: 'text-amber-700', text: `${c.warn} warn` }
        : { icon: CircleCheck, cls: 'text-emerald-700', text: 'all pass' }
  const Icon = v.icon
  return (
    <span className={cn('inline-flex items-center gap-0.5', v.cls)}>
      <Icon aria-hidden className="size-3.5" />
      {v.text}
    </span>
  )
}
