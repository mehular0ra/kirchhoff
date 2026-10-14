import { ChevronDown, Circle, CircleCheck } from 'lucide-react'
import { useState } from 'react'
import { cn } from 'cn'
import { CHECKLIST, useChecklist } from './checklistStore'

/** Bottom-left getting-started card; hidden in presentation mode (data-dev). */
export function Checklist() {
  const done = useChecklist((s) => s.done)
  const [open, setOpen] = useState(true)
  const count = CHECKLIST.filter((c) => done[c.id]).length
  return (
    <aside data-dev aria-label="Getting started" className="fixed bottom-14 left-3 z-40 w-64 rounded-lg border bg-popover text-sm shadow-xl">
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
                <CircleCheck aria-label="done" className="size-3.5 text-emerald-400" />
              ) : (
                <Circle aria-label="to do" className="size-3.5 text-zinc-500" />
              )}
              {c.label}
            </li>
          ))}
        </ul>
      )}
    </aside>
  )
}
