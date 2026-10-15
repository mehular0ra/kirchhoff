import { cardPlacement, spotlightBox } from './placement'

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
