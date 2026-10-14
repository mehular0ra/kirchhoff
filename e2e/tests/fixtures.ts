import { test as base, expect } from '@playwright/test'

/** Registered App Check debug token (ruling W19). Empty until Task 15 registers it; never committed. */
const APPCHECK_DEBUG_TOKEN = process.env.APPCHECK_DEBUG_TOKEN ?? ''

if (process.env.E2E_REQUIRE_APPCHECK === '1' && !APPCHECK_DEBUG_TOKEN) {
  throw new Error('E2E_REQUIRE_APPCHECK=1 but APPCHECK_DEBUG_TOKEN is empty: run `make e2e` (it reads Secret Manager)')
}

export const BANNER = 'Demo workspace — all companies, people and data are fictional'

/**
 * Local runs (make e2e-local) never reach Google: no anonymous sign-ins in the real Firebase project, no reCAPTCHA,
 * no Firestore. The app is static-first, so browsing must work with all of it refused.
 */
const BLOCK_GOOGLE = process.env.E2E_LOCAL === '1' || process.env.E2E_BLOCK_GOOGLE === '1'
const GOOGLE = [/\.googleapis\.com/, /\.firebaseio\.com/, /\.firebaseapp\.com\/__\/auth/, /recaptcha/, /\.gstatic\.com/]

export const test = base.extend<{ welcomed: boolean }>({
  welcomed: [true, { option: true }],
  context: async ({ context, welcomed }, use) => {
    if (BLOCK_GOOGLE) {
      for (const pattern of GOOGLE) await context.route(pattern, (route) => route.abort('connectionrefused'))
    }
    if (APPCHECK_DEBUG_TOKEN) {
      // The Firebase JS SDK reads this global in any build mode (controller ruling: no change to firebase.ts).
      await context.addInitScript((token: string) => {
        ;(self as unknown as { FIREBASE_APPCHECK_DEBUG_TOKEN?: string }).FIREBASE_APPCHECK_DEBUG_TOKEN = token
      }, APPCHECK_DEBUG_TOKEN)
    }
    if (welcomed) {
      await context.addInitScript(() => {
        try {
          localStorage.setItem('kirchhoff.welcomed', 'true')
        } catch {
          // storage blocked: the welcome dialog shows and the test fails visibly
        }
      })
    }
    await use(context)
  },
})

export { expect }
