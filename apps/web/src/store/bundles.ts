// One in-browser store holding a ProjectBundle per project view, fed by the static, live and
// replay adapters (spec §11 "one bundle format").
import { create } from 'zustand'
import type { DataSource } from '@/lib/select'
import type { Bundle } from '@/lib/types'

export interface ReplayState {
  cursor: number
  total: number
  playing: boolean
  speed: number
  elapsedS: number
}

export interface BundleEntry {
  status: 'loading' | 'ready' | 'error'
  source: DataSource
  bundle: Bundle | null
  error?: string
  replay?: ReplayState
}

interface BundleStore {
  entries: Record<string, BundleEntry>
  setLoading(key: string, source: DataSource): void
  setBundle(key: string, bundle: Bundle, source: DataSource): void
  setError(key: string, error: string, source: DataSource): void
  setReplay(key: string, replay: ReplayState): void
  clear(key: string): void
}

export const useBundleStore = create<BundleStore>()((set) => ({
  entries: {},
  setLoading: (key, source) =>
    set((s) => ({ entries: { ...s.entries, [key]: { status: 'loading', source, bundle: s.entries[key]?.bundle ?? null } } })),
  setBundle: (key, bundle, source) =>
    set((s) => ({ entries: { ...s.entries, [key]: { ...s.entries[key], status: 'ready', source, bundle, error: undefined } } })),
  setError: (key, error, source) =>
    set((s) => ({ entries: { ...s.entries, [key]: { status: 'error', source, bundle: s.entries[key]?.bundle ?? null, error } } })),
  setReplay: (key, replay) =>
    set((s) => (s.entries[key] ? { entries: { ...s.entries, [key]: { ...s.entries[key], replay } } } : s)),
  clear: (key) =>
    set((s) => {
      const entries = { ...s.entries }
      delete entries[key]
      return { entries }
    }),
}))

export function entryKey(pid: string, opts: { runId?: string | null; replay?: boolean } = {}): string {
  if (opts.runId) return `${pid}:live:${opts.runId}`
  return opts.replay ? `${pid}:replay` : `${pid}:static`
}
