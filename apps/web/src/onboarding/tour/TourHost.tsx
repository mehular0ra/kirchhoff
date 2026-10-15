// In-house spotlight tour on shadcn Popover (spec §12 libraries, §13.5).
import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router'
import { Button } from '@/components/ui/button'
import { Popover, PopoverAnchor, PopoverContent } from '@/components/ui/popover'
import { useBundleStore } from '@/store/bundles'
import { useUi } from '@/store/ui'
import { useTour } from './tour'
import { placeCard, spotlightBox } from './placement'
import { stepBody, TOUR_STEPS } from './tourSteps'

const STABLE_FRAMES = 8 // consecutive identical rects before tracking stops
const MIN_TRACK_MS = 600 // keep measuring at least this long after the target appears
const FIND_FRAMES = 600 // ~10 s of frames waiting for the anchor to mount
const sameRect = (a: DOMRect, b: DOMRect) =>
  Math.abs(a.left - b.left) < 0.5 && Math.abs(a.top - b.top) < 0.5 && Math.abs(a.width - b.width) < 0.5 && Math.abs(a.height - b.height) < 0.5

export function TourHost() {
  const { active, step, next, prev, stop } = useTour()
  const navigate = useNavigate()
  const location = useLocation()
  const hallA = useBundleStore((s) => s.entries['hall-a:static']?.bundle ?? null)
  const [rect, setRect] = useState<DOMRect | null>(null)
  const [cardRect, setCardRect] = useState<DOMRect | null>(null)
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, step])

  // Navigate to the step's route, and again if the route itself changes while the step is open
  // (step 3's ?finding= is only known once Hall A's bundle has loaded — e.g. after a reload mid-tour).
  useEffect(() => {
    if (!active) return
    if (`${location.pathname}${location.search}` !== route) navigate(route)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, step, route])

  // Wait (up to ~10 s) for the step's anchor, then keep measuring it every frame until its rect has
  // been stable for a while: the target may still be sliding in (step 3's chip sits in a Sheet that
  // animates from the right), and measuring only the first frame left the spotlight off-screen (C1).
  // Afterwards, resize/scroll/transition/animation ends and target resizes trigger a re-measure.
  useEffect(() => {
    if (!active) return
    let raf = 0
    let tries = 0
    let el: Element | null = null
    let last: DOMRect | null = null
    let lastCard: DOMRect | null = null
    let stable = 0
    let foundAt = 0
    let ro: ResizeObserver | null = null
    setRect(null)
    setCardRect(null)
    // The card's own anchor (D3), measured alongside the target: the drawer slides in with the chip.
    const cardBox = () => (s.cardTarget ? (document.querySelector(s.cardTarget)?.getBoundingClientRect() ?? null) : null)
    const track = () => {
      if (!el?.isConnected) {
        el = null
        last = null
        tries = 0
        raf = requestAnimationFrame(find)
        return
      }
      const r = el.getBoundingClientRect()
      const cr = cardBox()
      const cardSame = cr === lastCard || (!!cr && !!lastCard && sameRect(cr, lastCard))
      if (last && sameRect(r, last) && cardSame) stable += 1
      else {
        last = r
        lastCard = cr
        stable = 0
        setRect(r)
        setCardRect(cr)
      }
      if (stable < STABLE_FRAMES || performance.now() - foundAt < MIN_TRACK_MS) raf = requestAnimationFrame(track)
    }
    const find = () => {
      el = document.querySelector(s.target)
      if (el) {
        const r = el.getBoundingClientRect()
        el.scrollIntoView({ block: r.height > window.innerHeight * 0.8 ? 'start' : 'center' })
        foundAt = performance.now()
        stable = 0
        ro?.disconnect()
        ro = new ResizeObserver(remeasure)
        ro.observe(el)
        track()
      } else if (tries++ < FIND_FRAMES) raf = requestAnimationFrame(find)
    }
    const remeasure = () => {
      if (!el) return
      cancelAnimationFrame(raf)
      stable = 0
      foundAt = performance.now()
      raf = requestAnimationFrame(track)
    }
    window.addEventListener('resize', remeasure)
    window.addEventListener('scroll', remeasure, true)
    document.addEventListener('transitionend', remeasure, true)
    document.addEventListener('animationend', remeasure, true)
    find()
    return () => {
      cancelAnimationFrame(raf)
      ro?.disconnect()
      window.removeEventListener('resize', remeasure)
      window.removeEventListener('scroll', remeasure, true)
      document.removeEventListener('transitionend', remeasure, true)
      document.removeEventListener('animationend', remeasure, true)
    }
  }, [active, step, location.key, s.target, s.cardTarget])

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
  const vp = { w: window.innerWidth, h: window.innerHeight }
  const spot = rect ? spotlightBox(rect, vp) : null
  const cardSpot = cardRect ? spotlightBox(cardRect, vp) : null
  const place = spot ? placeCard(spot, cardSpot, s.side ?? 'bottom', vp) : null
  const box = spot ?? { left: vp.w / 2, top: vp.h / 3, width: 1, height: 1 }
  const last = step === TOUR_STEPS.length - 1
  return (
    // Re-keyed when the anchor is found so the popover layer mounts above any drawer opened by the step.
    <Popover open key={`${step}:${spot ? 'found' : 'none'}`}>
      <div data-testid="tour-anchor" className={spot ? 'tour-spotlight' : 'pointer-events-none fixed'} style={box} />
      <PopoverAnchor asChild>
        <div data-testid="tour-card-anchor" aria-hidden className="pointer-events-none fixed" style={place?.anchor ?? box} />
      </PopoverAnchor>
      <PopoverContent
        side={place?.side ?? 'bottom'}
        align="start"
        // Never leave the viewport (C1): clamp inside a 12 px margin even if the anchor is partly off-screen.
        collisionPadding={12}
        sticky="always"
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
        <p className="font-mono text-[11px] text-muted-foreground">
          Step {step + 1} of {TOUR_STEPS.length}
        </p>
        <h2 className="mt-1 text-sm font-semibold text-foreground">{s.title(ctx)}</h2>
        <p className="mt-1 text-xs text-zinc-700">{stepBody(s, ctx)}</p>
        {!rect && <p className="mt-1 text-xs text-muted-foreground">Loading this part of the workspace…</p>}
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
