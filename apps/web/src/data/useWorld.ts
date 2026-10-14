import { useEffect } from 'react'
import { create } from 'zustand'
import type { Project, World } from '@/lib/types'
import { useServices } from '@/services/services'
import { loadWorld } from './staticData'

interface WorldStore {
  world: World | null
  error: string | null
  loading: boolean
}
export const useWorldStore = create<WorldStore>()(() => ({ world: null, error: null, loading: false }))

/** Loads /demo/world.json once per session (static, works with the backend down). */
export function useWorld(): WorldStore {
  const { getJson } = useServices()
  const state = useWorldStore()
  useEffect(() => {
    const s = useWorldStore.getState()
    if (s.world || s.loading) return
    useWorldStore.setState({ loading: true })
    loadWorld(getJson)
      .then((world) => useWorldStore.setState({ world, loading: false, error: null }))
      .catch((e: Error) => useWorldStore.setState({ loading: false, error: e.message }))
  }, [getJson])
  return state
}

export function useWorldProject(pid: string | undefined): Project | null {
  const { world } = useWorld()
  return world?.projects.find((p) => p.id === pid) ?? null
}
