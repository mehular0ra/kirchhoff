// In-house spotlight tour on shadcn Popover (spec §12 libraries, §13.5).
import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router'
import { Button } from '@/components/ui/button'
import { Popover, PopoverAnchor, PopoverContent } from '@/components/ui/popover'
import { useBundleStore } from '@/store/bundles'
import { useUi } from '@/store/ui'
import { useTour } from './tour'
import { TOUR_STEPS } from './tourSteps'

export function TourHost() {
  const { active, step, next, prev, stop } = useTour()
  const navigate = useNavigate()
  const location = useLocation()
  const hallA = useBundleStore((s) => s.entries['hall-a:static']?.bundle ?? null)
  const [rect, setRect] = useState<DOMRect | null>(null)
  const s = TOUR_STEPS[step]
  const ctx = { hallA }
  const route = s.route(ctx)

  // Non-modal focus management: move focus into the popover's primary control on each step
  // (never trapped there — Escape/Skip/clicking elsewhere all still work), and give it back to
  // whatever had focus before the tour started once it stops.
  const openerRef = useRef<HTMLElement | null>(null)
  const wasActive = useRef(false)
  useEffect(() => {
    if (active && !wasActive.current) {
      openerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    }
    if (!active && wasActive.current) {
      const opener = openerRef.current
      openerRef.current = null
      opener?.focus?.()
    }
    wasActive.current = active
  }, [active])

  useEffect(() => {
    if (!active) return
    // Close drawers from the previous step; step 3 re-opens its finding through ?finding=.
    const ui = useUi.getState()
    ui.closeCitation()
    if (s.id !== 'finding') ui.closeFinding()
    if (`${location.pathname}${location.search}` !== route) navigate(route)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, step])

  // Wait (up to ~4 s) for the step's anchor to appear, then spotlight it.
  useEffect(() => {
    if (!active) return
    let raf = 0
    let tries = 0
    setRect(null)
    const find = () => {
      const el = document.querySelector(s.target)
      if (el) {
        el.scrollIntoView({ block: 'center' })
        setRect(el.getBoundingClientRect())
      } else if (tries++ < 240) raf = requestAnimationFrame(find)
    }
    find()
    return () => cancelAnimationFrame(raf)
  }, [active, step, location.key, s.target])

  useEffect(() => {
    if (!active) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight') next()
      if (e.key === 'ArrowLeft') prev()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [active, next, prev])

  if (!active) return null
  const box = rect
    ? { left: rect.left - 6, top: rect.top - 6, width: rect.width + 12, height: rect.height + 12 }
    : { left: window.innerWidth / 2, top: window.innerHeight / 3, width: 1, height: 1 }
  const last = step === TOUR_STEPS.length - 1
  return (
    // Re-keyed when the anchor is found so the popover layer mounts above any drawer opened by the step.
    <Popover open key={`${step}:${rect ? 'found' : 'none'}`}>
      <PopoverAnchor asChild>
        <div data-testid="tour-anchor" className={rect ? 'tour-spotlight' : 'pointer-events-none fixed'} style={box} />
      </PopoverAnchor>
      <PopoverContent
        side="bottom"
        align="start"
        className="z-[70] w-80"
        aria-label="Guided tour"
        onEscapeKeyDown={() => stop(false)}
        onInteractOutside={(e) => e.preventDefault()}
        onOpenAutoFocus={(e) => {
          // Prevent Radix's default (focus the first tabbable) and focus our primary control
          // ourselves on the next frame, once the content (and its buttons) has painted.
          e.preventDefault()
          const container = e.target as HTMLElement
          requestAnimationFrame(() => {
            container.querySelector<HTMLButtonElement>('[data-tour-next]')?.focus()
          })
        }}
      >
        <p className="font-mono text-[11px] text-zinc-500">
          Step {step + 1} of {TOUR_STEPS.length}
        </p>
        <h2 className="mt-1 text-sm font-semibold text-zinc-50">{s.title(ctx)}</h2>
        <p className="mt-1 text-xs text-zinc-300">{s.body}</p>
        {!rect && <p className="mt-1 text-xs text-zinc-500">Loading this part of the workspace…</p>}
        <div className="mt-3 flex items-center gap-2">
          <Button size="xs" variant="ghost" onClick={() => stop(false)}>
            Skip tour
          </Button>
          <Button size="xs" variant="outline" className="ml-auto" disabled={step === 0} onClick={prev}>
            Back
          </Button>
          <Button data-tour-next size="xs" onClick={next}>
            {last ? 'Finish' : 'Next'}
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )
}
