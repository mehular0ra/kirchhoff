import * as THREE from 'three'
import { centreHall, openingCamera, REF_ASPECT } from './hallCamera'

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

// Centring: the opening view looks at the orbit controls' target (0, 1.5, 0), and a hall seen from above and in front fills the lower half of the frame,
// with empty stage above it. `centreHall` pans the camera and its target together until the hall's outline has the same margin above and below, and left and right.
const TARGET = () => new THREE.Vector3(0, 1.5, 0) // the orbit controls' default target in HallView
function frame(aspect: number) {
  const camera = new THREE.PerspectiveCamera(40, aspect, 0.1, 500)
  camera.position.set(...openingCamera(W, D, aspect))
  const target = TARGET()
  return { camera, target }
}
/** The hall's four floor corners in the frame, in normalised device coordinates: -1..1 across and up. */
function outline(camera: THREE.PerspectiveCamera, target: THREE.Vector3) {
  camera.lookAt(target)
  camera.updateMatrixWorld()
  camera.updateProjectionMatrix()
  const pts = [
    [-W / 2, 0, -D / 2],
    [W / 2, 0, -D / 2],
    [W / 2, 0, D / 2],
    [-W / 2, 0, D / 2],
  ].map(([x, y, z]) => new THREE.Vector3(x, y, z).project(camera))
  const xs = pts.map((p) => p.x)
  const ys = pts.map((p) => p.y)
  return { minX: Math.min(...xs), maxX: Math.max(...xs), minY: Math.min(...ys), maxY: Math.max(...ys) }
}
const centreOf = (o: ReturnType<typeof outline>) => ({ x: (o.minX + o.maxX) / 2, y: (o.minY + o.maxY) / 2 })

describe.each([REF_ASPECT, 1.17, 1, 0.8, 2])('centreHall at a stage aspect of %s', (aspect) => {
  test('the hall outline ends up centred: equal margins above and below, left and right', () => {
    const { camera, target } = frame(aspect)
    centreHall(camera, target, W, D)
    const c = centreOf(outline(camera, target))
    expect(Math.abs(c.x)).toBeLessThan(0.01)
    expect(Math.abs(c.y)).toBeLessThan(0.01)
  })

  test('the whole outline is in the frame, so no corner of the boundary is cropped', () => {
    const { camera, target } = frame(aspect)
    centreHall(camera, target, W, D)
    const o = outline(camera, target)
    expect(Math.max(Math.abs(o.minX), Math.abs(o.maxX), Math.abs(o.minY), Math.abs(o.maxY))).toBeLessThanOrEqual(1)
  })

  test('it only pans: the view direction is unchanged and the target moves by a small part of the hall', () => {
    const { camera, target } = frame(aspect)
    camera.lookAt(target)
    const before = camera.getWorldDirection(new THREE.Vector3()).clone()
    const from = target.clone()
    centreHall(camera, target, W, D)
    expect(camera.getWorldDirection(new THREE.Vector3()).distanceTo(before)).toBeLessThan(1e-6)
    expect(target.distanceTo(from)).toBeLessThan(0.25 * Math.max(W, D))
  })
})

test('before centring, the hall sits low in a typical stage (this is what centreHall fixes)', () => {
  const { camera, target } = frame(1.17)
  expect(centreOf(outline(camera, target)).y).toBeLessThan(-0.08)
})
