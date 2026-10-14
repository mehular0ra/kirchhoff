// Production wiring of Services. Firebase (Auth, Firestore, App Check) is loaded on first use, not at
// startup: static browsing never needs it, and keeping it out of the entry chunk also keeps
// reCAPTCHA off the landing page (final review I9). Every path into it is time-bounded (I4).
import { fetchJson } from '@/data/staticData'
import type { LiveSource, Unsubscribe } from '@/data/liveSource'
import { httpApiClient, withTimeout, type Fetcher } from './apiClient'
import type { Services } from './services'

const SIGN_IN_TIMEOUT_MS = 10_000

type FirebaseModule = typeof import('@/firebase')
let firebasePromise: Promise<FirebaseModule> | null = null

/** Loads firebase.ts once and starts App Check before anything can ask for a token. */
function firebase(): Promise<FirebaseModule> {
  firebasePromise ??= import('@/firebase').then((m) => {
    m.initAppCheck()
    return m
  })
  return firebasePromise
}

/** Anonymous sign-in, bounded: a blocked reCAPTCHA can leave Auth waiting forever. */
async function signedInUid(): Promise<string> {
  const { ensureSignedIn } = await firebase()
  const user = await withTimeout(ensureSignedIn(), SIGN_IN_TIMEOUT_MS, () => new Error('Signing in to the live demo timed out'))
  return user.uid
}

const lazyApiFetch: Fetcher = async (path, init) => {
  await firebase()
  const { apiFetch } = await import('@/api')
  return apiFetch(path, init)
}

/** A LiveSource whose Firestore reader is created on the first subscription. */
function lazyLiveSource(): LiveSource {
  let real: Promise<LiveSource> | null = null
  const get = () =>
    (real ??= Promise.all([firebase(), import('@/data/liveSource')]).then(([fb, { firestoreSource }]) => firestoreSource(fb.db)))
  const deferred = (subscribe: (src: LiveSource) => Unsubscribe, onError?: (e: Error) => void): Unsubscribe => {
    let off: Unsubscribe | null = null
    let closed = false
    get().then(
      (src) => {
        if (!closed) off = subscribe(src)
      },
      (e: Error) => !closed && onError?.(e),
    )
    return () => {
      closed = true
      off?.()
    }
  }
  return {
    watchDoc: (path, cb, onError) => deferred((s) => s.watchDoc(path, cb, onError), onError),
    watchCollection: (path, cb, q, onError) => deferred((s) => s.watchCollection(path, cb, q, onError), onError),
    getDoc: async (path) => (await get()).getDoc(path),
  }
}

export function productionServices(): Services {
  return {
    api: httpApiClient(lazyApiFetch),
    getJson: fetchJson,
    live: lazyLiveSource(),
    uid: signedInUid,
    // `firebase/ai` (Schema, LiveGenerativeModel, the websocket handler) is sizeable and only
    // needed once a visitor clicks "Start voice", so it is loaded through a dynamic import on
    // first use instead of bundled into the main chunk for every visitor (fix round 1).
    startLiveVoice: async (opts) => {
      await firebase()
      return (await import('@/workspace/copilot/voice/liveVoice')).startLiveVoice(opts)
    },
  }
}
