import { motion, useReducedMotion } from 'motion/react'
import { Bot, CirclePlay, FileSearch, Layers, MessageCircleQuestion, PenLine, ShieldCheck, Stamp, Truck, Zap } from 'lucide-react'
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

// The three steps are a real sequence (the three gates), so they are numbered; each has its own colour and an icon, never colour alone.
const STEPS = [
  { t: 'Agents design', d: 'Gemini agents read the tender with verified citations and design power and cooling together.', Icon: Bot, chip: 'bg-blue-600 text-white' },
  { t: 'Physics checks', d: 'A deterministic rule pack checks every number; the AI cannot mark its own homework.', Icon: ShieldCheck, chip: 'bg-amber-400 text-zinc-950' },
  { t: 'An engineer signs', d: 'You decide at each gate, sign the revision, and PRs and the CRM update follow.', Icon: PenLine, chip: 'bg-emerald-700 text-white' },
] as const

const SCREENSHOT_LEGEND = [
  ['Agent lanes', 'Each agent’s status, with the quotes it verified against the tender.'],
  ['3D hall', 'Every finding drawn where it happens, with the clause that raised it.'],
  ['Co-pilot', 'Ask why a check failed, or what if a rack load or a limit changes.'],
] as const

const GOOGLE_STACK = ['Gemini on Vertex AI', 'Agent Development Kit', 'Cloud Run', 'Firestore', 'Firebase'] as const

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

/** A picture of what the checker does, not data: a grid of checks where nearly all pass and two are flagged. Decorative (aria-hidden). */
function CheckGrid() {
  const flagged = new Set([17, 38])
  return (
    <div aria-hidden className="grid grid-cols-12 gap-1.5">
      {Array.from({ length: 60 }, (_, i) => (
        <span key={i} className={`aspect-square rounded-[5px] ${flagged.has(i) ? 'bg-rose-500 ring-2 ring-rose-200' : 'bg-emerald-500/75'}`} />
      ))}
    </div>
  )
}

export function Landing() {
  const reduce = useReducedMotion()
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
          <p className="glass rounded-full px-3.5 py-1 text-xs font-medium text-slate-700">AI designs. Physics checks. An engineer signs.</p>
          <h1 className="max-w-3xl text-balance text-4xl font-semibold tracking-[-0.035em] text-foreground sm:text-5xl lg:text-6xl">
            Weeks of senior-engineer design work, in one reviewed, signed session.
          </h1>
          <p className="max-w-xl text-pretty text-base leading-relaxed text-slate-600">
            Gemini agents read the tender and design power and cooling for an AI data hall. A deterministic checker proves
            every number. The engineer decides and signs, and procurement and sales pick it up from there.
          </p>
          <div className="mt-1 flex flex-col items-center gap-3">
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
          </div>

          {/* The product in the first viewport (UX-1 I2): a real capture of the shipped Hall A view, fetched first (N4). */}
          <figure className="relative mt-8 w-full">
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
            <figcaption className="sr-only">Hall A (sample): the first revision’s failures, fixed and signed.</figcaption>
            <ul aria-label="What the screenshot shows" className="mt-5 grid gap-3 text-left text-sm sm:grid-cols-3">
              {SCREENSHOT_LEGEND.map(([t, d]) => (
                <li key={t} className="border-l-2 border-[var(--glass-edge)] pl-3">
                  <p className="font-semibold text-foreground">{t}</p>
                  <p className="text-xs leading-relaxed text-slate-600">{d}</p>
                </li>
              ))}
            </ul>
          </figure>

          <div className="mt-2 flex flex-col items-center gap-3">
            <p className="text-xs text-slate-600">Built on Google Cloud</p>
            <ul aria-label="Built on" className="flex flex-wrap items-center justify-center gap-2 text-xs font-medium text-slate-700">
              {GOOGLE_STACK.map((s) => (
                <li key={s} className="glass rounded-full px-3 py-1">
                  {s}
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
              <li key={t} className="glass relative rounded-xl p-5">
                <div className="flex items-center gap-2">
                  <span className={`grid h-6 min-w-8 place-items-center rounded-md px-1.5 font-mono text-xs font-semibold ${chip}`}>0{i + 1}</span>
                  <Icon aria-hidden className="size-4 text-slate-700" />
                </div>
                <p className="mt-3 font-semibold text-foreground">{t}</p>
                <p className="mt-1 text-xs leading-relaxed text-slate-600">{d}</p>
                {/* The signal path from step to step: a short trace with a node across the gap (sm and up, where the cards sit in a row). */}
                {i < STEPS.length - 1 && (
                  <span aria-hidden className="absolute top-1/2 -right-4 hidden h-0.5 w-4 -translate-y-1/2 bg-[var(--trace-blue)] sm:block">
                    <span className="absolute top-1/2 -right-0.5 size-2 -translate-y-1/2 rounded-full border-2 border-white bg-[var(--trace-blue)]" />
                  </span>
                )}
              </li>
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
