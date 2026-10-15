// Live triage (spec §20): only on the Hall B email. While it runs, a two-stage progress line (motion off under
// prefers-reduced-motion); if the API is down or slow, the recorded triage stays on screen with a note.
import { CircleCheck, LoaderCircle, TriangleAlert, Zap } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import type { InboxEmail } from '@/lib/types'
import { describeApiError } from '@/services/apiClient'
import { useServices } from '@/services/services'
import { applyTriage } from './useInbox'

const PROGRESS = ['Reading the email and its attachments…', 'Verifying quotes, checking fit and supply…']

export function TriageButton({ email }: { email: InboxEmail }) {
  const { api } = useServices()
  const [state, setState] = useState<'idle' | 'running' | 'done' | 'failed'>('idle')
  const [stage, setStage] = useState(0)
  const [note, setNote] = useState('')
  const mounted = useRef(true)  // a late answer after the user left the page is dropped, not applied
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])
  useEffect(() => {
    if (state !== 'running') return
    // A fixed 3 s swap, not a real signal: the API does not stream progress. It only keeps the line from looking stuck.
    const t = setTimeout(() => setStage(1), 3000)
    return () => clearTimeout(t)
  }, [state])
  if (!email.live_triage) return null
  const run = async () => {
    setState('running')
    setStage(0)
    try {
      const result = await api.triage(email.id)
      if (!mounted.current) return
      applyTriage(email.id, result)
      setState('done')
    } catch (e) {
      if (!mounted.current) return
      setNote(describeApiError(e))
      setState('failed')
    }
  }
  return (
    <div className="flex flex-col gap-1.5">
      <Button variant="outline" onClick={run} disabled={state === 'running'} className="self-start">
        <Zap aria-hidden />
        {state === 'done' ? 'Triage again' : 'Triage live'}
      </Button>
      {state === 'running' && (
        <p role="status" className="flex items-center gap-1.5 text-xs text-sky-200">
          <LoaderCircle aria-hidden className="size-3.5 animate-spin motion-reduce:animate-none" />
          {PROGRESS[stage]}
        </p>
      )}
      {state === 'done' && (
        <p role="status" className="flex items-center gap-1.5 text-xs text-emerald-300">
          <CircleCheck aria-hidden className="size-3.5 shrink-0" />
          Live triage complete.
        </p>
      )}
      {state === 'failed' && (
        <p role="status" className="flex items-start gap-1.5 text-xs text-amber-200">
          <TriangleAlert aria-hidden className="mt-0.5 size-3.5 shrink-0" />
          <span>
            Live triage unavailable: {note} {email.triage ? 'The recorded triage stays on screen.' : ''}
          </span>
        </p>
      )}
    </div>
  )
}
