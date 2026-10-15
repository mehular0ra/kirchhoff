import { ChevronDown, Circle, CircleCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import { create } from 'zustand'
import { cn } from 'cn'
import { CHECKLIST, useChecklist } from './checklistStore'

/** Number of mounted docked checklists; while one is docked the floating card stays hidden. */
const useDock = create<{ docked: number; add(n: number): void }>()((set) => ({
  docked: 0,
  add: (n) => set((s) => ({ docked: s.docked + n })),
}))

/**
 * Getting-started card (spec §13.5); hidden in presentation mode (data-dev). Pages with room for it
 * render it `docked` in their own layout (the dashboard's side column, the workspace's lanes column),
 * so it never floats over cards, the inbox entry, matrix ids or the canvas legend (M4, PR #5
 * follow-up); elsewhere AppShell's floating card is shown.
 */
export function Checklist({ docked = false }: { docked?: boolean }) {
  const done = useChecklist((s) => s.done)
  const dockedCount = useDock((s) => s.docked)
  const [open, setOpen] = useState(true)
  useEffect(() => {
    if (!docked) return
    useDock.getState().add(1)
    return () => useDock.getState().add(-1)
  }, [docked])
  if (!docked && dockedCount > 0) return null
  const count = CHECKLIST.filter((c) => done[c.id]).length
  return (
    <aside
      data-dev
      aria-label="Getting started"
      className={cn(
        'text-sm',
        docked ? 'rounded-lg border bg-card' : 'fixed bottom-14 left-3 z-40 w-64 rounded-lg border bg-popover shadow-xl',
      )}
    >
      <button type="button" aria-expanded={open} onClick={() => setOpen(!open)} className="flex w-full items-center gap-2 px-3 py-2">
        <span className="font-medium">Getting started</span>
        <span className="font-mono text-xs text-zinc-400">
          {count} of {CHECKLIST.length}
        </span>
        <ChevronDown aria-hidden className={cn('ml-auto size-4 text-zinc-500 transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <ul className="flex flex-col gap-1 px-3 pb-3">
          {CHECKLIST.map((c) => (
            <li key={c.id} className={cn('flex items-center gap-2 text-xs', done[c.id] ? 'text-zinc-400 line-through' : 'text-zinc-200')}>
              {done[c.id] ? (
                <CircleCheck aria-label="done" className="size-3.5 shrink-0 text-emerald-400" />
              ) : (
                <Circle aria-label="to do" className="size-3.5 shrink-0 text-zinc-500" />
              )}
              {c.label}
            </li>
          ))}
        </ul>
      )}
    </aside>
  )
}
