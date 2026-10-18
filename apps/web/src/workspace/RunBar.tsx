import { CircleCheck, CircleX, Clock, Hand, Info, LoaderCircle, Pause, Play, RotateCcw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { Num } from '@/components/Labels'
import { Button } from '@/components/ui/button'
import type { ReplayControls } from '@/data/replay'
import { useRecordedRun } from '@/data/useRecordedRun'
import { useLeaseWatchdog } from '@/data/useLeaseWatchdog'
import { fmtElapsed } from '@/lib/format'
import { useServices } from '@/services/services'
import type { ReplayState } from '@/store/bundles'
import { useWorkspace } from './WorkspaceContext'

const SPEEDS = [1, 4, 8, 16]
/**
 * Waiting for a live run's record (residual of the final re-review): the Firestore listener stays live the whole
 * time, so a run that appears late (a cold Cloud Run start) still shows. After the first stage the bar says it is
 * still waiting and offers the ways out; only after the second does it conclude the run is not in this workspace.
 */
const RUN_WAIT_MS = [10_000, 60_000] as const
/** Run phases (spec §5) in words, instead of the raw "phase p2" (M19). */
const PHASE_LABEL: Record<string, string> = {
  p1: 'reading the tender and planning',
  p2: 'placing racks and weighing options',
  p3: 'routing, checking and fixing',
  p4: 'handing off to ERP and CRM',
}

function ReplayBar({ replay, controls }: { replay: ReplayState; controls: ReplayControls | null }) {
  if (replay.total === 0) {
    // Nothing to replay yet (D10): say so instead of "event 0/0" with working speed controls.
    return (
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b bg-surface px-3 py-1.5 text-xs text-zinc-700">
        <span className="inline-flex items-center gap-1.5">
          <Info aria-hidden className="size-3.5 shrink-0 text-muted-foreground" /> This demo snapshot has no recorded run to replay yet; it shows the signed result.
        </span>
        <Link to="/app/p/hall-b" className="underline underline-offset-2">
          Run Hall B live to watch the agents work
        </Link>
      </div>
    )
  }
  return (
    <div className="flex items-center gap-3 border-b bg-surface px-3 py-1.5 text-xs">
      <Button
        variant="ghost"
        size="icon-xs"
        aria-label={replay.playing ? 'Pause replay' : 'Play replay'}
        onClick={() => (replay.playing ? controls?.pause() : controls?.play())}
      >
        {replay.playing ? <Pause aria-hidden /> : <Play aria-hidden />}
      </Button>
      <span className="inline-flex items-center gap-1 text-zinc-700">
        <Clock aria-hidden className="size-3.5" /> Elapsed (recorded) <Num>{fmtElapsed(replay.elapsedS)}</Num>
      </span>
      <span className="text-muted-foreground">Time-compressed replay of a recorded run</span>
      <span className="text-muted-foreground" data-dev>
        event <Num>{replay.cursor}</Num>/<Num>{replay.total}</Num>
      </span>
      <span className="ml-auto flex items-center gap-1" data-dev>
        {SPEEDS.map((s) => (
          <Button key={s} size="xs" variant={replay.speed === s ? 'secondary' : 'ghost'} onClick={() => controls?.setSpeed(s)}>
            {s}×
          </Button>
        ))}
        <Button size="xs" variant="ghost" onClick={() => controls?.seek(replay.total)}>
          Skip to end
        </Button>
      </span>
    </div>
  )
}

function LiveBar() {
  const { run } = useWorkspace()
  const { api } = useServices()
  const [now, setNow] = useState(() => Date.now() / 1000)
  const [stage, setStage] = useState<0 | 1 | 2>(0) // connecting → still waiting → not in this workspace
  const recorded = useRecordedRun()
  useLeaseWatchdog(run, api.resume)
  useEffect(() => {
    if (run) return
    const t1 = setTimeout(() => setStage(1), RUN_WAIT_MS[0])
    const t2 = setTimeout(() => setStage(2), RUN_WAIT_MS[1])
    return () => {
      clearTimeout(t1)
      clearTimeout(t2)
    }
  }, [run])
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now() / 1000), 1000)
    return () => clearInterval(id)
  }, [])
  if (!run) {
    const watchRecorded = recorded === true && (
      <Link to="/app/p/hall-a?replay=1" className="underline underline-offset-2">
        Watch the recorded run
      </Link>
    )
    if (stage === 0)
      return (
        <div role="status" className="flex items-center gap-1.5 border-b px-3 py-1.5 text-xs text-muted-foreground">
          <LoaderCircle aria-hidden className="size-3.5 animate-spin motion-reduce:animate-none" /> Connecting to your run…
        </div>
      )
    if (stage === 1)
      return (
        <div role="status" className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b px-3 py-1.5 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1.5">
            <LoaderCircle aria-hidden className="size-3.5 animate-spin motion-reduce:animate-none" /> Still waiting for your run to start; a
            cold start can take up to a minute.
          </span>
          {watchRecorded}
        </div>
      )
    // M2: a stale ?run= link, a reset workspace or another visitor's run never appears.
    return (
      <div role="alert" className="flex flex-wrap items-center gap-3 border-b bg-amber-500/10 px-3 py-1.5 text-xs text-amber-800">
        <span className="inline-flex items-center gap-1.5">
          <CircleX aria-hidden className="size-3.5" /> This run is not in your workspace: it may have been reset, or belong to another visitor.
        </span>
        <Link to="/app/p/hall-b" className="underline underline-offset-2">
          Start a new run
        </Link>
        {watchRecorded}
      </div>
    )
  }
  const end = run.finished_at ?? now
  const st =
    run.status === 'running'
      ? { icon: LoaderCircle, text: `Running · ${PHASE_LABEL[run.phase ?? ''] ?? 'starting'}`, cls: 'text-blue-700', spin: true }
      : run.status === 'at_gate'
        ? { icon: Hand, text: `Waiting for you · ${run.gate} gate`, cls: 'text-amber-700', spin: false }
        : run.status === 'done'
          ? { icon: CircleCheck, text: 'Run complete', cls: 'text-emerald-700', spin: false }
          : { icon: CircleX, text: run.status === 'expired' ? 'Expired at a gate after 24 h' : 'Run failed', cls: 'text-rose-700', spin: false }
  const Icon = st.icon
  return (
    <div className="flex items-center gap-3 border-b bg-surface px-3 py-1.5 text-xs" aria-live="polite">
      <span className={`inline-flex items-center gap-1 ${st.cls}`}>
        <Icon aria-hidden className={`size-3.5 ${st.spin ? 'animate-spin motion-reduce:animate-none' : ''}`} />
        {st.text}
      </span>
      <span className="inline-flex items-center gap-1 text-muted-foreground">
        <Clock aria-hidden className="size-3.5" /> Elapsed <Num>{fmtElapsed(end - run.started_at)}</Num>
      </span>
      <span className="text-muted-foreground">Autonomy: {run.autonomy === 'ask' ? 'Ask' : 'Auto'}</span>
      {run.status === 'done' && (
        <>
          {/* The agents run once per run, in order; what-ifs below only check the design (spec §6.5). Redesigning means a new run. */}
          <span className="text-muted-foreground">What-ifs only re-check this design; they do not redesign it.</span>
          <Button asChild size="xs" variant="outline" className="ml-auto">
            <Link to="/app/p/hall-b">
              <RotateCcw aria-hidden /> Run Hall B again
            </Link>
          </Button>
        </>
      )}
      {run.status === 'failed' && (
        <>
          <Button size="xs" variant="outline" className="ml-auto" onClick={() => void api.resume(run.id).catch(() => undefined)}>
            <RotateCcw aria-hidden /> Resume
          </Button>
          <Button asChild size="xs" variant="outline">
            <Link to="/app/p/hall-b">Start a new run</Link>
          </Button>
        </>
      )}
      {run.status === 'expired' && (
        <Button asChild size="xs" variant="outline" className="ml-auto">
          <Link to="/app/p/hall-b">Start a new run</Link>
        </Button>
      )}
    </div>
  )
}

export function RunBar({ replay, controls }: { replay?: ReplayState; controls: ReplayControls | null }) {
  const { source } = useWorkspace()
  if (source === 'replay' && replay) return <ReplayBar replay={replay} controls={controls} />
  if (source === 'live') return <LiveBar />
  return null
}
