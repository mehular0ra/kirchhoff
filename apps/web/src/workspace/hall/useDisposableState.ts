import { useEffect, useState } from 'react'

/**
 * Like useState, but for a disposable GPU resource (e.g. a THREE.BufferGeometry): disposes the
 * previous value whenever it is replaced, and disposes the current value on unmount. `init` runs
 * exactly once via useState's lazy initializer, so the initial value is never double-built or
 * disposed on mount. Prop-assigned geometries are not auto-disposed by react-three-fiber, so any
 * manually constructed geometry held in component state should be owned through this hook.
 */
export function useDisposableState<T extends { dispose(): void }>(init: () => T): [T, (next: T) => void] {
  const [value, setValue] = useState(init)
  // Cleanup closes over the `value` this effect ran with, so it disposes exactly that value —
  // whether it's being replaced (cleanup fires before the next effect) or the component unmounts.
  useEffect(() => () => value.dispose(), [value])
  return [value, setValue]
}
