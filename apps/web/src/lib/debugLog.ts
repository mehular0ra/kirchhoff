// A local record of what happened in the co-pilot, for debugging a conversation afterwards: what was typed, heard and
// said, which engine checks ran and what they returned. Gemini's own words are kept here (they are the only place they
// can be saved, because only the browser hears them) but not shown on screen unless the visitor switches on "Show what
// Gemini said" (default off): the written answer is the engine's (spec §6.3). It stays in this browser's localStorage
// until the visitor downloads or clears it.
import { readJson, writeJson } from '@/lib/storage'

const KEY = 'debuglog'
const MAX = 400

export interface DebugEntry {
  /** ISO time. */
  t: string
  kind: string
  [detail: string]: unknown
}

const isEntry = (e: unknown): e is DebugEntry => {
  const x = e as Partial<DebugEntry> | null
  return !!x && typeof x === 'object' && typeof x.t === 'string' && typeof x.kind === 'string'
}

const restored = readJson<unknown>(KEY, [])
let entries: DebugEntry[] = Array.isArray(restored) ? restored.filter(isEntry).slice(-MAX) : []

export function logDebug(kind: string, detail: Record<string, unknown> = {}): void {
  entries = [...entries, { ...detail, t: new Date().toISOString(), kind }].slice(-MAX)
  writeJson(KEY, entries)
}

export const debugEntries = (): DebugEntry[] => entries

export function clearDebugLog(): void {
  entries = []
  writeJson(KEY, entries)
}

/** The whole log as one JSON document, with whatever else helps read it (the project, the conversation as shown). */
export function exportDebugLog(context: Record<string, unknown> = {}): string {
  return JSON.stringify({ app: 'kirchhoff', exported_at: new Date().toISOString(), ...context, entries }, null, 2)
}
