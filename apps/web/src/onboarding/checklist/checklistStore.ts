// Getting-started checklist (spec §13.5). Progress lives in localStorage so it works with the backend down.
import { create } from 'zustand'
import { readJson, writeJson } from '@/lib/storage'

export type ChecklistId = 'open_signed' | 'inspect_source' | 'run_whatif' | 'ask_copilot' | 'run_live' | 'approve'

/** A task, how to do it (one line, matching what ticks it), and where it happens when that is a page of its own. */
export interface ChecklistItem {
  id: ChecklistId
  label: string
  how: string
  go?: { to: string; label: string }
}

export const CHECKLIST: ChecklistItem[] = [
  { id: 'open_signed', label: 'Open a signed design', how: 'Hall A opens signed.', go: { to: '/app/p/hall-a', label: 'Open Hall A' } },
  { id: 'inspect_source', label: 'Inspect a finding and its source', how: 'Open a finding, click its tender chip.' },
  { id: 'run_whatif', label: 'Run a what-if', how: 'Press a What if… chip, e.g. Racks → 200 kW.' },
  { id: 'ask_copilot', label: 'Ask the co-pilot (voice or text)', how: 'Type “why FA-01”, or press Start voice.' },
  { id: 'run_live', label: 'Run Hall B live', how: 'Press Start live run.', go: { to: '/app/p/hall-b', label: 'Open Hall B' } },
  { id: 'approve', label: 'Approve a revision', how: 'Press Approve in your Hall B review.' },
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
