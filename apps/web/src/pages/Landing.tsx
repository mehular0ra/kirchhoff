import { motion, useReducedMotion } from 'motion/react'
import { ArrowRight, CirclePlay, Zap } from 'lucide-react'
import { Link } from 'react-router'
import { Button } from '@/components/ui/button'
import { KirchhoffMark } from '@/components/KirchhoffMark'
import { FICTIONAL_TEXT, ILLUSTRATIVE_TEXT } from '@/components/Labels'
import { useRecordedRun } from '@/data/useRecordedRun'

// Effects live only here (spec §12). The background traces are decorative and static under reduced motion.
const TRACES = ['M 0 40 H 140 V 120 H 240', 'M 0 150 H 90 V 260 H 220', 'M 0 300 H 170 V 380 H 260', 'M 40 0 V 70 H 120']
// Feeder blue (the accent) and busway amber, at -600 so the hairlines read on white.
const TRACE_BLUE = '#2563eb'
const TRACE_AMBER = '#d97706'
const NODES: [number, number][] = [
  [240, 120],
  [220, 260],
  [260, 380],
  [120, 70],
]

export function Landing() {
  const reduce = useReducedMotion()
  const recorded = useRecordedRun()
  return (
    <div className="relative flex min-h-dvh flex-col overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(37,99,235,0.07),transparent_55%),radial-gradient(ellipse_at_bottom_right,rgba(245,158,11,0.06),transparent_50%)]"
      />
      {/* Decorative feeder traces in the side margins only — never across the text (M5) — drawn once,
          and static under reduced motion (MotionConfig alone does not stop a pathLength draw). */}
      {(['left', 'right'] as const).map((edge) => (
        <svg
          key={edge}
          aria-hidden
          viewBox="0 0 300 420"
          className={`pointer-events-none absolute top-28 hidden h-[420px] w-[300px] opacity-40 xl:block ${edge === 'left' ? 'left-6' : 'right-6 -scale-x-100'}`}
        >
          {TRACES.map((d, i) => (
            <motion.path
              key={d}
              d={d}
              fill="none"
              stroke={i % 2 ? TRACE_BLUE : TRACE_AMBER}
              strokeWidth={1.5}
              initial={reduce ? false : { pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 2.2, delay: i * 0.25, ease: 'easeInOut' }}
            />
          ))}
          {NODES.map(([cx, cy], i) => (
            <circle key={i} cx={cx} cy={cy} r={3.5} fill={i % 2 ? TRACE_BLUE : TRACE_AMBER} />
          ))}
        </svg>
      ))}
      <header className="relative z-10 flex items-center gap-2 px-6 pt-5 text-sm font-semibold tracking-tight">
        <KirchhoffMark />
        Kirchhoff <span className="font-normal text-muted-foreground">by Ordinal</span>
      </header>
      <main className="relative z-10 mx-auto flex w-full max-w-5xl flex-1 flex-col items-center gap-6 px-6 pt-16 pb-12 text-center sm:pt-20">
        <p className="rounded-full border border-zinc-300 px-3 py-1 text-xs text-muted-foreground">
          AI designs. Physics checks. An engineer signs.
        </p>
        <h1 className="max-w-3xl text-balance text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
          Weeks of senior-engineer design work, in one reviewed, signed session.
        </h1>
        <p className="max-w-xl text-pretty text-base text-muted-foreground">
          Gemini agents read the tender and design power and cooling for an AI data hall. A deterministic checker proves
          every number. The engineer decides and signs, and procurement and sales pick it up from there.
        </p>
        <Button asChild size="lg" className="mt-2">
          <Link to="/app">
            Enter the demo workspace (no login) <ArrowRight aria-hidden />
          </Link>
        </Button>
        <div className="flex flex-wrap items-center justify-center gap-3 text-sm">
          <Button asChild variant="outline" size="sm">
            <Link to="/app/p/hall-b">
              <Zap aria-hidden /> Run it live
            </Link>
          </Button>
          {/* Only when Hall A carries a recorded run (residual): the provisional bundle has no events to replay. */}
          {recorded === true && (
            <Button asChild variant="ghost" size="sm">
              <Link to="/app/p/hall-a?replay=1">
                <CirclePlay aria-hidden /> Replay a recorded run
              </Link>
            </Button>
          )}
        </div>
        {/* The product in the first viewport (UX-1 I2): a real capture of the shipped Hall A view, ~90 kB, fetched first (N4). */}
        <figure className="mt-6 w-full">
          <div className="overflow-hidden rounded-xl border border-border bg-background shadow-[0_1px_2px_rgba(15,23,42,0.06),0_24px_64px_-24px_rgba(15,23,42,0.28)]">
            <div aria-hidden className="flex items-center gap-1.5 border-b border-border bg-surface px-3 py-2">
              <span className="size-2.5 rounded-full bg-zinc-300" />
              <span className="size-2.5 rounded-full bg-zinc-300" />
              <span className="size-2.5 rounded-full bg-zinc-300" />
            </div>
            <img
              src="/landing/hall-a-r2.webp"
              width={1440}
              height={900}
              // Above the fold on desktop (N4): lazy-loading left a grey box at ~2.6 s.
              loading="eager"
              fetchPriority="high"
              decoding="async"
              alt="Hall A (sample) in Kirchhoff's 3D view: the signed revision with each fixed check called out as resolved, the revision story, the agent lanes and the co-pilot's what-if chips."
              className="block aspect-[16/10] h-auto w-full bg-muted"
            />
          </div>
          <figcaption className="mt-2 text-xs text-muted-foreground">Hall A (sample): the first revision’s failures, fixed and signed.</figcaption>
        </figure>
        <ol className="mt-4 grid w-full max-w-3xl grid-cols-1 gap-3 text-left text-sm sm:grid-cols-3" aria-label="How it works">
          {[
            ['Agents design', 'Gemini agents read the tender with verified citations and design power and cooling together.'],
            ['Physics checks', 'A deterministic rule pack checks every number; the AI cannot mark its own homework.'],
            ['An engineer signs', 'You decide at each gate, sign the revision, and PRs and the CRM update follow.'],
          ].map(([t, d], i) => (
            <li key={t} className="rounded-lg border border-border bg-surface p-4">
              <span className="font-mono text-xs text-muted-foreground">0{i + 1}</span>
              <p className="font-medium text-foreground">{t}</p>
              <p className="text-xs text-muted-foreground">{d}</p>
            </li>
          ))}
        </ol>
        <p className="text-xs text-muted-foreground">Built on Gemini · ADK · Cloud Run · Firestore · Firebase</p>
      </main>
      <footer className="relative z-10 flex flex-col items-center gap-1 p-4 text-center text-xs text-muted-foreground">
        <span>{FICTIONAL_TEXT}</span>
        <span>{ILLUSTRATIVE_TEXT}</span>
      </footer>
    </div>
  )
}
