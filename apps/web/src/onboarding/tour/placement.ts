// Where the tour's spotlight and card go (C1, GitHub issue #10): the spotlight is the target's rect
// clamped to the viewport; the card takes the preferred side if it fits there, else the first side
// that does, else floats at the bottom of the screen over the spotlight. Never off-screen.

export type Side = 'top' | 'right' | 'bottom' | 'left'
export interface Box {
  left: number
  top: number
  width: number
  height: number
}
interface Viewport {
  w: number
  h: number
}

const PAD = 6 // spotlight padding around the target
const EDGE = 4 // spotlight never closer than this to the viewport edge
const CARD_W = 280 // w-80 at the 14 px root size
const CARD_H = 170 // tallest card (title wraps on two lines) plus margin
const GAP = 16 // sideOffset plus collision padding
const MIN_CARD_TOP = 32 // below the fictional-data banner

/** The padded spotlight clamped to the visible viewport, or null when the target is entirely off-screen. */
export function spotlightBox(r: Box, vp: Viewport): Box | null {
  const left = Math.max(r.left - PAD, EDGE)
  const top = Math.max(r.top - PAD, EDGE)
  const right = Math.min(r.left + r.width + PAD, vp.w - EDGE)
  const bottom = Math.min(r.top + r.height + PAD, vp.h - EDGE)
  if (right <= left || bottom <= top) return null
  return { left, top, width: right - left, height: bottom - top }
}

const OPPOSITE: Record<Side, Side> = { top: 'bottom', bottom: 'top', left: 'right', right: 'left' }

export function cardPlacement(spot: Box, preferred: Side, vp: Viewport): { side: Side; anchor: Box; floating: boolean } {
  const room: Record<Side, number> = {
    left: spot.left,
    right: vp.w - (spot.left + spot.width),
    top: spot.top,
    bottom: vp.h - (spot.top + spot.height),
  }
  const fits = (side: Side) => room[side] >= (side === 'left' || side === 'right' ? CARD_W : CARD_H) + GAP
  const side = [preferred, OPPOSITE[preferred], 'bottom', 'top', 'right', 'left'].find((x) => fits(x as Side)) as Side | undefined
  if (side) return { side, anchor: spot, floating: false }
  // No room beside the target (it fills the screen): pin the card to the bottom edge, over the spotlight.
  return { side: 'top', anchor: { left: Math.max(EDGE, Math.min(spot.left + 12, vp.w - CARD_W - 12)), top: vp.h - 12, width: 1, height: 1 }, floating: true }
}

/**
 * The card's placement when a step names a separate `cardTarget` (UX-1 D3): tour step 3 spotlights the
 * tender chip inside the finding drawer, but its card goes beside the drawer so it never covers the
 * value-vs-limit bar and formula the step is about. When the card target leaves no room (the drawer is
 * full width on a phone), it falls back to the spotlight.
 */
export function placeCard(spot: Box, cardSpot: Box | null, preferred: Side, vp: Viewport): ReturnType<typeof cardPlacement> {
  if (cardSpot) {
    const p = cardPlacement(cardSpot, preferred, vp)
    if (!p.floating && p.side === preferred) {
      if (p.side === 'top' || p.side === 'bottom') return p
      // Beside a tall card target (the drawer), level the card with the spotlit chip (N2) instead of the target's
      // top (y=12, over the fictional-data banner); never above MIN_CARD_TOP, never past the bottom edge.
      const top = Math.max(MIN_CARD_TOP, Math.min(spot.top, vp.h - CARD_H - EDGE))
      return { ...p, anchor: { left: cardSpot.left, top, width: cardSpot.width, height: 1 } }
    }
  }
  return cardPlacement(spot, preferred, vp)
}
