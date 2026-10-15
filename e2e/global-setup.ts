import { chromium, type FullConfig } from '@playwright/test'
import { GOOGLE } from './tests/fixtures'

/**
 * Local runs (E2E_LOCAL=1) serve apps/web through the Vite dev server, which compiles each route's code on first use.
 * That cold cost (tens of seconds for the 3D hall and the SLD) belongs to the dev server, not to the product, and it
 * made the first test to open a heavy page time out or miss its timing budget. Visit every heavy screen once, and
 * press the what-if chip once, before the first test starts. A deployed site has nothing to compile: no-op there.
 * Google endpoints stay blocked here too, so the warm-up reaches no cloud service.
 */
export default async function globalSetup(config: FullConfig): Promise<void> {
  if (process.env.E2E_LOCAL !== '1') return
  const baseURL = config.projects[0].use.baseURL
  if (!baseURL) return
  const browser = await chromium.launch()
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    for (const pattern of GOOGLE) await context.route(pattern, (route) => route.abort('connectionrefused'))
    await context.addInitScript(() => {
      try {
        localStorage.setItem('kirchhoff.welcomed', 'true')
      } catch {
        // storage blocked: nothing to warm that depends on it
      }
    })
    const page = await context.newPage()
    for (const path of ['/app', '/app/inbox', '/app/integrations', '/app/p/hall-a?tab=matrix&rev=r1', '/app/p/grid-132kv']) {
      await page.goto(baseURL + path, { waitUntil: 'networkidle', timeout: 180_000 })
    }
    await page.goto(baseURL + '/app/p/hall-a', { waitUntil: 'networkidle', timeout: 180_000 })
    await page.locator('[data-tour="whatif-chip"]').click({ timeout: 60_000 })
    await page.getByRole('list', { name: 'Impact chain' }).waitFor({ timeout: 120_000 })
  } finally {
    await browser.close()
  }
}
