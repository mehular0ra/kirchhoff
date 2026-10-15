// IEC-style SLD symbols (IEC 60617-inspired, simplified) as React Flow custom nodes.
import { Handle, Position, type Node, type NodeProps } from '@xyflow/react'
import { cn } from 'cn'
import { memo } from 'react'
import { CHAIN_COLORS } from '@/lib/agents'
import type { ChangeKind } from '@/lib/diff'
import type { Discipline } from '@/lib/model'
import { STATUS_META } from '@/lib/status'
import type { FindingStatus } from '@/lib/types'
import type { SldKind } from './sldGraph'

export interface SldNodeData extends Record<string, unknown> {
  kind: SldKind
  label: string
  sub: string
  status: FindingStatus | null
  change: ChangeKind | null
  resolved: boolean
  chain: Discipline[]
  whatIfStatus: FindingStatus | null
  dim: boolean
  focused: boolean
  /** Accessible name including status (falls back to the label). */
  ariaLabel?: string
  /** Opens the node's worst non-pass finding (falling back to focus) — shared by click and keyboard. */
  activate: () => void
}
export type SldFlowNode = Node<SldNodeData, 'sld'>

const stroke = '#a1a1aa'

function Symbol({ kind }: { kind: SldKind }) {
  switch (kind) {
    case 'mv':
      return (
        <svg aria-hidden viewBox="0 0 120 16" className="h-3 w-full">
          <line x1="2" y1="4" x2="118" y2="4" stroke={stroke} strokeWidth="3" />
          <line x1="2" y1="12" x2="118" y2="12" stroke={stroke} strokeWidth="3" />
        </svg>
      )
    case 'transformer':
      return (
        <svg aria-hidden viewBox="0 0 40 28" className="h-6 w-9">
          <circle cx="14" cy="14" r="10" fill="none" stroke={stroke} strokeWidth="1.8" />
          <circle cx="26" cy="14" r="10" fill="none" stroke={stroke} strokeWidth="1.8" />
        </svg>
      )
    case 'board':
      return (
        <svg aria-hidden viewBox="0 0 60 14" className="h-3 w-14">
          <line x1="2" y1="4" x2="58" y2="4" stroke={stroke} strokeWidth="3.5" />
          {[12, 30, 48].map((x) => (
            <line key={x} x1={x} y1="4" x2={x} y2="13" stroke={stroke} strokeWidth="1.5" />
          ))}
        </svg>
      )
    case 'ups':
      return (
        <svg aria-hidden viewBox="0 0 32 24" className="h-5 w-7">
          <rect x="1" y="1" width="30" height="22" fill="none" stroke={stroke} strokeWidth="1.5" />
          <line x1="1" y1="23" x2="31" y2="1" stroke={stroke} strokeWidth="1" />
          <text x="6" y="10" fontSize="8" fill={stroke}>
            ~
          </text>
          <text x="20" y="20" fontSize="8" fill={stroke}>
            =
          </text>
        </svg>
      )
    case 'sts':
      return (
        <svg aria-hidden viewBox="0 0 32 20" className="h-4 w-7">
          <line x1="2" y1="16" x2="12" y2="16" stroke={stroke} strokeWidth="1.5" />
          <line x1="12" y1="16" x2="26" y2="6" stroke={stroke} strokeWidth="1.5" />
          <line x1="22" y1="16" x2="30" y2="16" stroke={stroke} strokeWidth="1.5" />
        </svg>
      )
    case 'busway':
      return (
        <svg aria-hidden viewBox="0 0 60 14" className="h-3 w-14">
          <rect x="2" y="3" width="56" height="4" fill={stroke} />
          {[10, 22, 34, 46].map((x) => (
            <line key={x} x1={x} y1="7" x2={x} y2="13" stroke={stroke} strokeWidth="1.2" />
          ))}
        </svg>
      )
    case 'rackgroup':
      return (
        <svg aria-hidden viewBox="0 0 48 16" className="h-3.5 w-12">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <rect key={i} x={2 + i * 7.5} y="2" width="5.5" height="12" fill="none" stroke={stroke} strokeWidth="1.2" />
          ))}
        </svg>
      )
  }
}

const CHANGE_TAG: Record<ChangeKind, { text: string; cls: string }> = {
  changed: { text: 'changed', cls: 'border-amber-400/60 text-amber-200' },
  added: { text: 'added', cls: 'border-emerald-400/60 text-emerald-200' },
  removed: { text: 'removed', cls: 'border-rose-400/60 text-rose-200' },
}

function SldNodeImpl({ data }: NodeProps<SldFlowNode>) {
  const st = data.status ? STATUS_META[data.status] : null
  const StIcon = st?.icon
  const ring = data.chain.length ? CHAIN_COLORS[data.chain[0]] : undefined
  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={data.ariaLabel ?? data.label}
      onKeyDown={(e) => {
        if (e.key !== 'Enter' && e.key !== ' ') return
        e.preventDefault() // Space must not scroll the canvas (global constraint: keyboard-reachable controls).
        data.activate()
      }}
      className={cn(
        'flex h-full w-full flex-col items-center justify-center gap-0.5 rounded-md border bg-zinc-950/90 px-2 text-center transition-[opacity,border-color,box-shadow] duration-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-400',
        st ? st.border : 'border-zinc-700',
        data.status === 'fail' && 'shadow-[0_0_14px_rgba(251,113,133,0.45)]',
        data.change === 'changed' && 'border-dashed border-amber-400',
        data.resolved && 'border-emerald-400 shadow-[0_0_14px_rgba(52,211,153,0.4)]',
        data.dim && 'opacity-35',
        data.focused && 'ring-2 ring-sky-400',
      )}
      style={ring ? { boxShadow: `0 0 0 2px ${ring}, 0 0 16px ${ring}` } : undefined}
    >
      <Handle type="target" position={Position.Top} className="!size-1.5 !border-0 !bg-zinc-500" />
      <Symbol kind={data.kind} />
      <span className="font-mono text-[11px] leading-tight text-zinc-100">{data.label}</span>
      {data.sub && <span className="font-mono text-[10px] leading-tight text-zinc-400">{data.sub}</span>}
      <span className="flex flex-wrap justify-center gap-1">
        {st && StIcon && data.status !== 'pass' && (
          <span className={cn('inline-flex items-center gap-0.5 text-[10px]', st.text)}>
            <StIcon aria-hidden className="size-3" />
            {st.label}
          </span>
        )}
        {data.change && (
          <span className={cn('rounded border px-1 text-[10px]', CHANGE_TAG[data.change].cls)}>{CHANGE_TAG[data.change].text}</span>
        )}
        {data.resolved && <span className="rounded border border-emerald-400/60 px-1 text-[10px] text-emerald-200">✓ resolved</span>}
        {data.whatIfStatus && data.whatIfStatus !== 'pass' && (
          <span className="rounded border border-zinc-500 px-1 text-[10px] text-zinc-100">what-if: {STATUS_META[data.whatIfStatus].label}</span>
        )}
      </span>
      <Handle type="source" position={Position.Bottom} className="!size-1.5 !border-0 !bg-zinc-500" />
    </div>
  )
}

export const SldNode = memo(SldNodeImpl)
export const nodeTypes = { sld: SldNode }
