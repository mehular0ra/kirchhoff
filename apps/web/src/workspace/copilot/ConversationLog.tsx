// The co-pilot's history: one card per question, oldest first. Each card keeps together what was asked (typed, or the
// transcript of what was said), which engine check answered, the engine's answer, and what changed on screen because
// of it, so a spoken question is never an answer from nowhere. When no engine check ran, the card says so.
import { Check, CircleX, Cpu, Download, Keyboard, LoaderCircle, Mic, Trash2, TriangleAlert } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { Button } from '@/components/ui/button'
import { exportDebugLog } from '@/lib/debugLog'
import { useConversation, type Turn, type TurnVia } from '@/store/conversation'

const VIA: Record<TurnVia, { label: string; Icon: typeof Mic }> = {
  typed: { label: 'You · typed', Icon: Keyboard },
  live: { label: 'You · voice', Icon: Mic },
  ptt: { label: 'You · push-to-talk', Icon: Mic },
}

const clock = (at: number) => new Date(at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

function TurnCard({ turn }: { turn: Turn }) {
  const { label, Icon } = VIA[turn.via]
  const waiting = turn.phase === 'working' && turn.steps.length === 0
  return (
    <li data-turn={turn.id} className="flex flex-col gap-1.5 rounded-lg border bg-background/60 p-2 text-xs">
      <div className="flex items-center gap-1.5 text-muted-foreground">
        <Icon aria-hidden className="size-3.5" />
        <span className="font-medium">{label}</span>
        <time className="ml-auto tabular-nums" dateTime={new Date(turn.at).toISOString()}>
          {clock(turn.at)}
        </time>
      </div>
      {turn.asked ? (
        <p className="text-foreground">{turn.asked}</p>
      ) : (
        turn.phase !== 'hearing' && <p className="italic text-muted-foreground">(your words were not transcribed)</p>
      )}
      {turn.steps.map((s, i) => (
        <div key={i} className="flex flex-col gap-1 border-l-2 border-indigo-300 pl-2">
          <p className="flex items-center gap-1 text-[11px] font-medium text-muted-foreground">
            <Cpu aria-hidden className="size-3 shrink-0" />
            <span>Engine check</span>
          </p>
          <p className="font-medium text-foreground">{s.check}</p>
          <p className="text-foreground">{s.answer}</p>
          {s.actions.length > 0 && (
            <>
              <p id={`changes-${turn.id}-${i}`} className="text-[11px] font-medium text-muted-foreground">
                What changed on screen
              </p>
              <ul aria-labelledby={`changes-${turn.id}-${i}`} className="flex flex-col gap-0.5 text-muted-foreground">
                {s.actions.map((a) => (
                  <li key={a} className="flex items-start gap-1">
                    <Check aria-hidden className="mt-0.5 size-3 shrink-0 text-emerald-700" />
                    {a}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      ))}
      {waiting && (
        <p className="flex items-center gap-1 text-muted-foreground">
          <LoaderCircle aria-hidden className="size-3.5 animate-spin motion-reduce:animate-none" />
          <span>Waiting for the engine…</span>
        </p>
      )}
      {turn.phase === 'hearing' && (
        <p className="flex items-center gap-1 text-muted-foreground">
          <Mic aria-hidden className="size-3.5 animate-pulse motion-reduce:animate-none" />
          <span>Listening…</span>
        </p>
      )}
      {turn.phase === 'unchecked' && (
        <div className="flex flex-col gap-0.5 rounded border border-amber-300 bg-amber-50 p-1.5 text-amber-950">
          <p className="flex items-center gap-1 font-medium">
            <TriangleAlert aria-hidden className="size-3.5 shrink-0" />
            <span>No engine check ran</span>
          </p>
          <p>Nothing was verified and nothing changed on screen.</p>
          {turn.note && <p>{turn.note}</p>}
        </div>
      )}
      {turn.phase === 'failed' && (
        <p className="flex items-center gap-1 text-red-800">
          <CircleX aria-hidden className="size-3.5 shrink-0" />
          <span>{turn.note ?? 'That check could not run.'}</span>
        </p>
      )}
    </li>
  )
}

export function ConversationLog() {
  const turns = useConversation((s) => s.turns)
  const elsewhere = useConversation((s) => Object.keys(s.saved).length > 0)
  const clear = useConversation((s) => s.clear)
  /** Saves the debug log (every entry, plus the conversation as shown) as one JSON file; the engine's own words and Gemini's. */
  const download = () => {
    const { project, turns: shown, saved } = useConversation.getState()
    const text = exportDebugLog({ project, conversation: { turns: shown, saved } })
    const url = URL.createObjectURL(new Blob([text], { type: 'application/json' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `kirchhoff-debug-${new Date().toISOString().replace(/[:.]/g, '-')}.json`
    a.click()
    URL.revokeObjectURL(url)
  }
  const listRef = useRef<HTMLOListElement>(null)
  // Keep the newest question in view inside the list, without scrolling the whole side panel.
  useEffect(() => {
    const el = listRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [turns])

  return (
    <section aria-label="Conversation history" className="flex flex-col gap-1.5 border-b p-3">
      <div className="flex items-center gap-2">
        <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Conversation</h3>
        {turns.length > 0 && <span className="text-[11px] text-muted-foreground">{`${turns.length} ${turns.length === 1 ? 'question' : 'questions'}`}</span>}
        <span className="ml-auto flex items-center gap-0.5">
          <Button size="icon-xs" variant="ghost" aria-label="Download debug log" title="Download the debug log: what was asked, heard and said, and what the engine answered" onClick={download}>
            <Download aria-hidden />
          </Button>
          {turns.length > 0 && (
            <Button size="icon-xs" variant="ghost" aria-label="Clear conversation" onClick={clear}>
              <Trash2 aria-hidden />
            </Button>
          )}
        </span>
      </div>
      <p className="text-[11px] text-muted-foreground">The engine writes every answer. Voice only chooses which check to run.</p>
      {turns.length === 0 ? (
        <>
          <p className="text-xs text-muted-foreground">Ask by typing or by voice. Each question appears here with the engine check behind its answer and what changed on screen.</p>
          {elsewhere && <p className="text-[11px] text-muted-foreground">Questions you asked in other projects are kept with them.</p>}
        </>
      ) : (
        <ol ref={listRef} aria-label="Conversation" aria-live="polite" className="flex max-h-80 flex-col gap-2 overflow-y-auto">
          {turns.map((t) => (
            <TurnCard key={t.id} turn={t} />
          ))}
        </ol>
      )}
    </section>
  )
}
