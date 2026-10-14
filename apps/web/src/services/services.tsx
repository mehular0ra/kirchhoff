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
export interface LiveVoiceHandle {
  stop(): Promise<void>
}
export type StartLiveVoice = (opts: {
  onToolCall: (call: LiveVoiceCall) => Promise<Record<string, unknown>>
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
