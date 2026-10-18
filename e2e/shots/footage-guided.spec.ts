import { mkdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test } from '../tests/fixtures'
import type { Page } from '@playwright/test'
import { clickAt, highlight, installGuide, pointAt } from './guide'

/**
 * Guided footage for the demo video (Mehul's review, 18 Oct 2026): the platform at a human's pace, with a visible cursor and a
 * labelled highlight on what is being explained. Same app, same recorded runs as footage.spec.ts; the difference is the cursor
 * and the highlights (guide.ts), and longer, slower holds. Nothing here writes to the shared sandbox.
 *
 *   E2E_FOOTAGE=1 npx playwright test --project=footage -g "guided"
 *
 * Clips land in FOOTAGE_OUT (default e2e/out/footage) as g01-inbox.webm ... g05-options.webm; shots/footage_to_mp4.sh converts them.
 */
const HERE = path.dirname(fileURLToPath(import.meta.url))
const OUT = process.env.FOOTAGE_OUT ?? path.join(HERE, '..', 'out', 'footage')
mkdirSync(OUT, { recursive: true })

const HANDLE = 2_000
const LONG = { timeout: 60_000 }
const hold = (page: Page, ms: number) => page.waitForTimeout(ms)
const text = (page: Page, t: string | RegExp) => expect(page.getByText(t).first()).toBeVisible(LONG)
const ready = async (page: Page) => {
  await expect(page.getByRole('navigation', { name: 'Agent lanes' }).or(page.getByRole('dialog')).first()).toBeVisible(LONG)
  await hold(page, 2_500) // the 3D hall animates in
}

type Beat = { clip: string; run: (page: Page) => Promise<void> }

const BEATS: Beat[] = [
  {
    // The Bids inbox: a new tender, opened, its fields each found in the source, and the fit verdict.
    clip: 'g01-inbox',
    run: async (page) => {
      await page.goto('/app/inbox')
      await expect(page.getByRole('heading', { name: 'Bids inbox', level: 1 })).toBeVisible(LONG)
      await expect(page.locator('a[href^="/app/inbox/em-"]')).toHaveCount(6)
      await hold(page, 1_800)
      const row = page.locator('a[href="/app/inbox/em-hall-b"]')
      await highlight(page, row, 'A new tender from the client', 2_600)
      await clickAt(page, row, 900)
      const detail = page.getByRole('region', { name: 'Email' })
      const fit = detail.getByRole('region', { name: 'Fit verdict' })
      await expect(fit).toContainText('Pursue', LONG)
      await hold(page, 1_000)
      await highlight(page, detail.getByRole('table', { name: 'Extracted fields' }), 'Every field is found in the source: quote verified', 5_000, { spot: true })
      await highlight(page, fit, 'Fit check: deterministic rules, no AI in the verdict', 5_000, { spot: true })
      await hold(page, 1_000)
    },
  },
  {
    // The checker at r1: 149 checks, the two failures, the drawer with its formula, limit and clause, the PDF with the quote boxed, r2 all pass.
    clip: 'g02-checker',
    run: async (page) => {
      await page.goto('/app/p/hall-a?tab=matrix&rev=r1')
      await text(page, '149 checks')
      await hold(page, 1_500)
      await highlight(page, page.getByText('149 checks').first(), '149 checks, run by deterministic code', 2_800)
      const fails = page.getByRole('button', { name: /: Fail$/ })
      await expect(fails).toHaveCount(2)
      await highlight(page, fails.nth(0), 'Failing: R05, feeder FA-01', 2_000, { pad: 6 })
      await clickAt(page, fails.nth(0), 900)
      const drawer = page.getByRole('dialog').first()
      await expect(drawer).toContainText('2.16%')
      await expect(drawer).toContainText('§4.6')
      await hold(page, 800)
      await highlight(page, drawer.getByText('2.16%').first(), 'Voltage drop 2.16%, against its limit', 2_600)
      await highlight(page, drawer.getByRole('region', { name: 'Formula' }), 'The formula, with the real inputs', 3_200)
      await highlight(page, drawer.getByRole('region', { name: 'Fix' }), 'Fix options, each re-checked by the engine', 3_200)
      const chip = page.getByRole('button', { name: /^Open tender §4\.6 · p\.\d+$/ }).first()
      await highlight(page, chip, 'One click to the tender clause', 1_900)
      await clickAt(page, chip, 800)
      const source = page.getByRole('dialog', { name: /^Tender §4\.6 · page \d+$/ })
      await expect(source).toContainText('Verified quote:')
      await expect(source.locator('canvas').first()).toBeVisible({ timeout: 20_000 })
      await expect(page.getByTestId('citation-highlight').first()).toBeVisible({ timeout: 20_000 })
      await hold(page, 600)
      await highlight(page, page.getByTestId('citation-highlight').first(), 'The quote, verified and boxed on the page', 4_000, { spot: true })
      await page.keyboard.press('Escape')
      await hold(page, 600)
      if (await page.getByRole('dialog').count()) await page.keyboard.press('Escape')
      await hold(page, 800)
      await highlight(page, fails.nth(1), 'Failing: R11, a pipe over a live feeder', 2_000, { pad: 6 })
      await clickAt(page, fails.nth(1), 900)
      await expect(page.getByRole('dialog').first()).toContainText('§6.3.4')
      await hold(page, 800)
      await highlight(page, page.getByRole('dialog').first().getByRole('region', { name: 'Fix' }), 'Two verified fixes, with their cost', 3_400)
      await page.keyboard.press('Escape')
      await hold(page, 800)
      const r2 = page.getByRole('button', { name: /r2/ }).first()
      await clickAt(page, r2, 900)
      await text(page, /all pass/)
      await hold(page, 800)
      await highlight(page, page.getByText(/all pass/).first(), 'r2: every check passes', 3_000)
    },
  },
  {
    // The what-if: the engineer picks "Racks to 200 kW" and the impact lights up across power and cooling.
    clip: 'g03-whatif',
    run: async (page) => {
      await page.goto('/app/p/hall-a')
      await ready(page)
      const chip = page.locator('[data-tour="whatif-chip"]')
      await highlight(page, chip, 'What if racks go to 200 kW?', 2_200)
      await clickAt(page, chip, 900)
      const chain = page.getByRole('list', { name: 'Impact chain' })
      await expect(chain).toBeVisible(LONG)
      await text(page, 'Show all 18 impact chains')
      await text(page, 'Show all 60 findings')
      await hold(page, 900)
      await highlight(page, chain, 'Rack to busway to board to transformer, and rack to zone to CDU', 4_600)
      await highlight(page, page.getByText('Show all 18 impact chains').first(), '18 impact chains, 60 findings, all from the engine', 3_200)
      await hold(page, 1_200)
    },
  },
  {
    // The sign-off: the approved review page, the stamp with name, time and revision hash.
    clip: 'g04-review',
    run: async (page) => {
      await page.goto('/app/p/hall-a/review/r2')
      await text(page, 'APPROVED')
      await hold(page, 1_800)
      const stamp = page.getByRole('figure', { name: 'Approval stamp' })
      await expect(stamp).toContainText('sha256')
      await pointAt(page, stamp, 1_000)
      await highlight(page, stamp, 'Name, role, time and the revision hash', 4_400, { spot: true })
      const handoff = page.getByRole('region', { name: 'Handoff' })
      if (await handoff.count()) await highlight(page, handoff, 'Approval raises purchase requisitions in the ERP sandbox', 4_000, { spot: true })
      await hold(page, 800)
    },
  },
  {
    // The options: the 2N card with the R15 swap, a transformer that ships in time.
    clip: 'g05-options',
    run: async (page) => {
      await page.goto('/app/p/hall-a?tab=options')
      await text(page, /R15, line transformer/)
      await hold(page, 1_800)
      const card = page.getByRole('article', { name: 'Option 2N' })
      await highlight(page, page.getByText(/R15, line transformer/).first(), 'R15: swapped for a transformer that ships in time', 3_600)
      await highlight(page, card, 'The swap is re-checked: loading and fault level', 3_800, { spot: true })
      await hold(page, 800)
    },
  },
]

for (const beat of BEATS) {
  test(`guided ${beat.clip}`, async ({ page }) => {
    test.setTimeout(240_000)
    await installGuide(page)
    await beat.run(page)
    await expect(page.getByText('all companies, people and data are fictional').first()).toBeVisible()
    await hold(page, HANDLE)
    const video = page.video()
    await page.close() // finalises the recording
    await video?.saveAs(path.join(OUT, `${beat.clip}.webm`))
  })
}
