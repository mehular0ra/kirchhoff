import { motion, useReducedMotion } from 'motion/react'
import { useState } from 'react'
import { Bot, CirclePlay, Cloud, Database, FileSearch, Flame, Layers, MessageCircleQuestion, PenLine, ShieldCheck, Sparkles, Stamp, Truck, Workflow, Zap } from 'lucide-react'
import { Link } from 'react-router'
import { Button } from '@/components/ui/button'
import { KirchhoffMark } from '@/components/KirchhoffMark'
import { FICTIONAL_TEXT, ILLUSTRATIVE_TEXT } from '@/components/Labels'
import { useRecordedRun } from '@/data/useRecordedRun'
import { CheckGrid, StepCard } from './landingMotion'
import { AREAS, SHOT } from './shotAreas'
import { useReveal } from './useReveal'

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

// The three steps are a real sequence (the three gates), so they are numbered; each has its own colour and an icon, never colour alone.
const STEPS = [
  { t: 'Agents design', d: 'Gemini agents read the tender with verified citations and design power and cooling together.', Icon: Bot, chip: 'bg-blue-600 text-white' },
  { t: 'Physics checks', d: 'A deterministic rule pack checks every number; the AI cannot mark its own homework.', Icon: ShieldCheck, chip: 'bg-amber-400 text-zinc-950' },
  { t: 'An engineer signs', d: 'You decide at each gate, sign the revision, and PRs and the CRM update follow.', Icon: PenLine, chip: 'bg-emerald-700 text-white' },
] as const

/** The three areas of the screenshot, left to right, each with the icon its card carries. */
const SCREENSHOT_LEGEND = [
  ['Agent lanes', 'Each agent’s status, with the quotes it verified against the tender.', 'left', Bot],
  ['3D hall', 'Every finding drawn where it happens, with the clause that raised it.', 'centre', Layers],
  ['Co-pilot', 'Ask why a check failed, or what if a rack load or a limit changes.', 'right', MessageCircleQuestion],
] as const

/**
 * A small map of the workspace's three columns (agents, hall, co-pilot) with one filled, so a card says where in the picture its area is. The columns have the
 * proportions measured on the real layout at the screenshot's width (shotAreas.ts), drawn in the 44-unit inner width of the frame; a white stroke makes the
 * gaps between them without changing their widths.
 */
function WhereInShot({ at }: { at: 'left' | 'centre' | 'right' }) {
  const names = ['left', 'centre', 'right'] as const
  const unit = 44 / SHOT.w
  return (
    <svg aria-hidden data-at={at} viewBox="0 0 52 34" className="h-9 w-14 shrink-0">
      <rect x="1" y="1" width="50" height="32" rx="5" fill="white" fillOpacity="0.8" stroke="var(--glass-edge)" strokeWidth="1.25" />
      {names.map((name, i) => (
        <rect
          key={name}
          data-col={name}
          x={4 + SHOT.cols[i] * unit}
          y="6"
          width={(SHOT.cols[i + 1] - SHOT.cols[i]) * unit}
          height="22"
          rx="2.5"
          fill={name === at ? 'var(--brand-text)' : 'var(--glass-edge)'}
          fillOpacity={name === at ? 0.9 : 0.5}
          stroke="white"
          strokeWidth="1.5"
        />
      ))}
    </svg>
  )
}

/** Generic icons (not the products' own logos), one per service, so the five tiles read as a set. */
const GOOGLE_STACK = [
  ['Gemini on Vertex AI', Sparkles],
  ['Agent Development Kit', Workflow],
  ['Cloud Run', Cloud],
  ['Firestore', Database],
  ['Firebase', Flame],
] as const

const FEATURES = [
  { t: 'Reads the tender and quotes it back', d: 'A requirement counts only if its quote is found on the tender page. Where the documents contradict each other, it asks you instead of guessing.', Icon: FileSearch },
  { t: 'Designs power and cooling together', d: 'Layout, power, cooling and procurement agents share one model of the hall, so a pipe routed over a live feeder is caught as a clash.', Icon: Layers },
  { t: 'Answers what if', d: 'Change a rack load or a limit, by typing or by voice, and see which checks fail and which feeders and pipes are affected.', Icon: MessageCircleQuestion },
  { t: 'Plans around your supply chain', d: 'Lead times and stock come from the ERP. A part that cannot arrive in time is swapped for one in stock, and the swap is shown on the option card.', Icon: Truck },
  { t: 'Hands off once signed', d: 'The signed revision gets a hash. Purchase requisitions go to the ERP, the calc report is filed and the CRM stage moves. In this demo those systems are sandboxes.', Icon: Stamp },
] as const

const PRINCIPLES = [
  ['Every number comes from the engine', 'Gemini proposes and deterministic code computes. Model text can only show numbers the engine has filled in.'],
  ['Every requirement is quoted', 'A requirement counts only if its quote is found on the tender page and verified against the PDF.'],
  ['An engineer signs', 'Sign-off always waits for a person. The stamp records who signed, when, and the exact revision.'],
] as const

/** A small glass card lifts a hair on hover; not at all under "reduce motion" (the lift is a CSS transform, so the media query is the whole switch). */
const LIFT =
  'transition-[transform,box-shadow] duration-200 ease-out hover:-translate-y-0.5 hover:shadow-[0_14px_30px_-14px_rgb(30_58_138/0.4)] motion-reduce:transition-none motion-reduce:hover:translate-y-0'

export function Landing() {
  const reduce = useReducedMotion()
  const reveal = useReveal()
  const [hot, setHot] = useState<keyof typeof AREAS | null>(null)
  const recorded = useRecordedRun()
  return (
    <div id="top" className="blueprint relative flex min-h-dvh flex-col overflow-x-clip">
      <a
        href="#main"
        className="sr-only z-[80] rounded bg-foreground px-3 py-1.5 text-sm text-background focus:not-sr-only focus:fixed focus:left-3 focus:top-3"
      >
        Skip to content
      </a>
      {/* Decorative feeder traces in the side margins only — never across the text (M5) — drawn once,
          and static under reduced motion (MotionConfig alone does not stop a pathLength draw). */}
      {(['left', 'right'] as const).map((edge) => (
        <svg
          key={edge}
          aria-hidden
          viewBox="0 0 300 420"
          className={`pointer-events-none absolute top-32 hidden h-[420px] w-[300px] opacity-90 xl:block ${edge === 'left' ? 'left-6' : 'right-6 -scale-x-100'}`}
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

      <header className="sticky top-3 z-30 mx-auto w-[calc(100%-2rem)] max-w-5xl">
        <nav aria-label="Landing" className="glass-strong flex items-center gap-1 rounded-full py-1.5 pr-1.5 pl-4 text-sm">
          <a href="#top" className="mr-auto flex items-center gap-2 rounded font-semibold tracking-tight">
            <KirchhoffMark />
            Kirchhoff <span className="hidden font-normal text-slate-600 sm:inline">by Ordinal</span>
          </a>
          {[
            ['#how-it-works', 'How it works'],
            ['#features', 'What it does'],
            ['#trust', 'Why trust the numbers'],
          ].map(([href, label]) => (
            <a key={href} href={href} className="hidden rounded-full px-3 py-1.5 whitespace-nowrap text-slate-700 hover:bg-white/80 hover:text-foreground md:inline">
              {label}
            </a>
          ))}
          <Button asChild size="sm" className="ml-1 rounded-full">
            <Link to="/app">Open the demo</Link>
          </Button>
        </nav>
      </header>

      <main id="main" tabIndex={-1} className="relative z-10 mx-auto flex w-full max-w-5xl flex-1 flex-col items-center gap-24 px-6 pt-16 pb-16 focus:outline-none sm:pt-20">
        <section aria-label="Kirchhoff" className="flex w-full flex-col items-center gap-6 text-center">
          {/* One entrance sequence on load (spec motion rules: once, and none under "reduce motion"): each part follows the one before it. */}
          <motion.p {...reveal({ on: 'load' })} className="glass rounded-full px-3.5 py-1 text-xs font-medium text-slate-700">
            AI designs. Physics checks. An engineer signs.
          </motion.p>
          <motion.h1
            {...reveal({ on: 'load', delay: 0.08 })}
            className="max-w-3xl text-balance text-4xl font-semibold tracking-[-0.035em] text-foreground sm:text-5xl lg:text-6xl"
          >
            Weeks of senior-engineer design work, in one reviewed, signed session.
          </motion.h1>
          <motion.p {...reveal({ on: 'load', delay: 0.16 })} className="max-w-xl text-pretty text-base leading-relaxed text-slate-600">
            Gemini agents read the tender and design power and cooling for an AI data hall. A deterministic checker proves
            every number. The engineer decides and signs, and procurement and sales pick it up from there.
          </motion.p>
          <motion.div {...reveal({ on: 'load', delay: 0.24 })} className="mt-1 flex flex-col items-center gap-3">
            <Button asChild size="lg" className="shadow-[0_10px_24px_-10px_rgb(11_13_16/0.6)] ring-1 ring-white/25">
              <Link to="/app">Enter the demo workspace (no login)</Link>
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
            <p className="text-xs text-slate-600">No login. The demo companies, people and data are all invented.</p>
          </motion.div>

          {/* The product in the first viewport (UX-1 I2): a real capture of the shipped Hall A view, fetched first (N4). It only rises into place (no fade),
              so the image is painted from the first frame. */}
          {/* The width of the text column, as before, so the window sits between the side traces. The capture is taken at the width it is shown at, so its
              text is at full size and sharp, not a larger layout scaled down. */}
          <motion.figure {...reveal({ on: 'load', delay: 0.36, y: 28, fade: false })} className="relative mt-8 w-full">
            {/* A soft cooling-blue / power-amber glow under the frame, so the glass bezel has something to refract. */}
            <div aria-hidden className="pointer-events-none absolute inset-x-10 -inset-y-4 -z-10 rounded-[2rem] bg-gradient-to-r from-blue-500/30 via-indigo-400/20 to-amber-400/30 blur-2xl" />
            <div className="glass-strong rounded-2xl p-2">
              <div className="overflow-hidden rounded-xl border border-border bg-background">
                <div aria-hidden className="flex items-center gap-1.5 border-b border-border bg-gradient-to-b from-white to-slate-100 px-3 py-2">
                  <span className="size-2.5 rounded-full bg-red-400" />
                  <span className="size-2.5 rounded-full bg-amber-400" />
                  <span className="size-2.5 rounded-full bg-emerald-500" />
                </div>
                {/* Lossless at 2x (a lossy WebP blurred the small text): WebP first, 57% lighter, and the identical pixels as PNG for a browser without
                    WebP. A phone gets the 3D column only, captured where it is about a phone's width, because the whole workspace shrunk to 360 px
                    cannot be read. */}
                <div className="relative">
                  <picture>
                    <source media="(max-width: 639px)" type="image/webp" srcSet="/landing/hall-a-r2-phone.webp" />
                    <source media="(max-width: 639px)" srcSet="/landing/hall-a-r2-phone.png" />
                    <source type="image/webp" srcSet="/landing/hall-a-r2.webp" />
                    <img
                      src="/landing/hall-a-r2.png"
                      width={1672}
                      height={1045}
                      // Above the fold on desktop (N4): lazy-loading left a grey box at ~2.6 s.
                      loading="eager"
                      fetchPriority="high"
                      decoding="async"
                      alt="Hall A (sample) in Kirchhoff's 3D view: the hall boundary, and the signed revision with each fixed check called out as resolved. The wider picture also shows the agent lanes and the co-pilot's what-if chips."
                      className="block aspect-[16/10] h-auto w-full bg-muted max-sm:aspect-[99/116]"
                    />
                  </picture>
                  {/* Hover a legend card below and the part of the picture it describes lights up. Decorative: hidden from assistive technology, never takes
                      the pointer, and not on a phone (its crop is the 3D column only). The fade is a CSS transition, off under "reduce motion". */}
                  <div aria-hidden className="pointer-events-none absolute inset-0 max-sm:hidden">
                    {(Object.keys(AREAS) as (keyof typeof AREAS)[]).map((at) => (
                      <span
                        key={at}
                        data-highlight={at}
                        data-active={hot === at}
                        style={AREAS[at]}
                        className={`absolute rounded-md bg-[var(--brand-text)]/10 ring-2 ring-[var(--brand-text)] transition-opacity duration-200 motion-reduce:transition-none ${hot === at ? 'opacity-100' : 'opacity-0'}`}
                      />
                    ))}
                  </div>
                </div>
              </div>
            </div>
            <figcaption className="sr-only">Hall A (sample): the first revision’s failures, fixed and signed.</figcaption>
            <ul aria-label="What the screenshot shows" className="mt-5 grid gap-3 text-left text-sm sm:grid-cols-3">
              {SCREENSHOT_LEGEND.map(([t, d, at, Icon]) => (
                // The phone crop shows the 3D hall only, so the other two cards are for the wide picture.
                <li
                  key={t}
                  onMouseEnter={() => setHot(at)}
                  onMouseLeave={() => setHot(null)}
                  className={`glass flex items-start gap-3.5 rounded-xl p-4 ${LIFT}${t === '3D hall' ? '' : ' max-sm:hidden'}`}
                >
                  <WhereInShot at={at} />
                  <div>
                    <p className="flex items-center gap-1.5 font-semibold text-foreground">
                      <Icon aria-hidden className="size-4 shrink-0 text-[var(--brand-text)]" />
                      {t}
                    </p>
                    <p className="mt-1 text-xs leading-relaxed text-slate-700">{d}</p>
                  </div>
                </li>
              ))}
            </ul>
          </motion.figure>

          {/* A strong label over five equal glass tiles (two columns on a phone, five from sm up; the odd one out spans the phone's width). Every
              tile has the same icon, size and weight and sits in its own frosted glass, so there are no lines between them. */}
          <div className="mt-2 flex w-full flex-col items-center gap-4">
            <p className="text-center text-base font-semibold tracking-tight text-foreground">Built on Google Cloud</p>
            <ul aria-label="Built on" className="grid w-full grid-cols-2 gap-3 sm:grid-cols-5">
              {GOOGLE_STACK.map(([name, Icon]) => (
                <li
                  key={name}
                  className={`glass flex flex-col items-center justify-start gap-2 rounded-xl px-3 py-4 text-center text-sm font-semibold leading-tight text-slate-800 max-sm:last:col-span-2 ${LIFT}`}
                >
                  <Icon aria-hidden className="size-5 shrink-0 text-[var(--brand-text)]" />
                  {name}
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section id="features" aria-labelledby="features-h" className="w-full scroll-mt-24 text-left">
          <h2 id="features-h" className="max-w-2xl text-3xl font-semibold tracking-tight">
            What Kirchhoff does
          </h2>
          <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
            <div className="glass-strong flex flex-col justify-center gap-5 rounded-2xl p-6">
              <CheckGrid />
              <h3 className="text-xl font-semibold tracking-tight">Every number is checked by code, not by the model</h3>
              <p className="text-sm leading-relaxed text-slate-600">
                A deterministic rule pack tests each design against the clauses in the tender. Each finding cites its clause and shows its formula, and every fix is
                re-checked against every rule before it is offered.
              </p>
            </div>
            <ul aria-label="More of what it does" className="divide-y divide-[var(--glass-edge)]">
              {FEATURES.map(({ t, d, Icon }) => (
                <li key={t} className="flex gap-4 py-5 first:pt-0 last:pb-0">
                  <span aria-hidden className="grid size-9 shrink-0 place-items-center rounded-lg bg-white/80 text-[var(--brand-text)] ring-1 ring-[var(--glass-edge)]">
                    <Icon className="size-4.5" />
                  </span>
                  <div>
                    <h3 className="font-semibold text-foreground">{t}</h3>
                    <p className="mt-0.5 max-w-prose text-sm leading-relaxed text-slate-600">{d}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section id="how-it-works" aria-labelledby="how-h" className="w-full scroll-mt-24 text-left">
          <h2 id="how-h" className="max-w-2xl text-3xl font-semibold tracking-tight">
            How a design gets made
          </h2>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-slate-600">You stay in control at three gates: the plan, the options and the review.</p>
          <ol className="mt-8 grid grid-cols-1 gap-4 text-sm sm:grid-cols-3" aria-label="How it works">
            {STEPS.map(({ t, d, Icon, chip }, i) => (
              // The signal path from step to step is a short trace with a node across the gap; StepCard draws it just after its card lands.
              <StepCard key={t} index={i} last={i === STEPS.length - 1} className="glass relative rounded-xl p-5">
                <div className="flex items-center gap-2">
                  <span className={`grid h-6 min-w-8 place-items-center rounded-md px-1.5 font-mono text-xs font-semibold ${chip}`}>0{i + 1}</span>
                  <Icon aria-hidden className="size-4 text-slate-700" />
                </div>
                <p className="mt-3 font-semibold text-foreground">{t}</p>
                <p className="mt-1 text-xs leading-relaxed text-slate-600">{d}</p>
              </StepCard>
            ))}
          </ol>
        </section>

        <section id="trust" aria-labelledby="trust-h" className="w-full scroll-mt-24 text-left">
          <h2 id="trust-h" className="max-w-2xl text-3xl font-semibold tracking-tight">
            Why you can trust the numbers
          </h2>
          <div className="mt-8 grid gap-8 sm:grid-cols-3">
            {PRINCIPLES.map(([t, d]) => (
              <div key={t} className="border-t-2 border-foreground/80 pt-4">
                <h3 className="font-semibold text-foreground">{t}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-slate-600">{d}</p>
              </div>
            ))}
          </div>
        </section>

        <section aria-labelledby="cta-h" className="glass-strong flex w-full flex-col items-center gap-5 rounded-3xl px-6 py-12 text-center">
          <h2 id="cta-h" className="max-w-xl text-balance text-3xl font-semibold tracking-tight">
            See a signed design, or run one yourself
          </h2>
          <p className="max-w-md text-sm leading-relaxed text-slate-600">Open the signed Hall A, replay the recorded run, or start Hall B live. No login.</p>
          <div className="flex flex-wrap items-center justify-center gap-3">
            <Button asChild size="lg" className="shadow-[0_10px_24px_-10px_rgb(11_13_16/0.6)] ring-1 ring-white/25">
              <Link to="/app">Open the demo workspace</Link>
            </Button>
            <Button asChild variant="glass" size="lg">
              <Link to="/app/p/hall-b">
                <Zap aria-hidden /> Run Hall B live
              </Link>
            </Button>
            {recorded === true && (
              <Button asChild variant="glass" size="lg">
                <Link to="/app/p/hall-a?replay=1">
                  <CirclePlay aria-hidden /> Watch a recorded run
                </Link>
              </Button>
            )}
          </div>
        </section>
      </main>

      <footer className="relative z-10 flex flex-col items-center gap-1 p-6 text-center text-xs text-slate-600">
        <span>{FICTIONAL_TEXT}</span>
        <span>{ILLUSTRATIVE_TEXT}</span>
        <span className="mt-2">Kirchhoff by Ordinal, built for the Google Cloud AI Builder Cup 2026.</span>
      </footer>
    </div>
  )
}
