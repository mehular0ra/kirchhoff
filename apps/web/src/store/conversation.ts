// What the co-pilot was asked and what it did about it, typed, spoken to Gemini Live or push-to-talk, oldest first.
// One turn per question: the answer, the engine check behind it and what changed on screen stay together, so a slow
// answer can never land under a later question.
import { create } from 'zustand'
import { readJson, writeJson } from '@/lib/storage'

export type TurnVia = 'typed' | 'live' | 'ptt'
/**
 * hearing: the visitor is still speaking. working: waiting for the engine. answered: an engine check answered.
 * unchecked: no engine check ran, so nothing was verified or changed. failed: the check could not run.
 */
export type TurnPhase = 'hearing' | 'working' | 'answered' | 'unchecked' | 'failed'

export interface TurnStep {
  /** What the engine was asked, in words: "Explain finding R05 · FA-01". */
  check: string
  /** The engine-built answer text (spec §6.3); never the model's own words. */
  answer: string
  /** What changed on screen because of it, one plain sentence each. */
  actions: string[]
}

export interface Turn {
  id: number
  via: TurnVia
  /** What was said or typed; null for a spoken question that was not transcribed. */
  asked: string | null
  phase: TurnPhase
  steps: TurnStep[]
  /** Why there is no engine answer (phase "unchecked" or "failed"); a plain sentence. */
  note: string | null
  at: number
  /** False while a spoken question's turn is still going (its words may still arrive); typed and finished turns are ended. */
  ended: boolean
  /** What the model said aloud, kept apart from the engine answer; shown only if the visitor switches it on (never the answer). */
  said: string | null
}

interface ConversationState {
  /** The project on screen: a conversation about Hall A is never shown in another project's panel. */
  project: string | null
  /** That project's turns. */
  turns: Turn[]
  /** The other projects' turns, kept until their panel opens again. */
  saved: Record<string, Turn[]>
  /** Called when a panel opens on a project: its own turns come back (none, the first time), the previous project's are kept. */
  enter(project: string): void
  start(via: TurnVia, asked: string | null, phase?: TurnPhase): number
  /** Appends a piece of the transcript of a spoken question. */
  hear(id: number, text: string): void
  setPhase(id: number, phase: TurnPhase, note?: string | null): void
  addStep(id: number, step: TurnStep): void
  setEnded(id: number, ended: boolean): void
  setSaid(id: number, said: string): void
  clear(): void
}

// The history lives in localStorage (like the getting-started checklist), so a reload, or a visit to another hall and
// back, does not lose it. Only the latest turns of a few projects are kept.
const KEY = 'conversation'
const MAX_TURNS = 100
const MAX_SAVED_PROJECTS = 8
const LEFT = 'This page was closed or reloaded before there was an answer.'

interface Stored {
  project: string | null
  turns: Turn[]
  saved: Record<string, Turn[]>
}

const isTurn = (t: unknown): t is Turn => {
  const x = t as Partial<Turn> | null
  return !!x && typeof x === 'object' && typeof x.id === 'number' && typeof x.at === 'number' && Array.isArray(x.steps)
}

/** A question still being heard or checked when the page went away will never get its answer: say so, instead of spinning. */
const settle = (t: Turn): Turn => {
  if (t.phase === 'hearing') return { ...t, phase: 'unchecked', note: LEFT }
  if (t.phase === 'working') return t.steps.length > 0 ? { ...t, phase: 'answered', note: null } : { ...t, phase: 'failed', note: LEFT }
  return t
}

// Whatever a page left behind is over: nothing more will arrive for it. (Turns saved before `ended` and `said` existed lack them.)
const closed = (t: Turn): Turn => ({ ...t, ended: true, said: t.said ?? null })

const turnList = (v: unknown): Turn[] => (Array.isArray(v) ? v.filter(isTurn).map(settle).map(closed).slice(-MAX_TURNS) : [])

function restore(): Stored {
  const raw = readJson<Partial<Stored> | null>(KEY, null)
  if (!raw || typeof raw !== 'object') return { project: null, turns: [], saved: {} }
  const saved: Record<string, Turn[]> = {}
  if (raw.saved && typeof raw.saved === 'object' && !Array.isArray(raw.saved))
    for (const [project, turns] of Object.entries(raw.saved)) {
      const list = turnList(turns)
      if (list.length > 0) saved[project] = list
    }
  return { project: typeof raw.project === 'string' ? raw.project : null, turns: turnList(raw.turns), saved }
}

const initial = restore()
// New ids continue after the restored ones, so an answer can never land on an older question.
let next = Math.max(0, ...[initial.turns, ...Object.values(initial.saved)].flat().map((t) => t.id))

const patch = (turns: Turn[], id: number, f: (t: Turn) => Turn): Turn[] => turns.map((t) => (t.id === id ? f(t) : t))

/** Changes one turn wherever it is: an answer can arrive after the visitor moved to another project, and must still reach its own question. */
const update = (s: ConversationState, id: number, f: (t: Turn) => Turn): Partial<ConversationState> => {
  if (s.turns.some((t) => t.id === id)) return { turns: patch(s.turns, id, f) }
  const home = Object.keys(s.saved).find((p) => s.saved[p].some((t) => t.id === id))
  return home ? { saved: { ...s.saved, [home]: patch(s.saved[home], id, f) } } : {}
}

export const useConversation = create<ConversationState>()((set) => ({
  project: initial.project,
  turns: initial.turns,
  saved: initial.saved,
  enter: (project) =>
    set((s) => {
      if (s.project === project) return s
      const saved = { ...s.saved }
      if (s.project && s.turns.length > 0) saved[s.project] = s.turns
      const turns = saved[project] ?? (s.project === null ? s.turns : [])
      delete saved[project]
      return { project, turns, saved: Object.fromEntries(Object.entries(saved).slice(-MAX_SAVED_PROJECTS)) }
    }),
  start: (via, asked, phase = 'working') => {
    const id = ++next
    set((s) => ({ turns: [...s.turns, { id, via, asked, phase, steps: [], note: null, at: Date.now(), ended: via !== 'live', said: null }].slice(-MAX_TURNS) }))
    return id
  },
  hear: (id, text) => set((s) => update(s, id, (t) => ({ ...t, asked: (t.asked ?? '') + text }))),
  setPhase: (id, phase, note = null) => set((s) => update(s, id, (t) => ({ ...t, phase, note }))),
  addStep: (id, step) => set((s) => update(s, id, (t) => ({ ...t, steps: [...t.steps, step] }))),
  setEnded: (id, ended) => set((s) => update(s, id, (t) => ({ ...t, ended }))),
  setSaid: (id, said) => set((s) => update(s, id, (t) => ({ ...t, said }))),
  clear: () => set({ turns: [] }),
}))

useConversation.subscribe((s) => writeJson(KEY, { project: s.project, turns: s.turns, saved: s.saved } satisfies Stored))
