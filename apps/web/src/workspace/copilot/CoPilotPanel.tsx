import { Cpu, Info, LoaderCircle, Mic, MicOff, Send, Volume2 } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { Revision, WhatIfParam, WhatIfResult } from '@/lib/types'
import { completeItem } from '@/onboarding/checklist/checklistStore'
import type { VoiceResponse } from '@/services/apiClient'
import { useServices, type LiveVoiceCall, type LiveVoiceEvent } from '@/services/services'
import { canvasesFor } from '@/lib/model'
import { revisionById, revisionLabel, revisionRef } from '@/lib/select'
import { useConversation } from '@/store/conversation'
import { useUi } from '@/store/ui'
import { PlanGate } from '../gates/PlanGate'
import { RequirementsPanel } from '../RequirementsPanel'
import { useWorkspace } from '../WorkspaceContext'
import { ConversationLog } from './ConversationLog'
import { INTENT_HELP, parseIntent } from './intent'
import { elementId, executeTool, findingLabel, focusActions, lookUpElement, whatIfCheck, type ToolContext } from './tools'
import { useWhatIf } from './useWhatIf'
import { canRecord, speak } from './voice/pushToTalk'
import { useVoice } from './voice/useVoice'
import { WhatIfPanel } from './WhatIfPanel'

/** A Live turn with no news for this long is over: whatever is said next is a new question. */
const LIVE_TURN_IDLE_MS = 20_000
const NO_TOOL_NOTE = 'Gemini replied by voice on its own, so that reply is not backed by the engine. Ask again, or type the question.'
const STOPPED_NOTE = 'Voice was stopped before there was an answer.'

/** What a Live conversation is doing right now, for the status line next to the mic. */
type LiveActivity = 'idle' | 'hearing' | 'checking' | 'replying'

const LIVE_STATUS: Record<LiveActivity, { Icon: typeof Mic; text: string; motion: string }> = {
  idle: { Icon: Mic, text: 'Listening (Gemini Live)', motion: 'animate-pulse motion-reduce:animate-none' },
  hearing: { Icon: Mic, text: 'Hearing you…', motion: 'animate-pulse motion-reduce:animate-none' },
  checking: { Icon: Cpu, text: 'Checking with the engine…', motion: 'animate-pulse motion-reduce:animate-none' },
  replying: { Icon: Volume2, text: 'Gemini is replying…', motion: '' },
}

const conv = () => useConversation.getState()

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
  const ctx: ToolContext = { view, api, runWhatIf, focus, openFinding, setViewRev }
  const ctxRef = useRef(ctx)
  useEffect(() => {
    ctxRef.current = { view, api, runWhatIf, focus, openFinding, setViewRev }
  }, [view, api, runWhatIf, focus, openFinding, setViewRev])

  // The conversation belongs to the project it was had in.
  const projectId = view.bundle.project.id
  useEffect(() => conv().enter(projectId), [projectId])

  const ask = async (q: string) => {
    const id = conv().start('typed', q, 'working')
    completeItem('ask_copilot')
    const intent = parseIntent(q)
    if (!intent) {
      conv().setPhase(id, 'unchecked', INTENT_HELP)
      return
    }
    const args =
      intent.tool === 'what_if'
        ? { param: intent.param, value: intent.value }
        : intent.tool === 'explain_finding'
          ? { element_id: intent.element, rule_id: intent.rule }
          : { element_id: intent.element }
    try {
      const out = await executeTool(intent.tool, args, ctxRef.current)
      conv().addStep(id, { check: out.check, answer: out.summary, actions: out.actions })
      conv().setPhase(id, 'answered')
    } catch {
      conv().setPhase(id, 'failed', 'That check could not run.')
    }
  }

  // ---- Gemini Live: one history card per question, built from the transcript, the tool calls and the turn ends.
  const liveTurn = useRef<{ id: number; last: number } | null>(null)
  const [activity, setActivity] = useState<LiveActivity>('idle')

  /** The card of the question being asked or answered, if there is one that is not long over. */
  const currentLiveTurn = () => {
    const t = liveTurn.current
    return t && Date.now() - t.last <= LIVE_TURN_IDLE_MS ? t : null
  }
  /** Closes the open card: with an engine answer it is answered, without one it says no engine check ran. */
  const endLiveTurn = (note: string) => {
    const t = liveTurn.current
    liveTurn.current = null
    if (!t) return
    const turn = conv().turns.find((x) => x.id === t.id)
    if (!turn || turn.phase === 'failed') return
    if (turn.steps.length > 0) conv().setPhase(t.id, 'answered')
    else conv().setPhase(t.id, 'unchecked', note)
  }

  const onLiveEvent = (e: LiveVoiceEvent) => {
    if (e.type === 'heard') {
      const open = currentLiveTurn()
      if (open) {
        conv().hear(open.id, e.text)
        open.last = Date.now()
      } else {
        liveTurn.current = { id: conv().start('live', e.text, 'hearing'), last: Date.now() }
      }
      setActivity('hearing')
    } else if (e.type === 'speaking') {
      const open = currentLiveTurn()
      const turn = open && conv().turns.find((x) => x.id === open.id)
      if (open && turn?.phase === 'hearing') conv().setPhase(open.id, 'working')
      setActivity('replying')
    } else {
      endLiveTurn(NO_TOOL_NOTE)
      setActivity('idle')
    }
  }

  const onToolCall = async (call: LiveVoiceCall) => {
    completeItem('ask_copilot')
    // A tool call with no transcript before it (the service sends none) still gets a card, with no words.
    let open = currentLiveTurn()
    if (!open) open = liveTurn.current = { id: conv().start('live', null, 'working'), last: Date.now() }
    open.last = Date.now()
    conv().setPhase(open.id, 'working')
    setActivity('checking')
    try {
      const out = await executeTool(call.name, call.args, ctxRef.current)
      conv().addStep(open.id, { check: out.check, answer: out.summary, actions: out.actions })
      conv().setPhase(open.id, 'answered')
      setActivity('replying')
      return out.data
    } catch {
      conv().setPhase(open.id, 'failed', 'That check could not run.')
      setActivity('idle')
      // Answer Gemini instead of throwing: the SDK ends the whole conversation when this handler throws.
      return { error: 'unavailable' }
    }
  }

  // ---- Push-to-talk: the server ran the tools; the panel applies their effects and writes them up.
  const onPushToTalk = (res: VoiceResponse, sentRef: string) => {
    completeItem('ask_copilot')
    // The revision /api/voice answered on (#37): the head, unless one was picked in the revision bar.
    const askedOn = view.bundle.revisions.find((r) => revisionRef(view.bundle, r.id, view.source) === sentRef) ?? null
    let whatIfOn: Revision | null = null
    const checks: string[] = []
    const actions: string[] = []
    const details: string[] = []
    for (const t of res.tool_results) {
      if (t.name === 'what_if' && Array.isArray((t.result as Partial<WhatIfResult>).impact_chain)) {
        const w = { result: t.result as unknown as WhatIfResult, origin: 'engine' as const }
        if (askedOn) showWhatIf(askedOn, w)
        else setWhatIf(w)
        whatIfOn = askedOn
        checks.push(whatIfCheck(String(t.args.param) as WhatIfParam, Number(t.args.value)))
        if (askedOn) actions.push(`Ran on ${revisionLabel(askedOn)}; engine only, nothing saved`)
        actions.push('The result is in the What-if panel and lit on the canvases')
      }
      if (t.name === 'focus_element') {
        // The server only says "Showing X"; what X is comes from the engine's model here, as for typed and Live questions.
        const id = elementId(t.args.element_id ?? t.result.element_id)
        const drawn = focus(id)
        details.push(lookUpElement(view.model, view.findings, id, drawn).summary)
        checks.push(`Details of ${id}`)
        actions.push(...focusActions(view.model, id, drawn))
      }
      if (t.name === 'explain_finding' && t.args.finding_id) {
        // D1, as typed and Live answers do (tools.ts): when the answer cites an earlier revision where the
        // check failed (`result.revision`, set by /api/voice only then), switch to it before opening the finding.
        // An automatic switch, not a revision-bar pick: later what-ifs stay on the head (#37).
        const cited = typeof t.result.revision === 'string' ? revisionById(view.bundle, t.result.revision) : null
        if (cited) setViewRev(cited.id, { source: 'auto' })
        openFinding(String(t.args.finding_id))
        checks.push(`Explain finding ${findingLabel(String(t.args.finding_id))}`)
        if (cited) actions.push(`Switched to ${revisionLabel(cited)}, where this check failed`)
        actions.push(`Opened ${findingLabel(String(t.args.finding_id))} in the finding drawer`)
      }
    }
    // A what-if answer names the revision it ran on, like the typed one: "On r2 (signed): …".
    const onlyElements = res.tool_results.length > 0 && res.tool_results.every((t) => t.name === 'focus_element')
    const answer = whatIfOn ? `On ${revisionLabel(whatIfOn)}: ${res.answer}` : onlyElements ? details.join(' ') : res.answer
    const id = conv().start('ptt', res.transcript || null, 'working')
    if (checks.length > 0) {
      conv().addStep(id, { check: checks.join(' + '), answer, actions })
      conv().setPhase(id, 'answered')
    } else {
      conv().setPhase(id, 'unchecked', answer)
    }
    speak(answer)
  }

  const voice = useVoice({ revisionRef: whatIfRef, onToolCall, onPushToTalk, onLiveEvent })
  const pttMode = voice.mode === 'ptt' || voice.mode === 'recording' || voice.mode === 'thinking'
  const micAvailable = canRecord()
  const stopVoice = async () => {
    await voice.stopLive()
    endLiveTurn(STOPPED_NOTE)
    setActivity('idle')
  }
  // Live's activity is only shown while Live is on (starting it again begins from idle).
  const live = LIVE_STATUS[voice.mode === 'live' ? activity : 'idle']

  return (
    <div className="flex flex-col">
      <section aria-label="Ask the co-pilot" className="flex flex-col gap-2 border-b p-3">
        <h3 className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          <span aria-hidden className="size-2 rounded-full bg-[linear-gradient(135deg,#d946ef,#0ea5e9)]" /> Co-pilot
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
        <p id="copilot-hint" className="-mt-1 text-[11px] text-muted-foreground">
          Try “why FA-01” or “what if racks go to 200 kW”
        </p>
        {micAvailable ? (
          <div className="flex flex-wrap items-center gap-2">
            {voice.mode === 'off' && (
              <Button
                size="xs"
                variant="outline"
                onClick={() => {
                  setActivity('idle')
                  void voice.startLive()
                }}
              >
                <Mic aria-hidden /> Start voice
              </Button>
            )}
            {voice.mode === 'connecting' && (
              <span role="status" className="inline-flex items-center gap-1 text-xs text-zinc-700">
                <LoaderCircle aria-hidden className="size-3.5 animate-spin motion-reduce:animate-none" /> Connecting to Gemini Live…
              </span>
            )}
            {voice.mode === 'live' && (
              <>
                <span role="status" className="inline-flex items-center gap-1 text-xs text-fuchsia-700">
                  <live.Icon aria-hidden className={`size-3.5 ${live.motion}`} />
                  {live.text}
                </span>
                <Button size="xs" variant="ghost" onClick={() => void stopVoice()}>
                  <MicOff aria-hidden /> Stop
                </Button>
              </>
            )}
            {pttMode && (
              <>
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
                {voice.mode === 'thinking' && (
                  <span role="status" className="text-xs text-muted-foreground">
                    Sending your question…
                  </span>
                )}
              </>
            )}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">This browser or device has no microphone access; use the typed box above.</p>
        )}
        {voice.note && (
          <p className="flex items-start gap-1 text-xs text-muted-foreground">
            <Info aria-hidden className="mt-px size-3.5 shrink-0" />
            {voice.note}
          </p>
        )}
      </section>
      <ConversationLog />
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
