import { Archive, Circle, CircleCheck, Eye, FileText, LoaderCircle, Stamp, type LucideIcon } from 'lucide-react'
import { cn } from 'cn'
import type { ProjectState } from '@/lib/types'

const META: Record<ProjectState, { label: string; icon: LucideIcon; cls: string }> = {
  not_started: { label: 'Not started', icon: Circle, cls: 'text-zinc-400' },
  running: { label: 'Running', icon: LoaderCircle, cls: 'text-sky-300' },
  in_review: { label: 'In review', icon: Eye, cls: 'text-amber-300' },
  checked: { label: 'Checked', icon: CircleCheck, cls: 'text-emerald-400' },
  draft: { label: 'Draft', icon: FileText, cls: 'text-zinc-300' },
  signed: { label: 'Signed', icon: Stamp, cls: 'text-emerald-300' },
  archived: { label: 'Archived', icon: Archive, cls: 'text-zinc-400' },
}

export function ProjectStateBadge({ state, className }: { state: ProjectState; className?: string }) {
  const m = META[state]
  const Icon = m.icon
  return (
    <span className={cn('inline-flex items-center gap-1 text-xs font-medium', m.cls, className)}>
      <Icon aria-hidden className={cn('size-3.5', state === 'running' && 'animate-spin motion-reduce:animate-none')} />
      {m.label}
    </span>
  )
}
