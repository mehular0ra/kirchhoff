import { useEffect, useRef, type RefObject } from 'react'

export interface Disposable {
  dispose(): void
}

/**
 * Owns a mesh's live, swappable resource (e.g. a THREE.BufferGeometry) outside of React state
 * (spec ruling P3-R4). A plain useState/useEffect pair disposes the live, in-use value during
 * Strict Mode's mount-time setup→cleanup→setup dry run, because that cleanup is keyed only on
 * the value and fires before anything has a chance to rebuild it. Here, disposal only ever
 * happens inside `swap`, which always hands the mesh a genuinely new value first — so even
 * under the dry run's extra cleanup+setup, the mesh is never left pointing at a disposed object.
 *
 * `swap(next)` is the only way to replace the live value: it assigns it onto the mesh ref,
 * disposes whatever was live before (unless it's the same object), and updates `liveGeom`.
 * Build values only inside effects or useFrame — never during render — and route every
 * replacement (a route-change effect, a reduced-motion snap, a useFrame animation step) through
 * this same `swap`, so `liveGeom` is never stale relative to what the mesh actually holds.
 *
 * The route-change effect that builds a new value is responsible for disposing it in its own
 * cleanup, but only if it is *still* `liveGeom` at cleanup time (it may already have been
 * disposed by something else, e.g. the safety net below, or superseded by a later swap) — see
 * AnimatedTube. This hook itself only adds a safety net: whatever is live when the component
 * truly unmounts gets disposed exactly once, covering the case where the last swap came from
 * useFrame (no React effect holds a cleanup for that value).
 */
export function useLiveGeometry<G extends Disposable>(meshRef: RefObject<{ geometry: Disposable | null } | null>) {
  const liveGeom = useRef<G | null>(null)

  const swap = (next: G) => {
    if (meshRef.current) meshRef.current.geometry = next
    const prev = liveGeom.current
    liveGeom.current = next
    if (prev && prev !== next) prev.dispose()
  }

  useEffect(
    () => () => {
      liveGeom.current?.dispose()
      liveGeom.current = null
    },
    [],
  )

  return { liveGeom, swap } as const
}
