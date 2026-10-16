import { CircleX, Hand, ListChecks } from 'lucide-react'
import { useState } from 'react'
import { Hint } from '@/components/Hint'
import { AgentDot } from '@/components/Labels'
import { TenderChip } from '@/components/TenderChip'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { AGENTS } from '@/lib/agents'
import type { RunRecord } from '@/lib/types'
import { describeApiError } from '@/services/apiClient'
import { useServices } from '@/services/services'

/** WS2's answer values (ruling R21): the main-body value (e.g. "2N") or "compare_all". */
const ANSWER_LABELS: Record<string, string> = { compare_all: 'Compare all three topologies' }
export const answerLabel = (v: string) => ANSWER_LABELS[v] ?? v

/**
 * Plan gate (spec §12 screen 4): steps with owners, Intake's open questions with cited sources,
 * Approve. Interactive only for a live run waiting at the plan gate; otherwise read-only history.
 * Answers are limited to the question's options (WS2 rejects anything else with 422 invalid_answer).
 */
export function PlanGate({ run, interactive }: { run: RunRecord; interactive: boolean }) {
  const { api } = useServices()
  const plan = run.plan ?? []
  const questions = run.open_questions ?? []
  const [answers, setAnswers] = useState<Record<string, string>>(() =>
    Object.fromEntries(questions.map((q) => [q.id, q.resolution ?? q.default_resolution])),
  )
  const [notes, setNotes] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const approve = async () => {
    setBusy(true)
    setError(null)
    try {
      await api.planGate(run.id, answers, Object.fromEntries(Object.entries(notes).filter(([, v]) => v.trim())))
    } catch (e) {
      setError(describeApiError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section aria-label="Plan" className="flex flex-col gap-3 rounded-lg border bg-card p-3 text-sm" data-tour="plan-gate">
      <Hint id="gates" text="Gates pause the run until you decide. In Auto, plan and option gates resolve by the tender and log why.">
        <h3 tabIndex={0} className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {interactive ? <Hand aria-hidden className="size-4 text-amber-700" /> : <ListChecks aria-hidden className="size-4" />}
          {interactive ? 'Plan gate · waiting for you' : 'Plan'}
        </h3>
      </Hint>
      <ol className="flex flex-col gap-2">
        {plan.map((s, i) => (
          <li key={s.id} className="flex flex-col gap-0.5">
            {/* Number, title, then the agent on its own line: titles align and keep the column's full width (polish). */}
            <span className="flex items-baseline gap-2">
              <span className="w-4 shrink-0 font-mono text-xs text-muted-foreground">{i + 1}</span>
              <span className="min-w-0 text-foreground">{s.title}</span>
            </span>
            <span className="ml-6 inline-flex items-center gap-1.5 text-xs text-muted-foreground">
              <AgentDot agent={s.agent} />
              {AGENTS[s.agent].label}
            </span>
            {interactive ? (
              <Input
                aria-label={`Note for ${s.title}`}
                placeholder="Optional note for this step"
                value={notes[s.id] ?? ''}
                onChange={(e) => setNotes({ ...notes, [s.id]: e.target.value })}
                className="ml-6 h-7 text-xs"
              />
            ) : (
              s.note && <span className="ml-6 text-xs text-muted-foreground">Note: {s.note}</span>
            )}
          </li>
        ))}
      </ol>
      {questions.map((q) => (
        <fieldset key={q.id} className="flex flex-col gap-2 rounded border border-amber-500/30 bg-amber-500/5 p-2">
          <legend className="px-1 text-xs font-medium text-amber-700">Open question</legend>
          <p className="text-foreground">{q.text}</p>
          <div className="flex flex-wrap gap-1.5">
            {q.citations.map((c) => (
              <TenderChip key={`${c.page}${c.clause}`} citation={c} />
            ))}
          </div>
          {interactive ? (
            <>
              <RadioGroup
                value={q.options.includes(answers[q.id]) ? answers[q.id] : ''}
                onValueChange={(v) => setAnswers({ ...answers, [q.id]: v })}
                aria-label={q.text}
              >
                {q.options.map((o) => (
                  <label key={o} className="flex items-center gap-2 text-xs">
                    <RadioGroupItem value={o} aria-label={answerLabel(o)} /> {answerLabel(o)}
                  </label>
                ))}
              </RadioGroup>
            </>
          ) : (
            <p className="text-xs text-zinc-700">
              Resolved: <span className="text-foreground">{answerLabel(q.resolution ?? q.default_resolution)}</span>
            </p>
          )}
        </fieldset>
      ))}
      {interactive && (
        <div className="flex items-center gap-2">
          <Button size="sm" onClick={() => void approve()} disabled={busy}>
            Approve plan
          </Button>
          {error && (
            <span role="alert" className="inline-flex items-center gap-1.5 text-xs text-rose-700">
              <CircleX aria-hidden className="size-3.5" /> {error}
            </span>
          )}
        </div>
      )}
    </section>
  )
}
