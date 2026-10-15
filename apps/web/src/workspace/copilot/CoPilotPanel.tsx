import { LoaderCircle, Mic, MicOff, Send } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { WhatIfResult } from '@/lib/types'
import { completeItem } from '@/onboarding/checklist/checklistStore'
import type { VoiceResponse } from '@/services/apiClient'
import { useServices, type LiveVoiceCall } from '@/services/services'
import { canvasesFor } from '@/lib/model'
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
  const { run: runWhatIf } = useWhatIf()
  const focusUi = useUi((s) => s.focus)
  // Co-pilot "show H-Z2" switches to a canvas that draws the element (I5).
  const focus = useCallback((id: string) => focusUi(id, canvasesFor(view.model, id)), [focusUi, view.model])
  const openFinding = useUi((s) => s.openFinding)
  const setWhatIf = useUi((s) => s.setWhatIf)
  const [text, setText] = useState('')
  const [log, setLog] = useState<LogEntry[]>([])
  const seq = useRef(0)
  const ctx: ToolContext = { view, api, runWhatIf, focus, openFinding }
  const ctxRef = useRef(ctx)
  useEffect(() => {
    ctxRef.current = { view, api, runWhatIf, focus, openFinding }
  }, [view, api, runWhatIf, focus, openFinding])

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

  const onPushToTalk = (res: VoiceResponse) => {
    completeItem('ask_copilot')
    add('you', 'voice', res.transcript)
    for (const t of res.tool_results) {
      if (t.name === 'what_if' && Array.isArray((t.result as Partial<WhatIfResult>).impact_chain))
        setWhatIf({ result: t.result as unknown as WhatIfResult, origin: 'engine' })
      if (t.name === 'focus_element') focus(String(t.args.element_id ?? t.result.element_id ?? ''))
      if (t.name === 'explain_finding' && t.args.finding_id) openFinding(String(t.args.finding_id))
    }
    add('co-pilot', 'voice', res.answer)
    speak(res.answer)
  }

  const voice = useVoice({ revisionRef: view.revRef, onToolCall, onPushToTalk })
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
            placeholder="Ask, or “what if racks go to 200 kW”"
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="h-8 text-xs"
          />
          <Button size="icon-sm" type="submit" aria-label="Send">
            <Send aria-hidden />
          </Button>
        </form>
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
        {voice.note && <p className="text-xs text-zinc-400">{voice.note}</p>}
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
