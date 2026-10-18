import { create } from 'zustand'
import { readJson, writeJson } from '@/lib/storage'
import { useLayout } from '@/store/layout'
import { TOUR_STEPS } from './tourSteps'

interface Persisted {
  active: boolean
  step: number
  done: boolean
}
interface TourStore extends Persisted {
  start(): void
  next(): void
  prev(): void
  stop(completed: boolean): void
  reload(): void
}

const KEY = 'tour'
const initial = (): Persisted => readJson<Persisted>(KEY, { active: false, step: 0, done: false })

/** Tour progress persists in localStorage (spec §13.4), so a reload resumes the same step. */
export const useTour = create<TourStore>()((set, get) => {
  const save = (p: Persisted) => {
    writeJson(KEY, p)
    set(p)
  }
  return {
    ...initial(),
    // The steps point into the agents lane and the co-pilot: a panel the visitor hid is shown again first.
    start: () => {
      useLayout.getState().openAll()
      save({ active: true, step: 0, done: get().done })
    },
    next: () => {
      const s = get()
      if (s.step >= TOUR_STEPS.length - 1) save({ active: false, step: 0, done: true })
      else save({ ...s, step: s.step + 1 })
    },
    prev: () => {
      const s = get()
      save({ ...s, step: Math.max(0, s.step - 1) })
    },
    stop: (completed) => save({ active: false, step: 0, done: completed || get().done }),
    reload: () => set(initial()),
  }
})

// A tour resumed after a reload points into the panels too.
if (useTour.getState().active) useLayout.getState().openAll()
