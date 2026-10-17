import { AREAS, SHOT } from './shotAreas'

// The three legend cards (Agent lanes, 3D hall, Co-pilot) light up the matching area of the hero screenshot on hover. The areas are measured on the real layout at
// the width the screenshot was captured at, so they must tile the picture's width exactly and stay inside it.

const n = (pct: string) => Number.parseFloat(pct)

test('the capture size is the one the hero image was taken at (1000 x 625, 16:10), so the percentages map onto the picture', () => {
  expect(SHOT.w / SHOT.h).toBe(1.6)
})

test('the three areas are the real columns of the workspace at that width: 224, 496 and 280 px of 1000', () => {
  expect([AREAS.left, AREAS.centre, AREAS.right].map((a) => n(a.width))).toEqual([22.4, 49.6, 28])
})

test('together they tile the width of the picture: no gap and no overlap, from the left edge to the right edge', () => {
  expect(n(AREAS.left.left)).toBe(0)
  expect(n(AREAS.centre.left)).toBeCloseTo(n(AREAS.left.left) + n(AREAS.left.width), 2)
  expect(n(AREAS.right.left)).toBeCloseTo(n(AREAS.centre.left) + n(AREAS.centre.width), 2)
  expect(n(AREAS.right.left) + n(AREAS.right.width)).toBeCloseTo(100, 2)
})

test('they share one band, below the app header and above the revisions bar, and inside the picture', () => {
  const tops = new Set([AREAS.left.top, AREAS.centre.top, AREAS.right.top])
  const heights = new Set([AREAS.left.height, AREAS.centre.height, AREAS.right.height])
  expect(tops.size).toBe(1)
  expect(heights.size).toBe(1)
  expect(n(AREAS.left.top)).toBeCloseTo((99 / 625) * 100, 1)
  expect(n(AREAS.left.top) + n(AREAS.left.height)).toBeLessThan(100)
})
