import { motion } from 'motion/react'
import { ArrowRight, CirclePlay, Zap } from 'lucide-react'
import { Link } from 'react-router'
import { Button } from '@/components/ui/button'
import { FICTIONAL_TEXT } from '@/components/Labels'

// Effects live only here (spec §12). The background traces are decorative and static under reduced motion.
export function Landing() {
  return (
    <div className="relative flex min-h-dvh flex-col overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(56,189,248,0.14),transparent_55%),radial-gradient(ellipse_at_bottom_right,rgba(251,191,36,0.10),transparent_50%)]"
      />
      <svg aria-hidden className="pointer-events-none absolute inset-x-0 top-24 mx-auto h-64 w-[56rem] max-w-full opacity-40">
        {[0, 1, 2, 3].map((i) => (
          <motion.path
            key={i}
            d={`M ${40 + i * 220} 10 V 90 H ${150 + i * 200} V 240`}
            fill="none"
            stroke={i % 2 ? '#60a5fa' : '#fbbf24'}
            strokeWidth={1.5}
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 2.2, delay: i * 0.25, ease: 'easeInOut' }}
          />
        ))}
      </svg>
      <main className="relative z-10 mx-auto flex max-w-3xl flex-1 flex-col items-center justify-center gap-6 px-6 text-center">
        <p className="rounded-full border border-zinc-700 px-3 py-1 text-xs text-zinc-400">
          AI designs. Physics checks. An engineer signs.
        </p>
        <h1 className="text-4xl font-semibold tracking-tight text-zinc-50 sm:text-5xl">
          Weeks of senior-engineer design work, in one reviewed, signed session.
        </h1>
        <p className="max-w-xl text-base text-zinc-400">
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
          <Button asChild variant="ghost" size="sm">
            <Link to="/app/p/hall-a?replay=1">
              <CirclePlay aria-hidden /> Replay a recorded run
            </Link>
          </Button>
        </div>
        <ol className="mt-6 grid w-full grid-cols-1 gap-3 text-left text-sm sm:grid-cols-3" aria-label="How it works">
          {[
            ['Agents design', 'Gemini agents read the tender with verified citations and design power and cooling together.'],
            ['Physics checks', 'A deterministic rule pack checks every number; the AI cannot mark its own homework.'],
            ['An engineer signs', 'You decide at each gate, sign the revision, and PRs and the CRM update follow.'],
          ].map(([t, d], i) => (
            <li key={t} className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-3">
              <span className="font-mono text-xs text-zinc-500">0{i + 1}</span>
              <p className="font-medium text-zinc-100">{t}</p>
              <p className="text-xs text-zinc-400">{d}</p>
            </li>
          ))}
        </ol>
      </main>
      <footer className="relative z-10 p-4 text-center text-xs text-zinc-500">{FICTIONAL_TEXT}</footer>
    </div>
  )
}
