// Dependency injection for everything that talks to the network, so components and tests never
// import firebase.ts directly. Production wiring lives in services/production.ts.
import { createContext, useContext, type ReactNode } from 'react'
import type { LiveSource } from '@/data/liveSource'
import type { JsonFetch } from '@/data/staticData'
import type { ApiClient } from './apiClient'

/** A function call requested by the Gemini Live model (spec §6.5 tools). */
export interface LiveVoiceCall {
  id?: string
  name: string
  args: Record<string, unknown>
}
/**
 * What a Live conversation reports besides its tool calls (workspace/copilot/voice/liveEvents.ts): a piece of what the
 * visitor said, that the model has started its spoken reply, and that the turn is over. The model's own words are
 * never in an event: the written answer is the engine's.
 */
export type LiveVoiceEvent = { type: 'heard'; text: string } | { type: 'speaking' } | { type: 'turn_complete' }
/** One finished Live turn, both sides in full (the model's own words included): for the debug log only, never for the screen. */
export interface LiveTurnRecord {
  heard: string
  said: string
  interrupted: boolean
}
export interface LiveVoiceHandle {
  stop(): Promise<void>
}
export type StartLiveVoice = (opts: {
  onToolCall: (call: LiveVoiceCall) => Promise<Record<string, unknown>>
  /** Optional: the transcript and turn boundaries, for the conversation history. */
  onEvent?: (e: LiveVoiceEvent) => void
  /** Optional: each finished turn in full, for the debug log. */
  onDebug?: (turn: LiveTurnRecord) => void
  /** Optional: facts about the design from the engine, given to the model when the session starts. */
  context?: string
}) => Promise<LiveVoiceHandle>

export interface Services {
  api: ApiClient
  getJson: JsonFetch
  /** Firestore reader for the visitor workspace; null when Firebase is unavailable. */
  live: LiveSource | null
  /** Anonymous Firebase uid (signs in on first use). */
  uid: () => Promise<string>
  /** Gemini Live voice session starter; null disables Live and forces push-to-talk. */
  startLiveVoice: StartLiveVoice | null
}

const Ctx = createContext<Services | null>(null)

export function ServicesProvider({ services, children }: { services: Services; children: ReactNode }) {
  return <Ctx.Provider value={services}>{children}</Ctx.Provider>
}

export function useServices(): Services {
  const s = useContext(Ctx)
  if (!s) throw new Error('useServices outside ServicesProvider')
  return s
}
