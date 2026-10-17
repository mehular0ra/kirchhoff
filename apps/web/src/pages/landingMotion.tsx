import { motion, useReducedMotion } from 'motion/react'
import type { ReactNode } from 'react'
import { canObserveViewport } from './useReveal'

// The landing page's motion lives in this file and useReveal.ts, so it can be taken out as one piece. Every part renders in its final state from the first
// frame under "reduce motion" (and wherever the browser cannot observe the viewport), and nothing here moves for decoration after it has played once.

const EASE = [0.2, 0.7, 0.2, 1] as const

const FLAGGED = new Set([17, 38])

/**
 * A picture of what the checker does, not data: a grid of checks where nearly all pass and two are flagged. Decorative (aria-hidden). When it scrolls into view
 * it fills cell by cell, like a run of checks, and the two flagged cells swell once as the sweep passes them.
 */
export function CheckGrid() {
  const animated = !useReducedMotion() && canObserveViewport()
  return (
    <motion.div
      aria-hidden
      data-check-grid
      className="grid grid-cols-12 gap-1.5"
      initial={animated ? 'hidden' : false}
      whileInView={animated ? 'shown' : undefined}
      viewport={{ once: true, amount: 0.6 }}
      variants={{ hidden: {}, shown: { transition: { staggerChildren: 0.012 } } }}
    >
      {Array.from({ length: 60 }, (_, i) => {
        const flagged = FLAGGED.has(i)
        return (
          <motion.span
            key={i}
            variants={{
              hidden: { opacity: 0, scale: 0.4 },
              shown: flagged
                ? { opacity: 1, scale: [0.4, 1, 1.4, 1], transition: { opacity: { duration: 0.25 }, scale: { duration: 1.1, times: [0, 0.3, 0.65, 1], ease: 'easeOut' } } }
                : { opacity: 1, scale: 1, transition: { duration: 0.25, ease: 'easeOut' } },
            }}
            className={`aspect-square rounded-[5px] ${flagged ? 'bg-rose-500 ring-2 ring-rose-200' : 'bg-emerald-500/75'}`}
          />
        )
      })}
    </motion.div>
  )
}

/**
 * One of the three "How it works" cards. The cards come in left to right, and the trace to the next card draws across the gap just after its card lands, so the
 * eye follows the signal path from step to step. `last` has no trace after it. The trace shows from `sm` up, where the cards sit in a row.
 */
export function StepCard({ index, last, className, children }: { index: number; last: boolean; className?: string; children: ReactNode }) {
  const animated = !useReducedMotion() && canObserveViewport()
  const at = index * 0.45
  return (
    <motion.li
      className={className}
      initial={animated ? 'hidden' : false}
      whileInView={animated ? 'shown' : undefined}
      viewport={{ once: true, amount: 0.5 }}
      variants={{ hidden: { opacity: 0, y: 14 }, shown: { opacity: 1, y: 0, transition: { duration: 0.5, delay: at, ease: EASE } } }}
    >
      {children}
      {!last && (
        <motion.span
          aria-hidden
          data-step-link
          className="absolute top-1/2 -right-4 hidden h-0.5 w-4 origin-left -translate-y-1/2 bg-[var(--trace-blue)] sm:block"
          variants={{ hidden: { scaleX: 0 }, shown: { scaleX: 1, transition: { duration: 0.35, delay: at + 0.4, ease: 'easeInOut' } } }}
        >
          <motion.span
            className="absolute top-1/2 -right-0.5 size-2 -translate-y-1/2 rounded-full border-2 border-white bg-[var(--trace-blue)]"
            variants={{ hidden: { scale: 0 }, shown: { scale: 1, transition: { duration: 0.25, delay: at + 0.7, ease: EASE } } }}
          />
        </motion.span>
      )}
    </motion.li>
  )
}
