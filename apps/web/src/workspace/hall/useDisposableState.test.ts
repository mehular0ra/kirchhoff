import { act, renderHook } from '@testing-library/react'
import { useDisposableState } from './useDisposableState'

function fakeGeom() {
  return { dispose: vi.fn() }
}

test('builds the initial value exactly once and does not dispose it on mount', () => {
  const build = vi.fn(fakeGeom)
  const { result } = renderHook(() => useDisposableState(build))
  expect(build).toHaveBeenCalledTimes(1)
  expect(result.current[0].dispose).not.toHaveBeenCalled()
})

test('disposes the previous value when it is replaced, and not the new one', () => {
  const first = fakeGeom()
  const { result } = renderHook(() => useDisposableState(() => first))
  const second = fakeGeom()
  act(() => result.current[1](second))
  expect(first.dispose).toHaveBeenCalledTimes(1)
  expect(second.dispose).not.toHaveBeenCalled()
  expect(result.current[0]).toBe(second)
})

test('disposes the current value exactly once on unmount, with no extra dispose from replacing it first', () => {
  const geom = fakeGeom()
  const { unmount } = renderHook(() => useDisposableState(() => geom))
  unmount()
  expect(geom.dispose).toHaveBeenCalledTimes(1)
})

test('replacing then unmounting disposes each value exactly once', () => {
  const first = fakeGeom()
  const second = fakeGeom()
  const { result, unmount } = renderHook(() => useDisposableState(() => first))
  act(() => result.current[1](second))
  unmount()
  expect(first.dispose).toHaveBeenCalledTimes(1)
  expect(second.dispose).toHaveBeenCalledTimes(1)
})
