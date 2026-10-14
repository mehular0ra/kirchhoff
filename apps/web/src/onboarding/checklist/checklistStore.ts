// Getting-started checklist (spec §13.5). Progress lives in localStorage so it works with the backend down.
import { create } from 'zustand'
import { readJson, writeJson } from '@/lib/storage'

export type ChecklistId = 'open_signed' | 'inspect_source' | 'run_whatif' | 'ask_copilot' | 'run_live' | 'approve'

export const CHECKLIST: { id: ChecklistId; label: string }[] = [
  { id: 'open_signed', label: 'Open a signed design' },
  { id: 'inspect_source', label: 'Inspect a finding and its source' },
  { id: 'run_whatif', label: 'Run a what-if' },
  { id: 'ask_copilot', label: 'Ask the co-pilot (voice or text)' },
  { id: 'run_live', label: 'Run Hall B live' },
  { id: 'approve', label: 'Approve a revision' },
]

const KEY = 'checklist'
type Done = Partial<Record<ChecklistId, true>>

interface ChecklistStore {
  done: Done
  complete(id: ChecklistId): void
  reload(): void
}

export const useChecklist = create<ChecklistStore>()((set, get) => ({
  done: readJson<Done>(KEY, {}),
  complete: (id) => {
    if (get().done[id]) return
    const done = { ...get().done, [id]: true as const }
    writeJson(KEY, done)
    set({ done })
  },
  reload: () => set({ done: readJson<Done>(KEY, {}) }),
}))

export function completeItem(id: ChecklistId): void {
  useChecklist.getState().complete(id)
}
