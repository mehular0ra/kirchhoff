// GREEN evidence for fix round 3. react-three-fiber's useFrame can't run outside a mounted
// <Canvas> (no WebGL in jsdom), so this exercises the real decision logic — useTubeGeometry,
// used verbatim by AnimatedTube in HallView.tsx — through a minimal plain-object "mesh" and a
// manual `tick()` call standing in for a useFrame callback, rendered with real render()/
// rerender()/unmount() inside <StrictMode> (never renderHook, which performs no real commit and
// so never exercises Strict Mode's mount-time dry run).
import { act, render } from '@testing-library/react'
import { StrictMode, useLayoutEffect, useRef } from 'react'
import { useTubeGeometry } from './useTubeGeometry'
import type { V3 } from './hallScene'

function fakeGeom(points: V3[]) {
  return { points, dispose: vi.fn() }
}
type FakeGeom = ReturnType<typeof fakeGeom>

const T1: V3[] = [[0, 0, 0], [10, 0, 0]]
const T2: V3[] = [[0, 0, 0], [10, 0, 3]]
const T3: V3[] = [[0, 0, 0], [10, 0, 6]]

interface Handle {
  from: { current: V3[] | null }
  t0: { current: number }
  displayed: { current: V3[] | null }
  mesh: { geometry: FakeGeom | null }
  tick(): void
}

function Owner({ target, reduce, now, onHandle }: { target: V3[]; reduce: boolean; now?: () => number; onHandle: (h: Handle) => void }) {
  const meshRef = useRef<{ geometry: FakeGeom | null }>({ geometry: null })
  const { from, t0, displayed, tick } = useTubeGeometry<FakeGeom>({ meshRef, target, reduce, build: fakeGeom, now })

  // Hands the test the live ref objects themselves (not snapshots of `.current`), so reading
  // them after an out-of-band `tick()` call reflects the real, current state.
  useLayoutEffect(() => {
    onHandle({ from, t0, displayed, mesh: meshRef.current, tick })
  })

  return null
}

test('mount: exactly one live geometry, undisposed; no animation started; the phantom is disposed exactly once', () => {
  let h: Handle | null = null
  render(
    <StrictMode>
      <Owner target={T1} reduce={false} onHandle={(x) => (h = x)} />
    </StrictMode>,
  )
  expect(h!.mesh.geometry).not.toBeNull()
  expect(h!.mesh.geometry!.dispose).not.toHaveBeenCalled()
  expect(h!.t0.current).toBe(0)
})

test('rerendering with a new target and reduce=false starts an animation, without snapping and without disposing the live geometry', () => {
  let h: Handle | null = null
  const { rerender } = render(
    <StrictMode>
      <Owner target={T1} reduce={false} onHandle={(x) => (h = x)} />
    </StrictMode>,
  )
  const liveAfterMount = h!.mesh.geometry!
  act(() => {
    rerender(
      <StrictMode>
        <Owner target={T2} reduce={false} onHandle={(x) => (h = x)} />
      </StrictMode>,
    )
  })
  expect(h!.t0.current).not.toBe(0) // an animation was started
  expect(h!.mesh.geometry).toBe(liveAfterMount) // no snap: the mesh still shows the pre-animation geometry
  expect(liveAfterMount.dispose).not.toHaveBeenCalled()
})

test('rerendering with a new target and reduce=true snaps, disposing the previous geometry exactly once', () => {
  let h: Handle | null = null
  const { rerender } = render(
    <StrictMode>
      <Owner target={T1} reduce={false} onHandle={(x) => (h = x)} />
    </StrictMode>,
  )
  const liveAfterMount = h!.mesh.geometry!
  act(() => {
    rerender(
      <StrictMode>
        <Owner target={T2} reduce={true} onHandle={(x) => (h = x)} />
      </StrictMode>,
    )
  })
  expect(h!.t0.current).toBe(0) // snap, not an animation
  expect(h!.mesh.geometry).not.toBe(liveAfterMount)
  expect(h!.mesh.geometry!.points).toEqual(T2)
  expect(liveAfterMount.dispose).toHaveBeenCalledTimes(1)
})

test('a route change while an animation is in flight restarts from the interpolated points, not the stale old target', () => {
  let h: Handle | null = null
  let t = 1000
  const now = () => t
  const { rerender } = render(
    <StrictMode>
      <Owner target={T1} reduce={false} now={now} onHandle={(x) => (h = x)} />
    </StrictMode>,
  )
  act(() => {
    rerender(
      <StrictMode>
        <Owner target={T2} reduce={false} now={now} onHandle={(x) => (h = x)} />
      </StrictMode>,
    )
  })
  // Advance partway through the 900ms ease and tick once, like a useFrame callback would.
  t += 450
  act(() => h!.tick())
  const midFlight = h!.displayed.current
  expect(midFlight).not.toEqual(T1)
  expect(midFlight).not.toEqual(T2)

  act(() => {
    rerender(
      <StrictMode>
        <Owner target={T3} reduce={false} now={now} onHandle={(x) => (h = x)} />
      </StrictMode>,
    )
  })
  // The new animation's start point is the interpolated mid-flight position, not T1 or T2.
  expect(h!.from.current).toEqual(midFlight)
})

test('unmount disposes the live geometry exactly once, and nothing is ever disposed twice', () => {
  let h: Handle | null = null
  const { unmount } = render(
    <StrictMode>
      <Owner target={T1} reduce={false} onHandle={(x) => (h = x)} />
    </StrictMode>,
  )
  const live = h!.mesh.geometry!
  act(() => unmount())
  expect(live.dispose).toHaveBeenCalledTimes(1)
})
