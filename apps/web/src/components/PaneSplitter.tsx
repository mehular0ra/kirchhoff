// The draggable edge between two panes: a vertical separator (ARIA window splitter) that resizes the pane beside it with
// the pointer or the keyboard. The pane's width lives in the caller's store; this only says what the new width is.
import { cn } from 'cn'
import { useRef, type KeyboardEvent, type PointerEvent } from 'react'

const STEP = 16
const BIG_STEP = 64

interface Props {
  label: string
  /** The pane's width now, in px. */
  value: number
  min: number
  max: number
  /** 1 when dragging right makes the pane wider (a pane on the left), -1 when dragging left does (a pane on the right). */
  grow: 1 | -1
  onChange(px: number): void
  onReset(): void
  className?: string
}

export function PaneSplitter({ label, value, min, max, grow, onChange, onReset, className }: Props) {
  const drag = useRef<{ x: number; width: number } | null>(null)
  const clamp = (n: number) => Math.min(max, Math.max(min, n))

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
      e.preventDefault()
      onChange(clamp(value + grow * (e.key === 'ArrowRight' ? 1 : -1) * (e.shiftKey ? BIG_STEP : STEP)))
    } else if (e.key === 'Home') {
      e.preventDefault()
      onChange(min)
    } else if (e.key === 'End') {
      e.preventDefault()
      onChange(max)
    } else if (e.key === 'Enter') {
      e.preventDefault()
      onReset()
    }
  }
  const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
    drag.current = { x: e.clientX, width: value }
    e.currentTarget.setPointerCapture?.(e.pointerId)
  }
  const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
    const d = drag.current
    if (d) onChange(clamp(d.width + grow * (e.clientX - d.x)))
  }
  const onPointerEnd = (e: PointerEvent<HTMLDivElement>) => {
    drag.current = null
    e.currentTarget.releasePointerCapture?.(e.pointerId)
  }

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      aria-valuenow={value}
      aria-valuemin={min}
      aria-valuemax={max}
      tabIndex={0}
      title="Drag to resize. Arrow keys also work; double-click or Enter to reset."
      onKeyDown={onKeyDown}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerEnd}
      onPointerCancel={onPointerEnd}
      onDoubleClick={onReset}
      className={cn(
        'group relative z-10 flex w-1.5 shrink-0 cursor-col-resize touch-none select-none items-stretch justify-center outline-none',
        'hover:bg-blue-500/20 focus-visible:bg-blue-500/25 focus-visible:ring-2 focus-visible:ring-blue-600 active:bg-blue-500/30',
        className,
      )}
    >
      <span aria-hidden className="w-px bg-border group-hover:bg-blue-500/60 group-focus-visible:bg-blue-600" />
    </div>
  )
}
