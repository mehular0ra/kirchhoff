import { useLayoutEffect, useRef, type RefObject } from 'react'
import { useLiveGeometry, type Disposable } from './useLiveGeometry'
import type { V3 } from './hallScene'

const EASE_MS = 900
const ease = (k: number): number => (k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2)
const samePoints = (a: V3[], b: V3[]): boolean =>
  a.length === b.length && a.every((p, i) => p[0] === b[i][0] && p[1] === b[i][1] && p[2] === b[i][2])
const lerpPoints = (from: V3[], to: V3[], e: number): V3[] =>
  to.map((p, i) => [from[i][0] + (p[0] - from[i][0]) * e, from[i][1] + (p[1] - from[i][1]) * e, from[i][2] + (p[2] - from[i][2]) * e] as V3)

export interface UseTubeGeometryOptions<G extends Disposable> {
  meshRef: RefObject<{ geometry: Disposable | null } | null>
  target: V3[]
  reduce: boolean
  build: (points: V3[]) => G
  now?: () => number
}

/**
 * Decides, per route change, whether a tube's geometry snaps instantly or eases in (spec ruling
 * P3-R5). Fix round 2 reset a "built" flag to `false` unconditionally in the route effect's own
 * cleanup to make Strict Mode's mount-time dry run rebuild correctly — but that cleanup fires on
 * *every* dependency change, not just the dry run, so a genuine route change was permanently
 * forced onto the snap branch after the very first one, breaking the cold-open shot's R11 ease
 * (fix round 3's regression). This hook separates the two concerns instead:
 *
 *  - "is there a geometry yet at all" is read directly off `liveGeom` (owned by useLiveGeometry,
 *    P3-R4) rather than a separate flag the route effect has to remember to reset. `liveGeom` is
 *    only ever null before the very first build, or right after Strict Mode's dry run disposes
 *    the phantom first one and nulls it (`useLiveGeometry`'s own unmount-safety effect) — in
 *    both cases the only sound thing to do is build and snap.
 *  - otherwise, if `reduce` is set, snap.
 *  - otherwise, start (or restart) an eased animation from wherever is *currently displayed*
 *    (the last interpolated frame, if a previous animation hadn't finished — never the old,
 *    possibly long-stale `target`) to the new target.
 *
 * The route effect's cleanup does nothing: no dispose, no flag reset. Disposal only ever
 * happens inside `swap` (called here for snaps, and every frame by `tick()` while animating) and
 * inside `useLiveGeometry`'s own dedicated unmount safety net.
 */
export function useTubeGeometry<G extends Disposable>({ meshRef, target, reduce, build, now = () => performance.now() }: UseTubeGeometryOptions<G>) {
  const { liveGeom, swap } = useLiveGeometry<G>(meshRef)
  const from = useRef<V3[] | null>(null) // fixed start of the in-flight animation, if any
  const displayed = useRef<V3[] | null>(null) // whatever is currently on screen (snapped value, or last interpolated frame)
  const t0 = useRef(0) // animation start time; 0 means "not animating"

  useLayoutEffect(() => {
    // A revision switch rebuilds every route array even where the route did not move (M16): keep
    // the live geometry instead of rebuilding a TubeGeometry per frame for nothing.
    if (liveGeom.current && !t0.current && displayed.current && samePoints(displayed.current, target)) return
    if (!liveGeom.current || reduce) {
      swap(build(target))
      displayed.current = target
      from.current = target
      t0.current = 0
      return
    }
    from.current = displayed.current ?? target
    t0.current = now()
    // No cleanup here on purpose — see the function doc comment.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- swap/liveGeom/build/now are stable across renders for our callers
  }, [target, reduce])

  /** Call once per frame (e.g. from useFrame). No-op while not animating. */
  const tick = () => {
    if (!t0.current) return
    const k = Math.min(1, (now() - t0.current) / EASE_MS)
    const pts = lerpPoints(from.current ?? target, target, ease(k))
    displayed.current = pts
    swap(build(pts))
    if (k >= 1) {
      t0.current = 0
      displayed.current = target
    }
  }

  return { liveGeom, swap, from, displayed, t0, tick } as const
}
