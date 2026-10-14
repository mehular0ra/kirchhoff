// Live triage (spec §20): only on the Hall B email. While it runs, a two-stage progress line (motion off under
// prefers-reduced-motion); if the API is down or slow, the recorded triage stays on screen with a note.
import { LoaderCircle, Zap } from 'lucide-react'
import { useEffect, useState } from 'react'
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
  useEffect(() => {
    if (state !== 'running') return
    const t = setTimeout(() => setStage(1), 3000)
    return () => clearTimeout(t)
  }, [state])
  if (!email.live_triage) return null
  const run = async () => {
    setState('running')
    setStage(0)
    try {
      applyTriage(email.id, await api.triage(email.id))
      setState('done')
    } catch (e) {
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
        <p role="status" className="text-xs text-emerald-300">
          Live triage complete.
        </p>
      )}
      {state === 'failed' && (
        <p role="status" className="text-xs text-amber-200">
          Live triage unavailable: {note} {email.triage ? 'The recorded triage stays on screen.' : ''}
        </p>
      )}
    </div>
  )
}
