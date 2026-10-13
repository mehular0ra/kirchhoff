import { initializeApp } from 'firebase/app'
import { getAuth, signInAnonymously, onAuthStateChanged, type User } from 'firebase/auth'
import { getFirestore } from 'firebase/firestore'
import { initializeAppCheck, ReCaptchaEnterpriseProvider, getToken, type AppCheck } from 'firebase/app-check'

export const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: 'ordinal-mep.firebaseapp.com',
  projectId: 'ordinal-mep',
  storageBucket: 'ordinal-mep.firebasestorage.app',
  messagingSenderId: '1015632998221',
  appId: '1:1015632998221:web:c98110f2fc88424da81104',
}

export const app = initializeApp(firebaseConfig)
export const auth = getAuth(app)
export const db = getFirestore(app)

let appCheck: AppCheck | null = null
export function initAppCheck(): void {
  if (import.meta.env.MODE === 'test' || appCheck) return
  if (import.meta.env.DEV) (self as any).FIREBASE_APPCHECK_DEBUG_TOKEN = import.meta.env.VITE_APPCHECK_DEBUG_TOKEN || true
  appCheck = initializeAppCheck(app, {
    provider: new ReCaptchaEnterpriseProvider('6LdBw-wtAAAAALNbcALgFtPxNx9lcvnK_q2HuERk'),
    isTokenAutoRefreshEnabled: true,
  })
}

export async function appCheckToken(): Promise<string | null> {
  if (!appCheck) return null
  try { return (await getToken(appCheck, false)).token } catch { return null }
}

let ensureSignedInPromise: Promise<User> | null = null

export function ensureSignedIn(): Promise<User> {
  if (ensureSignedInPromise) return ensureSignedInPromise

  if (auth.currentUser) return Promise.resolve(auth.currentUser)

  ensureSignedInPromise = new Promise((resolve, reject) => {
    let off: (() => void) | null = null
    const handleAuthStateChange = (u: User | null) => {
      if (u) {
        if (off) off()
        ensureSignedInPromise = null
        resolve(u)
      }
    }
    off = onAuthStateChanged(auth, handleAuthStateChange)
    signInAnonymously(auth).catch((err) => {
      if (off) off()
      ensureSignedInPromise = null
      reject(err)
    })
  })

  return ensureSignedInPromise
}
