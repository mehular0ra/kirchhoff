import { CircleCheck, CircleX, Clock, Hand, LoaderCircle, Pause, Play, RotateCcw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { Num } from '@/components/Labels'
import { Button } from '@/components/ui/button'
import type { ReplayControls } from '@/data/replay'
import { useLeaseWatchdog } from '@/data/useLeaseWatchdog'
import { fmtElapsed } from '@/lib/format'
import { useServices } from '@/services/services'
import type { ReplayState } from '@/store/bundles'
import { useWorkspace } from './WorkspaceContext'

const SPEEDS = [1, 4, 8, 16]

function ReplayBar({ replay, controls }: { replay: ReplayState; controls: ReplayControls | null }) {
  return (
    <div className="flex items-center gap-3 border-b bg-zinc-950/60 px-3 py-1.5 text-xs">
      <Button
        variant="ghost"
        size="icon-xs"
        aria-label={replay.playing ? 'Pause replay' : 'Play replay'}
        onClick={() => (replay.playing ? controls?.pause() : controls?.play())}
      >
        {replay.playing ? <Pause aria-hidden /> : <Play aria-hidden />}
      </Button>
      <span className="inline-flex items-center gap-1 text-zinc-300">
        <Clock aria-hidden className="size-3.5" /> Elapsed (recorded) <Num>{fmtElapsed(replay.elapsedS)}</Num>
      </span>
      <span className="text-zinc-500">Time-compressed replay of a recorded run</span>
      <span className="text-zinc-500" data-dev>
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
  useLeaseWatchdog(run, api.resume)
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now() / 1000), 1000)
    return () => clearInterval(id)
  }, [])
  if (!run) return <div className="border-b px-3 py-1.5 text-xs text-zinc-400">Connecting to your run…</div>
  const end = run.finished_at ?? now
  const st =
    run.status === 'running'
      ? { icon: LoaderCircle, text: `Running · phase ${run.phase ?? ''}`, cls: 'text-sky-300', spin: true }
      : run.status === 'at_gate'
        ? { icon: Hand, text: `Waiting for you · ${run.gate} gate`, cls: 'text-amber-300', spin: false }
        : run.status === 'done'
          ? { icon: CircleCheck, text: 'Run complete', cls: 'text-emerald-400', spin: false }
          : { icon: CircleX, text: run.status === 'expired' ? 'Expired at a gate after 24 h' : 'Run failed', cls: 'text-rose-400', spin: false }
  const Icon = st.icon
  return (
    <div className="flex items-center gap-3 border-b bg-zinc-950/60 px-3 py-1.5 text-xs" aria-live="polite">
      <span className={`inline-flex items-center gap-1 ${st.cls}`}>
        <Icon aria-hidden className={`size-3.5 ${st.spin ? 'animate-spin motion-reduce:animate-none' : ''}`} />
        {st.text}
      </span>
      <span className="inline-flex items-center gap-1 text-zinc-400">
        <Clock aria-hidden className="size-3.5" /> Elapsed <Num>{fmtElapsed(end - run.started_at)}</Num>
      </span>
      <span className="text-zinc-500">Autonomy: {run.autonomy === 'ask' ? 'Ask' : 'Auto'}</span>
      {run.status === 'failed' && (
        <Button size="xs" variant="outline" className="ml-auto" onClick={() => void api.resume(run.id).catch(() => undefined)}>
          <RotateCcw aria-hidden /> Resume
        </Button>
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
