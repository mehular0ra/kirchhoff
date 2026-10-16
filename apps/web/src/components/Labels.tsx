import { cn } from 'cn'
import { CircleX, FlaskConical, Info, LoaderCircle, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { AGENTS } from '@/lib/agents'
import type { AgentName } from '@/lib/types'

export const FICTIONAL_TEXT = 'Demo workspace — all companies, people and data are fictional'
export const SANDBOX_TEXT = 'sandbox (simulated)'
export const ILLUSTRATIVE_TEXT = 'IEC-based, illustrative values, not for construction'

export function DemoBanner() {
  return (
    <div
      role="note"
      className="flex items-center justify-center gap-2 border-b border-amber-200 bg-amber-50 px-4 py-1 text-xs text-amber-800"
    >
      <Info aria-hidden className="size-3.5" />
      {FICTIONAL_TEXT}
    </div>
  )
}

export function SandboxLabel({ className }: { className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-1 rounded bg-zinc-100 px-1.5 py-0.5 text-[11px] text-zinc-700', className)}>
      <FlaskConical aria-hidden className="size-3" />
      {SANDBOX_TEXT}
    </span>
  )
}

export function IllustrativeLabel({ className }: { className?: string }) {
  return <span className={cn('text-[11px] uppercase tracking-wide text-muted-foreground', className)}>{ILLUSTRATIVE_TEXT}</span>
}

export function AgentDot({ agent, className }: { agent: AgentName; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn('inline-block size-2 shrink-0 rounded-full', className)}
      style={{ background: AGENTS[agent].color }}
    />
  )
}

/** Monospace, tabular number with optional unit. Pass already-formatted text. */
export function Num({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cn('font-mono tabular-nums', className)}>{children}</span>
}

const EMPTY_TONE: Record<'info' | 'error' | 'loading', { icon: LucideIcon; cls: string; well: string }> = {
  info: { icon: Info, cls: 'text-muted-foreground', well: 'bg-muted' },
  error: { icon: CircleX, cls: 'text-rose-700', well: 'bg-rose-50' },
  loading: { icon: LoaderCircle, cls: 'animate-spin text-muted-foreground motion-reduce:animate-none', well: 'bg-muted' },
}

/** Empty, loading and error states: always an icon with the text (status is never colour alone, M1). */
export function EmptyState({
  title,
  children,
  action,
  tone,
  icon,
}: {
  title: string
  children?: ReactNode
  action?: ReactNode
  /** Defaults to "loading" for "Loading…" titles, else "info". */
  tone?: 'info' | 'error' | 'loading'
  icon?: LucideIcon
}) {
  const t = tone ?? (title.startsWith('Loading') ? 'loading' : 'info')
  const Icon = icon ?? EMPTY_TONE[t].icon
  return (
    <div
      data-tone={t}
      role={t === 'loading' ? 'status' : undefined}
      className="flex h-full min-h-40 flex-col items-center justify-center gap-2 p-6 text-center"
    >
      <span aria-hidden className={cn('mb-1 grid size-10 place-items-center rounded-full', EMPTY_TONE[t].well)}>
        <Icon aria-hidden className={cn('size-5', EMPTY_TONE[t].cls)} />
      </span>
      <p className="text-sm font-medium text-foreground">{title}</p>
      {children && <div className="max-w-md text-sm text-muted-foreground">{children}</div>}
      {action}
    </div>
  )
}
