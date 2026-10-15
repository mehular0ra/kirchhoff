import { test as base, expect, type Page } from '@playwright/test'

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

/** Landing -> demo workspace -> welcome -> "Take the 2-minute tour". Use it with `welcomed: false`. */
export async function startTour(page: Page): Promise<void> {
  await page.goto('/')
  await page.getByRole('link', { name: 'Enter the demo workspace (no login)' }).click()
  await page.getByRole('button', { name: 'Take the 2-minute tour' }).click()
  await expect(page.getByRole('dialog', { name: 'Guided tour' })).toBeVisible()
}

/** Walks the tour with the ArrowRight key and reports, per step, whether its card is fully inside the viewport. */
export async function tourCardPositions(page: Page, steps = 7) {
  const { width, height } = page.viewportSize()!
  const tour = page.getByRole('dialog', { name: 'Guided tour' })
  const out: { step: number; inView: boolean; box: { x: number; y: number; w: number; h: number } | null }[] = []
  for (let step = 1; step <= steps; step++) {
    await expect(tour.getByText(`Step ${step} of ${steps}`)).toBeVisible()
    await expect(tour.getByText('Loading this part of the workspace…')).toBeHidden({ timeout: 20_000 })
    await page.waitForTimeout(800) // the step scrolls its target into view first
    const b = await tour.boundingBox()
    const box = b && { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height) }
    const inView = !!box && box.x >= 0 && box.y >= 0 && box.x + box.w <= width && box.y + box.h <= height
    out.push({ step, inView, box })
    if (step < steps) await page.keyboard.press('ArrowRight')
  }
  return out
}

export { expect }
