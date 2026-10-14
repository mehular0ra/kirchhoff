import { CirclePlay, CircleX, FileText, LoaderCircle, Upload, Zap } from 'lucide-react'
import { useState, type DragEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { Button } from '@/components/ui/button'
import { writeJson } from '@/lib/storage'
import type { Project } from '@/lib/types'
import { describeApiError } from '@/services/apiClient'
import { useServices } from '@/services/services'
import { useUi } from '@/store/ui'
import { AutonomySwitch } from './gates/AutonomySwitch'

export const LIVE_TARGET = 'hall-b'

const INPUTS = [
  { name: 'Tender (PDF)', file: 'tender-hall-a.pdf' },
  { name: 'Hall drawing (DXF)', file: 'hall-a.dxf' },
  { name: 'Hall drawing plot (PDF)', file: 'hall-a-plan.pdf' },
  { name: 'Catalogue + ERP data', file: 'sandbox (simulated)' },
]

/** Hall B "Run it live" (spec §11): starts P1 in the visitor's own workspace. */
export function StartRunPanel({ project, onStarted }: { project: Project | null; onStarted?: () => void }) {
  const { api } = useServices()
  const navigate = useNavigate()
  const autonomy = useUi((s) => s.autonomy)
  const setAutonomy = useUi((s) => s.setAutonomy)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [over, setOver] = useState(false)

  const start = async () => {
    setBusy(true)
    setError(null)
    try {
      await api.ensureWorkspace()
      const { run_id } = await api.startRun(LIVE_TARGET, autonomy)
      writeJson(`lastRun.${LIVE_TARGET}`, run_id)
      onStarted?.()
      navigate(`/app/p/${LIVE_TARGET}?run=${run_id}`)
    } catch (e) {
      setError(describeApiError(e)) // global_cap / visitor_rate_limit (429) offer the replay link below
    } finally {
      setBusy(false)
    }
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setOver(false)
    void start()
  }

  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col justify-center gap-5 p-6">
      <div>
        <h1 className="text-lg font-semibold">{project?.name ?? 'Deccan AI Campus · Hall B'}</h1>
        <p className="text-sm text-zinc-400">
          Hall B uses the same tender, drawing and catalogue as Hall A. Kirchhoff's agents design it in your own
          workspace; you decide at each gate and sign at the end.
        </p>
      </div>
      <ul className="grid grid-cols-2 gap-2 text-xs">
        {INPUTS.map((i) => (
          <li key={i.name} className="flex items-center gap-2 rounded border bg-card px-2 py-1.5">
            <FileText aria-hidden className="size-4 text-zinc-500" />
            <span className="text-zinc-200">{i.name}</span>
            <span className="ml-auto truncate font-mono text-zinc-500">{i.file}</span>
          </li>
        ))}
      </ul>
      <div
        role="region"
        aria-label="Drop the tender PDF and drawing to start"
        onDragOver={(e) => {
          e.preventDefault()
          setOver(true)
        }}
        onDragLeave={() => setOver(false)}
        onDrop={onDrop}
        className={`flex flex-col items-center gap-1 rounded-lg border border-dashed p-6 text-center text-sm ${over ? 'border-sky-400 bg-sky-500/10' : 'border-zinc-700'}`}
      >
        <Upload aria-hidden className="size-5 text-zinc-400" />
        Drop the tender PDF and drawing here to start
        <span className="text-xs text-zinc-500">The demo always uses the Hall B package above; dropped files are not uploaded.</span>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <AutonomySwitch value={autonomy} onChange={setAutonomy} />
        <Button onClick={() => void start()} disabled={busy}>
          {busy ? <LoaderCircle aria-hidden className="animate-spin" /> : <Zap aria-hidden />} Start live run
        </Button>
        <Button asChild variant="ghost">
          <Link to="/app/p/hall-a?replay=1">
            <CirclePlay aria-hidden /> Replay a recorded run
          </Link>
        </Button>
      </div>
      {error && (
        <p role="alert" className="flex items-center gap-1.5 rounded border border-amber-500/40 bg-amber-500/10 p-2 text-sm text-amber-200">
          <CircleX aria-hidden className="size-4 shrink-0" /> {error}
        </p>
      )}
    </div>
  )
}
