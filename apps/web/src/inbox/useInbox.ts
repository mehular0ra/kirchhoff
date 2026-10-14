// Bids inbox data (spec §20). Static first: /demo/inbox.json renders with the backend down (spec §11). Live
// second: GET /api/inbox adds the visitor's overlay (triage, Pursue) and replaces the static data when it answers.
// "New" is per browser: ids opened here are kept in localStorage `kirchhoff.inbox.read` (addendum ruling B9).
import { useEffect } from 'react'
import { create } from 'zustand'
import { loadInboxSnapshot } from '@/data/staticData'
import { readJson, writeJson } from '@/lib/storage'
import type { InboxEmail, InboxSnapshot, PursueResult, TriageResult } from '@/lib/types'
import { useServices } from '@/services/services'

const READ_KEY = 'inbox.read'

export interface InboxState {
  data: InboxSnapshot | null
  live: boolean
  loading: boolean
  error: string | null
  read: string[]
}

export const useInboxStore = create<InboxState>()(() => ({ data: null, live: false, loading: false, error: null, read: [] }))

export function resetInboxStore(): void {
  useInboxStore.setState({ data: null, live: false, loading: false, error: null, read: readJson<string[]>(READ_KEY, []) })
}

export function useInbox(): InboxState {
  const { api, getJson } = useServices()
  const state = useInboxStore()
  useEffect(() => {
    const s = useInboxStore.getState()
    if (s.data || s.loading) return
    useInboxStore.setState({ loading: true, read: readJson<string[]>(READ_KEY, []) })
    const failed = { static: null as string | null, live: false }
    const settle = () => {
      if (failed.static && failed.live && !useInboxStore.getState().data)
        useInboxStore.setState({ loading: false, error: failed.static })
    }
    loadInboxSnapshot(getJson)
      .then((data) => {
        if (!useInboxStore.getState().live) useInboxStore.setState({ data, loading: false, error: null })
      })
      .catch((e: Error) => {
        failed.static = e.message
        settle()
      })
    api
      .inbox()
      .then((data) => useInboxStore.setState({ data, live: true, loading: false, error: null }))
      .catch(() => {
        failed.live = true
        settle()
      })
  }, [api, getJson])
  return state
}

export function markRead(id: string): void {
  const { read } = useInboxStore.getState()
  if (read.includes(id)) return
  const next = [...read, id]
  writeJson(READ_KEY, next)
  useInboxStore.setState({ read: next })
}

export function unreadCount(data: InboxSnapshot | null, read: string[]): number {
  return data ? data.emails.filter((e) => !read.includes(e.id)).length : 0
}

function patchEmail(id: string, patch: (e: InboxEmail) => Partial<InboxEmail>): void {
  const { data } = useInboxStore.getState()
  if (!data) return
  useInboxStore.setState({ data: { ...data, emails: data.emails.map((e) => (e.id === id ? { ...e, ...patch(e) } : e)) } })
}

export function applyTriage(id: string, triage: TriageResult): void {
  patchEmail(id, (e) => ({ triage, status: e.status === 'pursued' ? 'pursued' : 'triaged' }))
}

export function applyPursue(id: string, pursue: PursueResult): void {
  patchEmail(id, () => ({ pursue, status: 'pursued' }))
}
