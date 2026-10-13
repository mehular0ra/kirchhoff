import { CircleCheck, TriangleAlert } from 'lucide-react'
import { motion } from 'motion/react'
import { TenderChip } from '@/components/TenderChip'
import { fmtQty } from '@/lib/format'
import { useWorkspace } from './WorkspaceContext'

/** Intake's requirement cards (spec §3 0:10–0:30): each with its verified quote and a tender chip. */
export function RequirementsPanel() {
  const { bundle } = useWorkspace()
  const brief = bundle.brief
  if (!brief) return <p className="p-3 text-xs text-zinc-500">Requirement cards appear when Intake has read the tender.</p>
  return (
    <section aria-label="Requirements" className="flex flex-col gap-2 p-3">
      <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-500">Citations</h3>
      <ol className="flex flex-col gap-2">
        {brief.requirements.map((r, i) => (
          <motion.li
            key={r.id}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: Math.min(i, 12) * 0.05 }}
            className="rounded border bg-card p-2 text-xs"
          >
            <p className="text-zinc-200">{r.text}</p>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              {typeof r.value === 'number' && <span className="font-mono text-zinc-300">{fmtQty(r.value, r.unit)}</span>}
              {typeof r.value === 'string' && <span className="font-mono text-zinc-300">{r.value}</span>}
              <TenderChip citation={r.citation} />
              {r.verified ? (
                <span className="inline-flex items-center gap-1 text-emerald-400">
                  <CircleCheck aria-hidden className="size-3.5" /> quote verified
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-amber-300">
                  <TriangleAlert aria-hidden className="size-3.5" /> quote not verified
                </span>
              )}
            </div>
          </motion.li>
        ))}
      </ol>
    </section>
  )
}
