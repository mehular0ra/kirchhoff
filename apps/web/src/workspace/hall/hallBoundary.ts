// The hall's boundary in scene coordinates (metres, the floor plane centred on the origin, y up): a closed outline drawn on the floor
// and four low perimeter walls. Pure geometry; the colours and materials live in HallView.
export type V3 = [number, number, number]
export interface BoundaryWall {
  id: 'north' | 'south' | 'east' | 'west'
  center: V3
  size: V3
}

/** Wall height and thickness: low enough to leave the hall readable from the default camera. */
export const WALL_H = 0.5
export const WALL_T = 0.3

/** The footprint as a closed loop (first point repeated), a hair above the floor so it never z-fights with it. */
export function boundaryLoop(w: number, d: number, y = 0.03): V3[] {
  const x = w / 2
  const z = d / 2
  return [
    [-x, y, -z],
    [x, y, -z],
    [x, y, z],
    [-x, y, z],
    [-x, y, -z],
  ]
}

/** North and south walls span the full width plus the corners; east and west stop at them, so the corners are not drawn twice. */
export function boundaryWalls(w: number, d: number): BoundaryWall[] {
  const y = WALL_H / 2
  return [
    { id: 'north', center: [0, y, -d / 2], size: [w + WALL_T, WALL_H, WALL_T] },
    { id: 'south', center: [0, y, d / 2], size: [w + WALL_T, WALL_H, WALL_T] },
    { id: 'west', center: [-w / 2, y, 0], size: [WALL_T, WALL_H, d - WALL_T] },
    { id: 'east', center: [w / 2, y, 0], size: [WALL_T, WALL_H, d - WALL_T] },
  ]
}
