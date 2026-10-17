import { openingCamera, REF_ASPECT } from './hallCamera'

// The opening view frames the whole hall (so its boundary is in the first picture). Tuned for a stage about 1.34 wide for every 1 high;
// a narrower stage is stepped back in proportion so the boundary is not cropped at the sides. Pure arithmetic, tested without WebGL.
const W = 60
const D = 36

test('at the reference aspect, or wider, the camera sits at the tuned opening position', () => {
  const base = openingCamera(W, D, REF_ASPECT)
  expect(base).toEqual([W * 0.62, W * 0.68, D * 1.5])
  expect(openingCamera(W, D, 2.4)).toEqual(base)
})

test('a narrower stage steps the camera back along the same line of sight', () => {
  const base = openingCamera(W, D, REF_ASPECT)
  const narrow = openingCamera(W, D, REF_ASPECT / 1.25)
  const k = narrow[0] / base[0]
  expect(k).toBeCloseTo(1.25, 5)
  expect(narrow[1] / base[1]).toBeCloseTo(k, 5)
  expect(narrow[2] / base[2]).toBeCloseTo(k, 5)
})

test('a very tall, thin stage is capped, so the hall never shrinks to a dot', () => {
  const [x] = openingCamera(W, D, 0.1)
  expect(x / (W * 0.62)).toBeLessThanOrEqual(2.2)
})

test('a bigger hall moves the camera out with it', () => {
  expect(openingCamera(120, 72, REF_ASPECT)[0]).toBe(2 * openingCamera(60, 36, REF_ASPECT)[0])
})
