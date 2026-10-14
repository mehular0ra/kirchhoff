// Production wiring of Services (imports Firebase; never imported by tests).
import { apiFetch } from '@/api'
import { firestoreSource } from '@/data/liveSource'
import { fetchJson } from '@/data/staticData'
import { db, ensureSignedIn } from '@/firebase'
import { httpApiClient } from './apiClient'
import type { Services } from './services'

export function productionServices(): Services {
  return {
    api: httpApiClient(apiFetch),
    getJson: fetchJson,
    live: firestoreSource(db),
    uid: async () => (await ensureSignedIn()).uid,
    startLiveVoice: null, // wired to Gemini Live in Task 17
  }
}
