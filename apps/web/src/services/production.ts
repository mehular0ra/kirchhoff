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
    // `firebase/ai` (Schema, LiveGenerativeModel, the websocket handler) is sizeable and only
    // needed once a visitor clicks "Start voice", so it is loaded through a dynamic import on
    // first use instead of bundled into the main chunk for every visitor (fix round 1).
    startLiveVoice: async (opts) => (await import('@/workspace/copilot/voice/liveVoice')).startLiveVoice(opts),
  }
}
