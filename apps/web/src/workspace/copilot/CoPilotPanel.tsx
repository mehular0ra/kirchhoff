import { Info, LoaderCircle, Mic, MicOff, Send } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { Revision, WhatIfResult } from '@/lib/types'
import { completeItem } from '@/onboarding/checklist/checklistStore'
import type { VoiceResponse } from '@/services/apiClient'
import { useServices, type LiveVoiceCall } from '@/services/services'
import { canvasesFor } from '@/lib/model'
import { revisionById, revisionLabel, revisionRef } from '@/lib/select'
import { useUi } from '@/store/ui'
import { PlanGate } from '../gates/PlanGate'
import { RequirementsPanel } from '../RequirementsPanel'
import { useWorkspace } from '../WorkspaceContext'
import { INTENT_HELP, parseIntent } from './intent'
import { executeTool, type ToolContext } from './tools'
import { useWhatIf } from './useWhatIf'
import { canRecord, speak } from './voice/pushToTalk'
import { useVoice } from './voice/useVoice'
import { WhatIfPanel } from './WhatIfPanel'

interface LogEntry {
  id: number
  who: 'you' | 'co-pilot'
  via: 'typed' | 'voice'
  text: string
}

export function CoPilotPanel() {
  const view = useWorkspace()
  const { api } = useServices()
  // What-ifs (typed, Live and push-to-talk) run on the head revision unless one was picked in the revision bar (#37).
  const { run: runWhatIf, show: showWhatIf, revRef: whatIfRef } = useWhatIf()
  const focusUi = useUi((s) => s.focus)
  // Co-pilot "show H-Z2" switches to a canvas that draws the element (I5).
  const focus = useCallback(
    (id: string) => {
      const drawnOn = canvasesFor(view.model, id)
      focusUi(id, drawnOn)
      return drawnOn.length > 0
    },
    [focusUi, view.model],
  )
  const openFinding = useUi((s) => s.openFinding)
  const setViewRev = useUi((s) => s.setViewRev)
  const setWhatIf = useUi((s) => s.setWhatIf)
  const [text, setText] = useState('')
  const [log, setLog] = useState<LogEntry[]>([])
  const seq = useRef(0)
  const ctx: ToolContext = { view, api, runWhatIf, focus, openFinding, setViewRev }
  const ctxRef = useRef(ctx)
  useEffect(() => {
    ctxRef.current = { view, api, runWhatIf, focus, openFinding, setViewRev }
  }, [view, api, runWhatIf, focus, openFinding, setViewRev])

  const add = (who: LogEntry['who'], via: LogEntry['via'], t: string) =>
    setLog((l) => [...l.slice(-7), { id: ++seq.current, who, via, text: t }])

  const ask = async (q: string) => {
    add('you', 'typed', q)
    completeItem('ask_copilot')
    const intent = parseIntent(q)
    if (!intent) {
      add('co-pilot', 'typed', INTENT_HELP)
      return
    }
    const args =
      intent.tool === 'what_if'
        ? { param: intent.param, value: intent.value }
        : intent.tool === 'explain_finding'
          ? { element_id: intent.element, rule_id: intent.rule }
          : { element_id: intent.element }
    const out = await executeTool(intent.tool, args, ctxRef.current)
    add('co-pilot', 'typed', out.summary)
  }

  const onToolCall = async (call: LiveVoiceCall) => {
    completeItem('ask_copilot')
    add('you', 'voice', `(voice) ${call.name.replace('_', ' ')}`)
    const out = await executeTool(call.name, call.args, ctxRef.current)
    add('co-pilot', 'voice', out.summary)
    return out.data
  }

  const onPushToTalk = (res: VoiceResponse, sentRef: string) => {
    completeItem('ask_copilot')
    add('you', 'voice', res.transcript)
    // The revision /api/voice answered on (#37): the head, unless one was picked in the revision bar.
    const askedOn = view.bundle.revisions.find((r) => revisionRef(view.bundle, r.id, view.source) === sentRef) ?? null
    let whatIfOn: Revision | null = null
    for (const t of res.tool_results) {
      if (t.name === 'what_if' && Array.isArray((t.result as Partial<WhatIfResult>).impact_chain)) {
        const w = { result: t.result as unknown as WhatIfResult, origin: 'engine' as const }
        if (askedOn) showWhatIf(askedOn, w)
        else setWhatIf(w)
        whatIfOn = askedOn
      }
      if (t.name === 'focus_element') focus(String(t.args.element_id ?? t.result.element_id ?? ''))
      if (t.name === 'explain_finding' && t.args.finding_id) {
        // D1, as typed and Live answers do (tools.ts): when the answer cites an earlier revision where the
        // check failed (`result.revision`, set by /api/voice only then), switch to it before opening the finding.
        // An automatic switch, not a revision-bar pick: later what-ifs stay on the head (#37).
        const cited = typeof t.result.revision === 'string' ? revisionById(view.bundle, t.result.revision) : null
        if (cited) setViewRev(cited.id, { source: 'auto' })
        openFinding(String(t.args.finding_id))
      }
    }
    // A what-if answer names the revision it ran on, like the typed one: "On r2 (signed): …".
    const answer = whatIfOn ? `On ${revisionLabel(whatIfOn)}: ${res.answer}` : res.answer
    add('co-pilot', 'voice', answer)
    speak(answer)
  }

  const voice = useVoice({ revisionRef: whatIfRef, onToolCall, onPushToTalk })
  const pttMode = voice.mode === 'ptt' || voice.mode === 'recording' || voice.mode === 'thinking'
  const micAvailable = canRecord()

  return (
    <div className="flex flex-col">
      <section aria-label="Ask the co-pilot" className="flex flex-col gap-2 border-b p-3">
        <h3 className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-zinc-400">
          <span aria-hidden className="size-2 rounded-full bg-[linear-gradient(135deg,#e879f9,#38bdf8)]" /> Co-pilot
        </h3>
        <form
          className="flex gap-1.5"
          onSubmit={(e) => {
            e.preventDefault()
            if (text.trim()) void ask(text.trim())
            setText('')
          }}
        >
          <Input
            aria-label="Ask the co-pilot"
            placeholder="Ask why, or “what if…”"
            aria-describedby="copilot-hint"
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="h-8 text-xs"
          />
          <Button size="icon-sm" type="submit" aria-label="Send">
            <Send aria-hidden />
          </Button>
        </form>
        {/* The examples in full (N1): too long for the input's placeholder at this width, so they get their own line. */}
        <p id="copilot-hint" className="-mt-1 text-[11px] text-zinc-400">
          Try “why FA-01” or “what if racks go to 200 kW”
        </p>
        {micAvailable ? (
          <div className="flex flex-wrap items-center gap-2">
            {voice.mode === 'off' && (
              <Button size="xs" variant="outline" onClick={() => void voice.startLive()}>
                <Mic aria-hidden /> Start voice
              </Button>
            )}
            {voice.mode === 'connecting' && (
              <span className="inline-flex items-center gap-1 text-xs text-zinc-300">
                <LoaderCircle aria-hidden className="size-3.5 animate-spin motion-reduce:animate-none" /> Connecting to Gemini Live…
              </span>
            )}
            {voice.mode === 'live' && (
              <>
                <span className="inline-flex items-center gap-1 text-xs text-fuchsia-200">
                  <Mic aria-hidden className="size-3.5 animate-pulse motion-reduce:animate-none" /> Listening (Gemini Live)
                </span>
                <Button size="xs" variant="ghost" onClick={() => void voice.stopLive()}>
                  <MicOff aria-hidden /> Stop
                </Button>
              </>
            )}
            {pttMode && (
              <Button
                size="xs"
                variant={voice.mode === 'recording' ? 'default' : 'outline'}
                disabled={voice.mode === 'thinking'}
                onPointerDown={() => void voice.pttDown()}
                onPointerUp={() => void voice.pttUp()}
                onKeyDown={(e) => {
                  if ((e.key === ' ' || e.key === 'Enter') && !e.repeat) void voice.pttDown()
                }}
                onKeyUp={(e) => {
                  if (e.key === ' ' || e.key === 'Enter') void voice.pttUp()
                }}
              >
                {voice.mode === 'thinking' ? <LoaderCircle aria-hidden className="animate-spin motion-reduce:animate-none" /> : <Mic aria-hidden />}
                {voice.mode === 'recording' ? 'Release to send' : 'Hold to talk'}
              </Button>
            )}
          </div>
        ) : (
          <p className="text-xs text-zinc-400">This browser or device has no microphone access; use the typed box above.</p>
        )}
        {voice.note && (
          <p className="flex items-start gap-1 text-xs text-zinc-400">
            <Info aria-hidden className="mt-px size-3.5 shrink-0" />
            {voice.note}
          </p>
        )}
        {log.length > 0 && (
          <ol aria-label="Conversation" className="flex flex-col gap-1 text-xs" aria-live="polite">
            {log.map((e) => (
              <li key={e.id} className={e.who === 'you' ? 'text-zinc-400' : 'text-zinc-100'}>
                <span className="font-medium">{e.who === 'you' ? 'You' : 'Co-pilot'}:</span> {e.text}
              </li>
            ))}
          </ol>
        )}
      </section>
      <WhatIfPanel />
      {view.run && (view.run.plan?.length ?? 0) > 0 && !(view.source === 'live' && view.run.status === 'at_gate' && view.run.gate === 'plan') && (
        <div className="border-b p-3">
          <PlanGate run={view.run} interactive={false} />
        </div>
      )}
      <RequirementsPanel />
    </div>
  )
}
