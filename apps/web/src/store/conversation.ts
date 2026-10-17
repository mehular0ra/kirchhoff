// What the co-pilot was asked and what it did about it, typed, spoken to Gemini Live or push-to-talk, oldest first.
// One turn per question: the answer, the engine check behind it and what changed on screen stay together, so a slow
// answer can never land under a later question.
import { create } from 'zustand'

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
}

interface ConversationState {
  /** The project the turns belong to: a conversation about Hall A is never shown in another project's panel. */
  project: string | null
  turns: Turn[]
  /** Called when a panel opens on a project: a different project starts an empty conversation, the same one keeps its turns. */
  enter(project: string): void
  start(via: TurnVia, asked: string | null, phase?: TurnPhase): number
  /** Appends a piece of the transcript of a spoken question. */
  hear(id: number, text: string): void
  setPhase(id: number, phase: TurnPhase, note?: string | null): void
  addStep(id: number, step: TurnStep): void
  clear(): void
}

let next = 0

const patch = (turns: Turn[], id: number, f: (t: Turn) => Turn): Turn[] => turns.map((t) => (t.id === id ? f(t) : t))

export const useConversation = create<ConversationState>()((set) => ({
  project: null,
  turns: [],
  enter: (project) => set((s) => (s.project === project ? s : { project, turns: [] })),
  start: (via, asked, phase = 'working') => {
    const id = ++next
    set((s) => ({ turns: [...s.turns, { id, via, asked, phase, steps: [], note: null, at: Date.now() }] }))
    return id
  },
  hear: (id, text) => set((s) => ({ turns: patch(s.turns, id, (t) => ({ ...t, asked: (t.asked ?? '') + text })) })),
  setPhase: (id, phase, note = null) => set((s) => ({ turns: patch(s.turns, id, (t) => ({ ...t, phase, note })) })),
  addStep: (id, step) => set((s) => ({ turns: patch(s.turns, id, (t) => ({ ...t, steps: [...t.steps, step] })) })),
  clear: () => set({ turns: [] }),
}))
