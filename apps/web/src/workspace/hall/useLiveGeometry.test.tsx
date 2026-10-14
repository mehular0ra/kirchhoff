// GREEN evidence for fix round 2. Must use real render(), not renderHook: renderHook never
// performs an actual commit, so it never exercises Strict Mode's mount-time setup→cleanup→setup
// dry run that disposed the live geometry under the old useDisposableState (see the RED
// evidence in task-8-report.md's "Fix round 2" section). react-three-fiber's useFrame can't run
// outside a <Canvas> (no WebGL in jsdom), so this tests the extracted ownership hook through a
// minimal plain-object "mesh" standing in for a THREE.Mesh, built the same way AnimatedTube
// builds its tube geometry: a useLayoutEffect, keyed on `route`, that builds via a factory and
// calls `swap`, disposing its own value in cleanup only if it's still live.
import { act, render } from '@testing-library/react'
import { StrictMode, useLayoutEffect, useRef } from 'react'
import { useLiveGeometry } from './useLiveGeometry'

function fakeGeom(label: string) {
  return { label, dispose: vi.fn() }
}
type FakeGeom = ReturnType<typeof fakeGeom>

/** Mirrors AnimatedTube's build-on-mount/route-change pattern (HallView.tsx) against a plain
 * object standing in for a THREE.Mesh, so it can render under real StrictMode without a canvas. */
function Owner({ route, factory, onMesh }: { route: string; factory: (route: string) => FakeGeom; onMesh?: (m: { geometry: FakeGeom | null }) => void }) {
  const meshRef = useRef<{ geometry: FakeGeom | null }>({ geometry: null })
  const { liveGeom, swap } = useLiveGeometry<FakeGeom>(meshRef)

  useLayoutEffect(() => {
    const g = factory(route)
    swap(g)
    return () => {
      if (liveGeom.current === g) {
        g.dispose()
        liveGeom.current = null
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [route])

  // Hands the test the same stable object meshRef.current points at, so it can inspect which
  // geometry is live after each commit — reported from an effect (declared after the one above,
  // so it always runs once the swap for this commit has happened), never read during render.
  useLayoutEffect(() => {
    onMesh?.(meshRef.current)
  }, [onMesh])

  return null
}

test('after mount under real StrictMode, the geometry currently assigned is not disposed', () => {
  const created: FakeGeom[] = []
  let mesh: { geometry: FakeGeom | null } | null = null
  render(
    <StrictMode>
      <Owner
        route="r1"
        factory={(r) => {
          const g = fakeGeom(r)
          created.push(g)
          return g
        }}
        onMesh={(m) => (mesh = m)}
      />
    </StrictMode>,
  )
  expect(mesh!.geometry).not.toBeNull()
  expect(mesh!.geometry!.dispose).not.toHaveBeenCalled()
  // Strict Mode's dry run built one extra geometry and disposed the one it replaced — not the
  // one left live — so disposals never exceed builds minus the one still live.
  const disposed = created.filter((g) => g.dispose.mock.calls.length > 0)
  expect(disposed).not.toContain(mesh!.geometry)
  for (const g of created) expect(g.dispose.mock.calls.length).toBeLessThanOrEqual(1)
})

test('changing the route disposes the previous geometry exactly once and leaves the new one live and undisposed', () => {
  const created: FakeGeom[] = []
  const factory = (r: string) => {
    const g = fakeGeom(r)
    created.push(g)
    return g
  }
  let mesh: { geometry: FakeGeom | null } | null = null
  const { rerender } = render(
    <StrictMode>
      <Owner route="r1" factory={factory} onMesh={(m) => (mesh = m)} />
    </StrictMode>,
  )
  const afterMount = mesh!.geometry!
  act(() => {
    rerender(
      <StrictMode>
        <Owner route="r2" factory={factory} onMesh={(m) => (mesh = m)} />
      </StrictMode>,
    )
  })
  expect(afterMount.dispose).toHaveBeenCalledTimes(1)
  expect(mesh!.geometry).not.toBe(afterMount)
  expect(mesh!.geometry!.dispose).not.toHaveBeenCalled()
  for (const g of created) expect(g.dispose.mock.calls.length).toBeLessThanOrEqual(1)
})

test('unmounting disposes the live geometry exactly once, and no geometry is ever disposed twice', () => {
  const created: FakeGeom[] = []
  const factory = (r: string) => {
    const g = fakeGeom(r)
    created.push(g)
    return g
  }
  let mesh: { geometry: FakeGeom | null } | null = null
  const { unmount } = render(
    <StrictMode>
      <Owner route="r1" factory={factory} onMesh={(m) => (mesh = m)} />
    </StrictMode>,
  )
  const live = mesh!.geometry!
  act(() => unmount())
  expect(live.dispose).toHaveBeenCalledTimes(1)
  for (const g of created) expect(g.dispose.mock.calls.length).toBeLessThanOrEqual(1)
})

