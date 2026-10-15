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
