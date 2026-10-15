import { CARD_H, CARD_W, cardPlacement, placeCard, spotlightBox, type Box } from './placement'

const desk = { w: 1440, h: 900 }
const phone = { w: 412, h: 915 }
const box = (left: number, top: number, width: number, height: number) => ({ left, top, width, height })

/**
 * The card's own rendered rect for a `{ side, anchor }` placement, approximating how Radix's Popover
 * lays it out (align="start", the preferred side, a small gap) — enough to assert the card doesn't land
 * on top of another rect, which the exact pixel count from a headless run can't check on its own.
 */
function renderedCardBox(place: { side: 'top' | 'right' | 'bottom' | 'left'; anchor: Box }): Box {
  const { side, anchor } = place
  if (side === 'top') return { left: anchor.left, top: anchor.top - CARD_H - 8, width: CARD_W, height: CARD_H }
  if (side === 'bottom') return { left: anchor.left, top: anchor.top + anchor.height + 8, width: CARD_W, height: CARD_H }
  if (side === 'left') return { left: anchor.left - CARD_W - 8, top: anchor.top, width: CARD_W, height: CARD_H }
  return { left: anchor.left + anchor.width + 8, top: anchor.top, width: CARD_W, height: CARD_H }
}

function overlaps(a: Box, b: Box): boolean {
  return a.left < b.left + b.width && a.left + a.width > b.left && a.top < b.top + b.height && a.top + a.height > b.top
}

test('issue #10 step 3: a chip near the right edge on a phone gets the card below it, not off-screen to the left', () => {
  expect(cardPlacement(box(172, 148, 105, 33), 'left', phone).side).toBe('bottom')
  expect(cardPlacement(box(1200, 148, 105, 33), 'left', desk).side).toBe('left') // room on desktop
})

test('issue #10 step 4: the full-height lanes column keeps the card to its right on desktop and floats it on a phone', () => {
  expect(cardPlacement(box(4, 93, 225, 775), 'right', desk)).toMatchObject({ side: 'right', floating: false })
  const p = cardPlacement(box(4, 93, 225, 790), 'right', phone)
  expect(p.floating).toBe(true)
  // Anchored at the bottom of the screen, card above it: always inside the viewport.
  expect(p.side).toBe('top')
  expect(p.anchor.top).toBeLessThanOrEqual(phone.h)
})

test('issue #10 step 1: a target taller than the screen is clamped, and the card still finds room', () => {
  const s = spotlightBox({ left: 181, top: -518, width: 805, height: 1997 }, desk)!
  expect(s.top).toBeGreaterThanOrEqual(0)
  expect(s.top + s.height).toBeLessThanOrEqual(desk.h)
  expect(cardPlacement(s, 'bottom', desk)).toMatchObject({ side: 'right', floating: false }) // beside it, on screen
  expect(cardPlacement(box(175, 193, 817, 292), 'bottom', desk)).toMatchObject({ side: 'bottom', floating: false })
})

test('D3 step 3: with the drawer as the card target, the card sits left of the drawer (over the dimmed matrix), not on the evidence', () => {
  const chip = box(1200, 148, 105, 33)
  const drawer = box(992, 0, 448, 900)
  const p = placeCard(chip, drawer, 'left', desk)
  expect(p).toMatchObject({ side: 'left', floating: false })
  // laid out against the drawer's left edge (never over it), its top level with the chip's (N2), not pinned to y=12
  expect(p.anchor.left).toBe(drawer.left)
  expect(p.anchor.top).toBe(chip.top)
})

test('N2: the card beside a card target never rides up over the banner and header (at least 32 px down)', () => {
  const chipNearTop = box(1200, 6, 105, 33)
  const drawer = box(992, 0, 448, 900)
  expect(placeCard(chipNearTop, drawer, 'left', desk).anchor.top).toBeGreaterThanOrEqual(32)
})

test('N2: a chip low on the screen keeps the card fully inside the viewport', () => {
  const chipLow = box(1200, 860, 105, 33)
  const drawer = box(992, 0, 448, 900)
  const p = placeCard(chipLow, drawer, 'left', desk)
  expect(p.anchor.top + 170).toBeLessThanOrEqual(desk.h)
})

test('N9 step 3 on a phone: the drawer fills the width, so the card pins to the bottom edge, clear of the chip, the value bar and the formula', () => {
  const chip = box(172, 148, 105, 33)
  const drawer = box(0, 0, 412, 915)
  const p = placeCard(chip, drawer, 'left', phone)
  expect(p).toMatchObject({ side: 'top', floating: true })
  expect(p.anchor.top).toBe(phone.h - 12)
  // Not pinned under the banner (that regression covered the chip itself, N9 follow-up): the rendered
  // card must not overlap the tender chip the step tells the visitor to click.
  const card = renderedCardBox(p)
  expect(overlaps(card, chip)).toBe(false)
  // nor the rest of the drawer's evidence further down (the value bar, formula and fix cards end ~y 620).
  expect(overlaps(card, box(0, 150, 412, 470))).toBe(false)
})

test('N9: the same full-width-drawer fallback applies at 390 px wide, and the card stays clear of the chip', () => {
  const narrow = { w: 390, h: 844 }
  const chip = box(150, 185, 105, 33)
  const drawer = box(0, 0, 390, 844)
  const p = placeCard(chip, drawer, 'left', narrow)
  expect(p).toMatchObject({ side: 'top', floating: true })
  expect(p.anchor.top).toBe(narrow.h - 12)
  expect(p.anchor.left).toBeGreaterThanOrEqual(0)
  expect(p.anchor.left + p.anchor.width).toBeLessThanOrEqual(narrow.w)
  const card = renderedCardBox(p)
  expect(overlaps(card, chip)).toBe(false)
  expect(overlaps(card, box(0, 150, 390, 470))).toBe(false)
})

test('D3: without a card target the card is placed against the spotlight as before', () => {
  const chip = box(1200, 148, 105, 33)
  expect(placeCard(chip, null, 'left', desk)).toEqual(cardPlacement(chip, 'left', desk))
})
