// Loads a project view into the bundle store from one of three adapters:
// static (/demo/projects/{pid}.json), live (Firestore, ?run=rid) or replay (?replay=1).
import { useEffect, useRef, useState } from 'react'
import type { DataSource } from '@/lib/select'
import type { Bundle, Project } from '@/lib/types'
import { useServices } from '@/services/services'
import { entryKey, useBundleStore, type ReplayState } from '@/store/bundles'
import { subscribeLiveBundle } from './liveBundle'
import { createReplay, type ReplayControls } from './replay'
import { staticBundle } from './staticData'

export interface ProjectDataOptions {
  runId?: string | null
  replay?: boolean
  project?: Project | null
  speed?: number
}

export interface ProjectData {
  key: string
  status: 'loading' | 'ready' | 'error'
  source: DataSource
  bundle: Bundle | null
  error?: string
  replay?: ReplayState
  controls: ReplayControls | null
}

const placeholderProject = (pid: string): Project => ({
  id: pid,
  name: pid,
  client: '',
  asset_pack: 'datahall',
  state: 'running',
  sample: false,
  updated_at: 0,
})

export function useProjectData(pid: string, opts: ProjectDataOptions = {}): ProjectData {
  const services = useServices()
  const source: DataSource = opts.runId ? 'live' : opts.replay ? 'replay' : 'static'
  const key = entryKey(pid, { runId: opts.runId, replay: opts.replay })
  const entry = useBundleStore((s) => s.entries[key])
  const [controls, setControls] = useState<ReplayControls | null>(null)
  const projectRef = useRef(opts.project)
  projectRef.current = opts.project

  useEffect(() => {
    const store = useBundleStore.getState()
    let cancelled = false
    let cleanup: () => void = () => {}

    if (source === 'static') {
      if (store.entries[key]?.status === 'ready') return
      store.setLoading(key, source)
      staticBundle(pid, services.getJson)
        .then((b) => !cancelled && useBundleStore.getState().setBundle(key, b, source))
        .catch((e: Error) => !cancelled && useBundleStore.getState().setError(key, e.message, source))
    }

    if (source === 'replay') {
      store.setLoading(key, source)
      staticBundle(pid, services.getJson)
        .then((full) => {
          if (cancelled) return
          const c = createReplay(full, {
            speed: opts.speed,
            onFrame: (b, s) => {
              const st = useBundleStore.getState()
              st.setBundle(key, b, source)
              st.setReplay(key, s)
            },
          })
          setControls(c)
          cleanup = () => c.dispose()
        })
        .catch((e: Error) => !cancelled && useBundleStore.getState().setError(key, e.message, source))
    }

    if (source === 'live') {
      const live = services.live
      if (!live) {
        store.setError(key, 'Live data is unavailable in this environment', source)
        return
      }
      store.setLoading(key, source)
      services
        .uid()
        .then((uid) => {
          if (cancelled) return
          cleanup = subscribeLiveBundle(
            live,
            {
              uid,
              runId: opts.runId!,
              project: projectRef.current ?? placeholderProject(pid),
              loadJson: async (ref) =>
                ref.startsWith('http') || ref.startsWith('/')
                  ? services.getJson(ref)
                  : JSON.parse(await (await services.api.fileBlob(ref)).text()),
            },
            (b) => useBundleStore.getState().setBundle(key, b, source),
            (e) => useBundleStore.getState().setError(key, e.message, source),
          )
        })
        .catch((e: Error) => !cancelled && useBundleStore.getState().setError(key, e.message, source))
    }

    return () => {
      cancelled = true
      cleanup()
      setControls(null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  return {
    key,
    status: entry?.status ?? 'loading',
    source,
    bundle: entry?.bundle ?? null,
    error: entry?.error,
    replay: entry?.replay,
    controls,
  }
}
