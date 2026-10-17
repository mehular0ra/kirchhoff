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
