// Whether a seed project (Hall A) carries a recorded run that replay can play (UX-1 D10). Loads the static
// bundle into the shared bundle store, so opening Hall A afterwards is instant and the tour reuses it.
import { useEffect } from 'react'
import { useServices } from '@/services/services'
import { entryKey, useBundleStore } from '@/store/bundles'
import { staticBundle } from './staticData'

/** true / false once the bundle is known; null while loading or when it cannot load. */
export function useRecordedRun(pid = 'hall-a'): boolean | null {
  const { getJson } = useServices()
  const key = entryKey(pid)
  const bundle = useBundleStore((s) => s.entries[key]?.bundle ?? null)
  useEffect(() => {
    const store = useBundleStore.getState()
    if (store.entries[key]) return
    store.setLoading(key, 'static')
    staticBundle(pid, getJson)
      .then((b) => useBundleStore.getState().setBundle(key, b, 'static'))
      .catch((e: Error) => useBundleStore.getState().setError(key, e.message, 'static'))
  }, [key, pid, getJson])
  return bundle ? bundle.events.length > 0 : null
}
