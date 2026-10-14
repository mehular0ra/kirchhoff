// Spec §6.2: if the running phase's lease heartbeat is older than 60 s, the client calls
// POST /api/runs/{rid}/resume (at most once per minute).
import { useEffect, useRef } from 'react'
import type { RunRecord } from '@/lib/types'

export function leaseIsStale(run: RunRecord | null, nowS: number, maxAgeS = 60): boolean {
  if (!run || run.status !== 'running' || !run.lease) return false
  const hb = (run.lease.heartbeat_at ?? run.lease.heartbeatAt) as number | undefined
  return typeof hb === 'number' && nowS - hb > maxAgeS
}

export function useLeaseWatchdog(
  run: RunRecord | null,
  resume: (runId: string) => Promise<unknown>,
  opts: { intervalMs?: number; now?: () => number } = {},
): void {
  const runRef = useRef(run)
  const lastCall = useRef(0)
  runRef.current = run
  const intervalMs = opts.intervalMs ?? 15_000
  const now = opts.now ?? (() => Date.now() / 1000)

  useEffect(() => {
    const id = setInterval(() => {
      const r = runRef.current
      const t = now()
      if (r && leaseIsStale(r, t) && t - lastCall.current >= 60) {
        lastCall.current = t
        resume(r.id).catch(() => {
          // resume is best-effort; the next tick retries after 60 s
        })
      }
    }, intervalMs)
    return () => clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs, resume])
}
