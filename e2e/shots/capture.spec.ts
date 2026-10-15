import { mkdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test } from '../tests/fixtures'
import type { Locator, Page } from '@playwright/test'

/**
 * Deck screenshots (issue #17). Drives the app to each state in docs/submission/deck/shots/README.md and saves a PNG
 * with exactly the file name the deck builder expects. Every value on screen comes from the app's own data (the recorded
 * run / static bundles); nothing is typed by hand, and the fictional-data banner stays visible.
 *
 * Each shot first asserts the content its README row describes, so a state that is still empty (for example the Options
 * tab before the golden capture, which has no options yet) FAILS the shot instead of saving an empty screen.
 *
 *   dry run (default)  writes to e2e/out/shots, so the deck's placeholders are not touched:
 *                      E2E_LOCAL=1 E2E_SHOTS=1 npx playwright test --project=shots
 *   final capture      after the UI freeze and the golden-capture deploy, against the deployed site:
 *                      E2E_BASE_URL=https://kirchhoff.web.app E2E_SHOTS=1 SHOTS_WRITE=1 npx playwright test --project=shots
 *   live-only shots    (Hall B live run, voice) also need E2E_LIVE=1: they call the deployed agents.
 */
const HERE = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(HERE, '..', '..')
const OUT = process.env.SHOTS_WRITE === '1' ? path.join(ROOT, 'docs', 'submission', 'deck', 'shots') : path.join(HERE, '..', 'out', 'shots')
mkdirSync(OUT, { recursive: true })

type Shot = {
  file: string
  /** Opens the state and asserts what it must show. Returns the element to crop to, or nothing for a full-screen capture. */
  open: (page: Page) => Promise<Locator | void>
  live?: boolean
}

const LONG = { timeout: 60_000 }
const settle = (page: Page, ms = 1500) => page.waitForTimeout(ms) // the 3D hall and the SLD animate in
const text = (page: Page, t: string | RegExp) => expect(page.getByText(t).first()).toBeVisible(LONG)

/** Opens a Hall A workspace URL; the lanes are hidden from the accessibility tree while a finding drawer is open. */
const workspace = async (page: Page, query = '') => {
  await page.goto(`/app/p/hall-a${query}`)
  await expect(page.getByRole('navigation', { name: 'Agent lanes' }).or(page.getByRole('dialog')).first()).toBeVisible(LONG)
  await settle(page, 2500)
}

const SHOTS: Shot[] = [
  {
    file: 's03-workspace-signed.png',
    open: async (page) => {
      await workspace(page)
      await text(page, /signed by Priya Raman/)
    },
  },
  {
    file: 's05-1-intake-quotes.png',
    open: async (page) => {
      await workspace(page, '?replay=1')
      await text(page, /quote verified/i) // needs the recorded run (golden capture)
      return page.getByRole('navigation', { name: 'Agent lanes' })
    },
  },
  {
    file: 's05-2-hall-3d-tiers.png',
    open: async (page) => {
      await workspace(page, '?tab=hall')
      return page.locator('canvas').first()
    },
  },
  {
    file: 's05-3-compliance-matrix.png',
    open: async (page) => {
      await workspace(page, '?tab=matrix')
      return page.getByRole('table', { name: 'Compliance matrix' })
    },
  },
  {
    file: 's05-4-option-r15-swap.png',
    open: async (page) => {
      await workspace(page, '?tab=options')
      await text(page, '3.15 MVA') // the R15 swap card: needs the options from the golden capture
      return page.getByRole('tabpanel').first()
    },
  },
  {
    file: 's05-5-impact-chain.png',
    open: async (page) => {
      await workspace(page)
      await page.locator('[data-tour="whatif-chip"]').click()
      const chain = page.getByRole('list', { name: 'Impact chain' })
      await expect(chain).toBeVisible()
      await text(page, 'Show all 18 impact chains')
      await settle(page, 1000)
      return chain
    },
  },
  { file: 's05-6-copilot-voice.png', live: true, open: async (page) => { await workspace(page) } },
  {
    file: 's05-7-review-stamp.png',
    open: async (page) => {
      await page.goto('/app/p/hall-a/review/r2')
      await text(page, 'APPROVED')
      await settle(page)
      return page.getByText('APPROVED').first().locator('xpath=ancestor::*[contains(@class,"border")][1]')
    },
  },
  {
    file: 's05-8-integrations.png',
    open: async (page) => {
      await page.goto('/app/integrations')
      await expect(page.getByRole('region', { name: 'Latest handoff' })).toBeVisible(LONG)
      await settle(page, 1000)
      return page.getByRole('main')
    },
  },
  {
    file: 's05-9-solar-field.png',
    open: async (page) => {
      await page.goto('/app/p/solar-5mwp')
      const field = page.getByRole('img', { name: 'Site geometry' })
      await expect(field).toBeVisible(LONG)
      await settle(page, 1000)
      return field
    },
  },
  {
    file: 's07-finding-drawer-r05.png',
    open: async (page) => {
      await workspace(page, '?tab=matrix&rev=r1&finding=R05%3AFA-01')
      const drawer = page.getByRole('dialog').first()
      await expect(drawer).toContainText('2.16%')
      await expect(drawer).toContainText('§4.6')
      return drawer
    },
  },
  {
    file: 's11-1-projects-dashboard.png',
    open: async (page) => {
      await page.goto('/app')
      await text(page, 'Signed')
      await text(page, 'Not started')
      await settle(page, 1000)
    },
  },
  { file: 's11-2-hall-b-live-run.png', live: true, open: async (page) => { await page.goto('/app/p/hall-b') } },
  {
    file: 's11-3-finding-drawer-r11.png',
    open: async (page) => {
      await workspace(page, '?tab=hall&rev=r1&finding=R11%3AH-Z2')
      const drawer = page.getByRole('dialog').first()
      await expect(drawer).toContainText('H-Z2')
      await expect(drawer).toContainText('§6.3.4')
    },
  },
  {
    file: 's11-4-options-r15-swap.png',
    open: async (page) => {
      await workspace(page, '?tab=options')
      await text(page, '3.15 MVA') // needs the options from the golden capture
    },
  },
  {
    file: 's11-5-what-if-200kw.png',
    open: async (page) => {
      await workspace(page)
      await page.locator('[data-tour="whatif-chip"]').click()
      await expect(page.getByRole('list', { name: 'Impact chain' })).toBeVisible()
      await text(page, 'Show all 18 impact chains')
      await text(page, 'Show all 60 findings')
      await settle(page, 1500)
    },
  },
  {
    file: 's11-6-review-approved.png',
    open: async (page) => {
      await page.goto('/app/p/hall-a/review/r2')
      await text(page, 'APPROVED')
      await settle(page)
    },
  },
  {
    file: 's12-compliance-matrix-first-pass.png',
    open: async (page) => {
      await workspace(page, '?tab=matrix&rev=r1')
      await text(page, '149 checks')
      await expect(page.getByRole('button', { name: /: Fail$/ })).toHaveCount(2)
    },
  },
  {
    file: 's13-grid-pack.png',
    open: async (page) => {
      await page.goto('/app/p/grid-132kv')
      await expect(page.getByRole('table', { name: 'Asset options' })).toBeVisible(LONG)
      await expect(page.getByRole('region', { name: 'Mini SLD' })).toBeVisible()
      await settle(page, 1000)
    },
  },
  {
    file: 's13-solar-pack.png',
    open: async (page) => {
      await page.goto('/app/p/solar-5mwp')
      await expect(page.getByRole('table', { name: 'Asset options' })).toBeVisible(LONG)
      await text(page, /STR-28/)
      await settle(page, 1000)
    },
  },
]

for (const shot of SHOTS) {
  test(shot.file, async ({ page }) => {
    test.skip(shot.live === true && process.env.E2E_LIVE !== '1', 'needs the deployed agents: set E2E_LIVE=1')
    test.setTimeout(150_000)
    await page.setViewportSize({ width: 1920, height: 1080 })
    const target = await shot.open(page)
    // The banner must be visible in every capture: full-screen shots show it; for a crop, check it is on the page.
    // (By text, not by role: an open finding drawer is a modal and hides the banner from the accessibility tree.)
    await expect(page.getByText('all companies, people and data are fictional').first()).toBeVisible()
    const file = path.join(OUT, shot.file)
    if (target) await target.screenshot({ path: file })
    else await page.screenshot({ path: file })
  })
}
