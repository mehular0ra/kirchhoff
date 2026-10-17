import * as THREE from 'three'

// The opening view of the 3D hall. It frames the whole hall so its boundary is in the first picture; the position was tuned on a stage about
// 1.34 wide for every 1 high. A narrower stage is stepped back along the same line of sight in proportion, so the boundary is not cropped at
// the sides, up to a cap so a very thin stage never shrinks the hall to a dot.
export const REF_ASPECT = 1.34
const MAX_STEP_BACK = 2.2

export type Vec3 = [number, number, number]

export function openingCamera(w: number, d: number, aspect: number): Vec3 {
  const k = Math.min(MAX_STEP_BACK, Math.max(1, REF_ASPECT / Math.max(aspect, 0.3)))
  return [w * 0.62 * k, w * 0.68 * k, d * 1.5 * k]
}

/**
 * Pans the camera and its orbit target together, in the camera's own right and up directions, until the hall's outline (its four floor corners) is centred in
 * the frame: the same margin above and below, and left and right. A hall seen from above and in front otherwise sits low, with empty stage above it.
 * Only a pan: the view direction and the distance do not change, so the framing set by `openingCamera` still holds. A pan shifts perspective a little, so it
 * repeats a few times until the centre is within a thousandth of the frame.
 */
export function centreHall(camera: THREE.PerspectiveCamera, target: THREE.Vector3, w: number, d: number, iterations = 6): void {
  const corners = [
    [-w / 2, 0, -d / 2],
    [w / 2, 0, -d / 2],
    [w / 2, 0, d / 2],
    [-w / 2, 0, d / 2],
  ].map(([x, y, z]) => new THREE.Vector3(x, y, z))
  const p = new THREE.Vector3()
  const right = new THREE.Vector3()
  const up = new THREE.Vector3()
  for (let i = 0; i < iterations; i++) {
    camera.lookAt(target)
    camera.updateMatrixWorld()
    camera.updateProjectionMatrix()
    let minX = Infinity
    let maxX = -Infinity
    let minY = Infinity
    let maxY = -Infinity
    for (const c of corners) {
      p.copy(c).project(camera)
      minX = Math.min(minX, p.x)
      maxX = Math.max(maxX, p.x)
      minY = Math.min(minY, p.y)
      maxY = Math.max(maxY, p.y)
    }
    const cx = (minX + maxX) / 2
    const cy = (minY + maxY) / 2
    if (Math.abs(cx) < 1e-3 && Math.abs(cy) < 1e-3) break
    // How far one unit of the frame is in the world, at the target's distance, then a pan along the camera's own axes.
    const halfHeight = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * camera.position.distanceTo(target)
    right.setFromMatrixColumn(camera.matrixWorld, 0).multiplyScalar(cx * halfHeight * camera.aspect)
    up.setFromMatrixColumn(camera.matrixWorld, 1).multiplyScalar(cy * halfHeight)
    camera.position.add(right).add(up)
    target.add(right).add(up)
  }
  camera.lookAt(target)
  camera.updateMatrixWorld()
}
