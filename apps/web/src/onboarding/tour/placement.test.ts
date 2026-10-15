import { cardPlacement, placeCard, spotlightBox } from './placement'

const desk = { w: 1440, h: 900 }
const phone = { w: 412, h: 915 }
const box = (left: number, top: number, width: number, height: number) => ({ left, top, width, height })

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

test('D3 step 3 on a phone: the drawer fills the width, so the card falls back to the chip (below it)', () => {
  const chip = box(172, 148, 105, 33)
  const drawer = box(0, 0, 412, 915)
  const p = placeCard(chip, drawer, 'left', phone)
  expect(p).toMatchObject({ side: 'bottom', floating: false })
  expect(p.anchor).toEqual(chip)
})

test('D3: without a card target the card is placed against the spotlight as before', () => {
  const chip = box(1200, 148, 105, 33)
  expect(placeCard(chip, null, 'left', desk)).toEqual(cardPlacement(chip, 'left', desk))
})
