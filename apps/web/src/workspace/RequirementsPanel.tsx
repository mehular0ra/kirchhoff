import { CircleCheck, TriangleAlert } from 'lucide-react'
import { motion } from 'motion/react'
import { TenderChip } from '@/components/TenderChip'
import { fmtQty } from '@/lib/format'
import { useWorkspace } from './WorkspaceContext'

/** WS2's UNVERIFIED_TEMPLATE (services/api/kirchhoff/intake/brief.py). */
export const UNVERIFIED_TEXT = 'Requirement not accepted: the quote was not found on the cited page.'

/** What a recorded sample without Intake's brief does include (D10, N5); a live run still fills the cards. */
export const SAMPLE_WITHOUT_BRIEF = 'This sample includes the checked design, findings and sign-off; the tender requirements are in the Docs tab.'

/** Intake's requirement cards (spec §3 0:10–0:30): each with its verified quote and a tender chip. */
export function RequirementsPanel() {
  const { bundle, source } = useWorkspace()
  const brief = bundle.brief
  if (!brief)
    return (
      <p className="p-3 text-xs text-muted-foreground">
        {/* N5: a replayed recording has no brief either, same as a static sample (?replay=1 is still source 'replay'). */}
        {source !== 'live' ? SAMPLE_WITHOUT_BRIEF : 'Requirement cards appear when Intake has read the tender.'}
      </p>
    )
  return (
    <section aria-label="Requirements" className="flex flex-col gap-2 p-3">
      <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Citations</h3>
      <ol className="flex flex-col gap-2">
        {brief.requirements.map((r, i) => (
          <motion.li
            key={r.id}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: Math.min(i, 12) * 0.05 }}
            className="rounded border bg-card p-2 text-xs"
          >
            {/* Defence in depth (§6.3): never show an unaccepted requirement's text as if it were the tender's. */}
            <p className={r.verified ? 'text-foreground' : 'text-amber-700'}>{r.verified ? r.text : UNVERIFIED_TEXT}</p>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              {r.verified && typeof r.value === 'number' && <span className="font-mono text-zinc-700">{fmtQty(r.value, r.unit)}</span>}
              {r.verified && typeof r.value === 'string' && <span className="font-mono text-zinc-700">{r.value}</span>}
              <TenderChip citation={r.citation} verified={r.verified} />
              {r.verified ? (
                <span className="inline-flex items-center gap-1 text-emerald-700">
                  <CircleCheck aria-hidden className="size-3.5" /> quote verified
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-amber-700">
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
