import { useEffect, useState } from 'react'
import type { RunEvent } from '../contracts/generated'

type Props = {
  start: () => Promise<string>
  subscribe: (runId: string, cb: (events: RunEvent[]) => void) => () => void
}

export function HelloRun({ start, subscribe }: Props) {
  const [runId, setRunId] = useState<string | null>(null)
  const [events, setEvents] = useState<RunEvent[]>([])

  useEffect(() => {
    if (!runId) return
    return subscribe(runId, (evs) => setEvents([...evs].sort((a, b) => a.seq - b.seq)))
  }, [runId, subscribe])

  return (
    <main style={{ fontFamily: 'Inter, system-ui', padding: 24, color: '#e5e7eb', background: '#0b0d10', minHeight: '100vh' }}>
      <h1>Kirchhoff — hello run</h1>
      <button onClick={async () => setRunId(await start())}>Start run</button>
      {runId && <p>Run {runId}</p>}
      <ol>{events.map((e) => <li key={e.seq}>{e.seq}. {e.title} <small>{e.detail}</small></li>)}</ol>
    </main>
  )
}
