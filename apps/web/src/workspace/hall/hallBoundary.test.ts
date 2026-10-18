import { boundaryLoop, boundaryWalls, WALL_H, WALL_T } from './hallBoundary'

// The hall boundary: a closed outline on the floor and four low perimeter walls, in the scene's coordinates (floor plane centred on
// the origin, metres, y up). Pure geometry, so it is tested without WebGL.
const W = 60
const D = 36

test('the outline is a closed rectangle at the hall footprint, just above the floor', () => {
  const loop = boundaryLoop(W, D)
  expect(loop).toHaveLength(5)
  expect(loop[0]).toEqual(loop[4])
  expect(loop.map(([x]) => Math.abs(x))).toEqual([W / 2, W / 2, W / 2, W / 2, W / 2])
  expect(loop.map(([, , z]) => Math.abs(z))).toEqual([D / 2, D / 2, D / 2, D / 2, D / 2])
  for (const [, y] of loop) expect(y).toBeGreaterThan(0)
  for (const [, y] of loop) expect(y).toBeLessThan(0.1)
})

test('four perimeter walls sit on the boundary, low, and together span the whole footprint', () => {
  const walls = boundaryWalls(W, D)
  expect(walls.map((w) => w.id).sort()).toEqual(['east', 'north', 'south', 'west'])
  for (const w of walls) {
    expect(w.size[1]).toBe(WALL_H)
    expect(w.center[1]).toBe(WALL_H / 2) // resting on the floor
  }
  const ns = walls.filter((w) => w.id === 'north' || w.id === 'south')
  const ew = walls.filter((w) => w.id === 'east' || w.id === 'west')
  for (const w of ns) {
    expect(Math.abs(w.center[2])).toBe(D / 2)
    expect(w.size[0]).toBe(W + WALL_T) // the long walls cover the corners
  }
  for (const w of ew) {
    expect(Math.abs(w.center[0])).toBe(W / 2)
    expect(w.size[2]).toBe(D - WALL_T) // the short walls stop at the long ones, so the corners are not drawn twice
  }
})

test('a different hall size moves the boundary with it', () => {
  const [a, b] = [boundaryLoop(20, 10), boundaryLoop(40, 10)]
  expect(Math.max(...a.map(([x]) => x))).toBe(10)
  expect(Math.max(...b.map(([x]) => x))).toBe(20)
})
