import { motion, useReducedMotion } from 'motion/react'
import { ArrowRight, Bot, CirclePlay, PenLine, ShieldCheck, Zap } from 'lucide-react'
import { Link } from 'react-router'
import { Button } from '@/components/ui/button'
import { KirchhoffMark } from '@/components/KirchhoffMark'
import { FICTIONAL_TEXT, ILLUSTRATIVE_TEXT } from '@/components/Labels'
import { useRecordedRun } from '@/data/useRecordedRun'

// Effects live only here (spec §12). The background traces are decorative and static under reduced motion.
const TRACES = ['M 0 40 H 140 V 120 H 240', 'M 0 150 H 90 V 260 H 220', 'M 0 300 H 170 V 380 H 260', 'M 40 0 V 70 H 120']
// Feeder blue (cooling) and busway amber (power), the -700 tones (--trace-blue / --trace-amber, >= 3:1 on the canvas, checked in theme.contrast.test.ts).
const TRACE_BLUE = 'var(--trace-blue)'
const TRACE_AMBER = 'var(--trace-amber)'
const NODES: [number, number][] = [
  [240, 120],
  [220, 260],
  [260, 380],
  [120, 70],
]

// The three steps: each has its own colour (agents = cooling blue, checks = power amber, sign-off = approved green) and icon, never colour alone.
const STEPS = [
  { t: 'Agents design', d: 'Gemini agents read the tender with verified citations and design power and cooling together.', Icon: Bot, chip: 'bg-blue-600 text-white' },
  { t: 'Physics checks', d: 'A deterministic rule pack checks every number; the AI cannot mark its own homework.', Icon: ShieldCheck, chip: 'bg-amber-400 text-zinc-950' },
  { t: 'An engineer signs', d: 'You decide at each gate, sign the revision, and PRs and the CRM update follow.', Icon: PenLine, chip: 'bg-emerald-700 text-white' },
] as const

export function Landing() {
  const reduce = useReducedMotion()
  const recorded = useRecordedRun()
  return (
    <div className="blueprint relative flex min-h-dvh flex-col overflow-hidden">
      {/* Decorative feeder traces in the side margins only — never across the text (M5) — drawn once,
          and static under reduced motion (MotionConfig alone does not stop a pathLength draw). */}
      {(['left', 'right'] as const).map((edge) => (
        <svg
          key={edge}
          aria-hidden
          viewBox="0 0 300 420"
          className={`pointer-events-none absolute top-28 hidden h-[420px] w-[300px] opacity-90 xl:block ${edge === 'left' ? 'left-6' : 'right-6 -scale-x-100'}`}
          style={{ filter: 'drop-shadow(0 0 5px rgb(37 99 235 / 0.28))' }}
        >
          {TRACES.map((d, i) => (
            <motion.path
              key={d}
              d={d}
              fill="none"
              stroke={i % 2 ? TRACE_BLUE : TRACE_AMBER}
              strokeWidth={2.5}
              strokeLinecap="round"
              strokeLinejoin="round"
              initial={reduce ? false : { pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 2.2, delay: i * 0.25, ease: 'easeInOut' }}
            />
          ))}
          {NODES.map(([cx, cy], i) => (
            <g key={i}>
              <circle cx={cx} cy={cy} r={11} fill={i % 2 ? TRACE_BLUE : TRACE_AMBER} fillOpacity={0.18} />
              <circle cx={cx} cy={cy} r={5} fill={i % 2 ? TRACE_BLUE : TRACE_AMBER} stroke="#ffffff" strokeWidth={2} />
            </g>
          ))}
        </svg>
      ))}
      <header className="relative z-10 flex items-center gap-2 px-6 pt-5 text-sm font-semibold tracking-tight">
        <KirchhoffMark />
        Kirchhoff <span className="font-normal text-slate-600">by Ordinal</span>
      </header>
      <main className="relative z-10 mx-auto flex w-full max-w-5xl flex-1 flex-col items-center gap-6 px-6 pt-16 pb-12 text-center sm:pt-20">
        <p className="glass rounded-full px-3.5 py-1 text-xs font-medium text-slate-700">AI designs. Physics checks. An engineer signs.</p>
        <h1 className="max-w-3xl bg-gradient-to-b from-[#0b0d10] from-55% to-[#1e3a8a] bg-clip-text text-balance text-4xl font-semibold tracking-tight text-transparent forced-colors:bg-none forced-colors:text-[CanvasText] sm:text-5xl">
          Weeks of senior-engineer design work, in one reviewed, signed session.
        </h1>
        <p className="max-w-xl text-pretty text-base text-slate-600">
          Gemini agents read the tender and design power and cooling for an AI data hall. A deterministic checker proves
          every number. The engineer decides and signs, and procurement and sales pick it up from there.
        </p>
        <Button asChild size="lg" className="mt-2 shadow-[0_10px_24px_-10px_rgb(11_13_16/0.6)] ring-1 ring-white/25">
          <Link to="/app">
            Enter the demo workspace (no login) <ArrowRight aria-hidden />
          </Link>
        </Button>
        <div className="flex flex-wrap items-center justify-center gap-3 text-sm">
          <Button asChild variant="glass" size="sm">
            <Link to="/app/p/hall-b">
              <Zap aria-hidden /> Run it live
            </Link>
          </Button>
          {/* Only when Hall A carries a recorded run (residual): the provisional bundle has no events to replay. */}
          {recorded === true && (
            <Button asChild variant="glass" size="sm">
              <Link to="/app/p/hall-a?replay=1">
                <CirclePlay aria-hidden /> Replay a recorded run
              </Link>
            </Button>
          )}
        </div>
        {/* The product in the first viewport (UX-1 I2): a real capture of the shipped Hall A view, ~90 kB, fetched first (N4). */}
        <figure className="relative mt-6 w-full">
          {/* A soft cooling-blue / power-amber glow under the frame, so the glass bezel has something to refract. */}
          <div aria-hidden className="pointer-events-none absolute inset-x-10 -inset-y-4 -z-10 rounded-[2rem] bg-gradient-to-r from-blue-500/30 via-indigo-400/20 to-amber-400/30 blur-2xl" />
          <div className="glass-strong rounded-2xl p-2">
            <div className="overflow-hidden rounded-xl border border-border bg-background">
              <div aria-hidden className="flex items-center gap-1.5 border-b border-border bg-gradient-to-b from-white to-slate-100 px-3 py-2">
                <span className="size-2.5 rounded-full bg-red-400" />
                <span className="size-2.5 rounded-full bg-amber-400" />
                <span className="size-2.5 rounded-full bg-emerald-500" />
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
          </div>
          <figcaption className="mt-3 text-xs text-slate-600">Hall A (sample): the first revision’s failures, fixed and signed.</figcaption>
        </figure>
        <ol className="mt-4 grid w-full max-w-3xl grid-cols-1 gap-3 text-left text-sm sm:grid-cols-3" aria-label="How it works">
          {STEPS.map(({ t, d, Icon, chip }, i) => (
            <li key={t} className="glass relative rounded-xl p-4">
              <div className="flex items-center gap-2">
                <span className={`grid h-6 min-w-8 place-items-center rounded-md px-1.5 font-mono text-xs font-semibold ${chip}`}>0{i + 1}</span>
                <Icon aria-hidden className="size-4 text-slate-700" />
              </div>
              <p className="mt-2.5 font-semibold text-foreground">{t}</p>
              <p className="mt-0.5 text-xs leading-relaxed text-slate-600">{d}</p>
              {/* The signal path from step to step: a short trace with a node across the gap (sm and up, where the cards sit in a row). */}
              {i < STEPS.length - 1 && (
                <span aria-hidden className="absolute top-1/2 -right-3 hidden h-0.5 w-3 -translate-y-1/2 bg-[var(--trace-blue)] sm:block">
                  <span className="absolute top-1/2 -right-0.5 size-2 -translate-y-1/2 rounded-full border-2 border-white bg-[var(--trace-blue)]" />
                </span>
              )}
            </li>
          ))}
        </ol>
        <p className="text-xs text-slate-600">Built on Gemini · ADK · Cloud Run · Firestore · Firebase</p>
      </main>
      <footer className="relative z-10 flex flex-col items-center gap-1 p-4 text-center text-xs text-slate-600">
        <span>{FICTIONAL_TEXT}</span>
        <span>{ILLUSTRATIVE_TEXT}</span>
      </footer>
    </div>
  )
}
