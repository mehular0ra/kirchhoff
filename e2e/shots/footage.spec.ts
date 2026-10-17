import { mkdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test } from '../tests/fixtures'
import type { Page } from '@playwright/test'

/**
 * Screen footage for the demo video (issue #25), one clip per storyboard beat, named as docs/submission/video/edit-plan.md
 * expects (`vNN-<beat>`). Every value on screen comes from the app's own data; nothing is typed into a number, and the
 * fictional-data banner is asserted to be on the page for every clip. Each clip has 2 s of handles before and after.
 *
 *   rehearsal   E2E_FOOTAGE=1 npx playwright test --project=footage                      (writes e2e/out/footage/*.webm)
 *   one beat    E2E_FOOTAGE=1 npx playwright test --project=footage -g v06
 *   deployed    E2E_BASE_URL=https://kirchhoff.web.app is the default; run it after the UI freeze and the golden-capture deploy.
 *   then        shots/footage_to_mp4.sh converts the clips to .mp4 and prints each clip's real length for the issue checklist.
 *
 * Beats that need the recorded run (events, options) from the golden capture fail with a clear message until it is deployed.
 * Beat 3 (problem card), 12 (proof) and 13 (end card) have no product footage; beat 5 comes from the live run
 * (footage-live.spec.ts). Beat 9 (sign-off) is the static `v09-sign-off` clip below, the approved Hall A review page, which touches no
 * shared state; a SIGNED live run's sign-off is the alternative `v09-sign-off-live` (footage_cut.sh), named apart so neither overwrites the other.
 */
const HERE = path.dirname(fileURLToPath(import.meta.url))
const OUT = process.env.FOOTAGE_OUT ?? path.join(HERE, '..', 'out', 'footage')
mkdirSync(OUT, { recursive: true })

const HANDLE = 2_000
const LONG = { timeout: 60_000 }
const hold = (page: Page, ms: number) => page.waitForTimeout(ms)
const text = (page: Page, t: string | RegExp) => expect(page.getByText(t).first()).toBeVisible(LONG)

/** Waits for the 3D hall and the lanes (or an open drawer) to render, then holds the 2 s handle. */
const ready = async (page: Page) => {
  await expect(page.getByRole('navigation', { name: 'Agent lanes' }).or(page.getByRole('dialog')).first()).toBeVisible(LONG)
  await hold(page, 2_500) // the 3D hall animates in
  await hold(page, HANDLE)
}

type Beat = { clip: string; run: (page: Page) => Promise<void> }

const BEATS: Beat[] = [
  {
    // Hall A recorded design, r1 in view: the camera flies to H-Z2 where it crosses above the busway (the failing R11).
    clip: 'v01-cold-open',
    run: async (page) => {
      await page.goto('/app/p/hall-a?tab=hall&rev=r1')
      await ready(page)
      await page.getByRole('textbox', { name: 'Ask the co-pilot' }).fill('Show me H-Z2')
      await page.getByRole('button', { name: 'Send' }).click()
      await text(page, 'Showing H-Z2.')
      await text(page, /Tender §6\.3\.4/)
      await hold(page, 5_000) // the fly-in and the clause chip
    },
  },
  {
    // The held green-hall frame the title card sits on: the signed revision, everything passing.
    clip: 'v02-title',
    run: async (page) => {
      await page.goto('/app/p/hall-a?tab=hall')
      await ready(page)
      await text(page, /signed by Priya Raman/)
      await hold(page, 6_000)
    },
  },
  {
    // Recorded run replay: Intake streams requirement cards marked "quote verified" (needs the golden capture's events).
    clip: 'v04-tender-in',
    run: async (page) => {
      await page.goto('/app/p/hall-a?replay=1')
      await text(page, /quote verified/i)
      await hold(page, HANDLE)
      await hold(page, 12_000)
    },
  },
  {
    // The checker: matrix at r1 (2 fails), the R05 drawer, the R11 drawer, then r2 all pass.
    clip: 'v06-checker',
    run: async (page) => {
      await page.goto('/app/p/hall-a?tab=matrix&rev=r1')
      await text(page, '149 checks')
      await hold(page, HANDLE)
      await hold(page, 3_000) // the counter and the matrix read at full speed
      const fails = page.getByRole('button', { name: /: Fail$/ })
      await expect(fails).toHaveCount(2)
      await fails.nth(0).click()
      const drawer = page.getByRole('dialog').first()
      await expect(drawer).toContainText('2.16%')
      await expect(drawer).toContainText('§4.6')
      await hold(page, 6_000)
      await page.keyboard.press('Escape')
      await hold(page, 800)
      await fails.nth(1).click()
      await expect(drawer).toContainText('§6.3.4')
      await hold(page, 6_000)
      await page.keyboard.press('Escape')
      await hold(page, 800)
      await page.getByRole('button', { name: /r2/ }).first().click()
      await text(page, /all pass/)
      await hold(page, 3_000)
    },
  },
  {
    // The R15 swap on the 2N option card ("TX-2500 -> TX-3150 (R15, line transformer)", loading 38.07% / 76.15%): the
    // recorded run's options (needs the golden capture). The card does not show lead-time weeks or stock, see issue #25.
    clip: 'v07-erp-swap',
    run: async (page) => {
      await page.goto('/app/p/hall-a?tab=options')
      await text(page, /R15, line transformer/)
      await hold(page, HANDLE)
      await hold(page, 8_000)
    },
  },
  {
    // The what-if on the signed revision r2 from a fresh page (a finding question moves the view to r1, issue #37). Silent:
    // the spoken question is laid over it in the edit.
    clip: 'v08-what-if-voice',
    run: async (page) => {
      await page.goto('/app/p/hall-a')
      await ready(page)
      await page.locator('[data-tour="whatif-chip"]').click()
      await expect(page.getByRole('list', { name: 'Impact chain' })).toBeVisible()
      await text(page, 'Show all 18 impact chains')
      await text(page, 'Show all 60 findings')
      await hold(page, 8_000)
    },
  },
  {
    // The sign-off beat without touching the shared sandbox: the recorded run's approved review page, its stamp with the revision hash.
    // The live variant, signing as "You (Demo Reviewer)" and moving the PRs and the CRM stage, is footage-live.spec.ts.
    clip: 'v09-sign-off',
    run: async (page) => {
      await page.goto('/app/p/hall-a/review/r2')
      await text(page, 'APPROVED')
      await hold(page, HANDLE)
      const stamp = page.getByRole('figure', { name: 'Approval stamp' })
      await expect(stamp).toContainText('sha256')
      await hold(page, 6_000)
    },
  },
  {
    // The bids inbox: six emails, newest first; the Hall B tender is triaged (Pursue, with its fit reasons); the scanned BOQ is marked
    // "Not verified (scan)" and its email is a deterministic Decline. Nothing is clicked that writes: "Pursue" would move a CRM stage in
    // the shared sandbox when the API is up, so this clip only reads (the recorded triage comes from the static bundle).
    clip: 'v12-inbox-triage',
    run: async (page) => {
      await page.goto('/app/inbox')
      await expect(page.getByRole('heading', { name: 'Bids inbox', level: 1 })).toBeVisible(LONG)
      await expect(page.locator('a[href^="/app/inbox/em-"]')).toHaveCount(6)
      await hold(page, HANDLE)
      await hold(page, 2_500) // the list: six emails, newest first
      await page.locator('a[href="/app/inbox/em-hall-b"]').click()
      const detail = page.getByRole('region', { name: 'Email' })
      const fit = detail.getByRole('region', { name: 'Fit verdict' })
      await expect(fit).toContainText('Pursue', LONG)
      await expect(fit).toContainText('Day-zero supply')
      await hold(page, 4_500) // the verdict and its reasons
      await page.goto('/app/inbox/em-vindhya-boq')
      await expect(detail.getByText('Not verified (scan)').first()).toBeVisible(LONG)
      await expect(detail.getByRole('region', { name: 'Fit verdict' })).toContainText('only on a scanned page')
      await hold(page, 4_500) // the scan is never trusted: its fit rule asks for a text copy
    },
  },
  {
    // The trust moment: a failing finding cites its tender clause; click the clause and the tender PDF opens on that page with a box
    // around the quote and "Verified quote". Hall A r1, R05 FA-01 (section 4.6). Silent: the voice is laid over it in the edit.
    clip: 'v13-trust-quote',
    run: async (page) => {
      await page.goto('/app/p/hall-a?tab=matrix&rev=r1')
      await text(page, '149 checks')
      await hold(page, HANDLE)
      await page.getByRole('button', { name: 'R05 FA-01: Fail' }).click()
      const drawer = page.getByRole('dialog').first()
      await expect(drawer).toContainText('2.16%')
      await hold(page, 3_500) // the finding, its formula and its clause chip
      await page.getByRole('button', { name: /^Open tender §4\.6 · p\.\d+$/ }).first().click()
      const source = page.getByRole('dialog', { name: /^Tender §4\.6 · page \d+$/ })
      await expect(source).toContainText('Verified quote:')
      await expect(source.locator('canvas').first()).toBeVisible({ timeout: 20_000 }) // the PDF page rendered
      await expect(page.getByTestId('citation-highlight').first()).toBeVisible({ timeout: 20_000 }) // the box around the quote
      await hold(page, 6_000)
    },
  },
  {
    clip: 'v10-integrations',
    run: async (page) => {
      await page.goto('/app/integrations')
      await expect(page.getByRole('region', { name: 'Latest handoff' })).toBeVisible(LONG)
      await hold(page, HANDLE)
      await hold(page, 6_000)
    },
  },
  {
    clip: 'v11-grid-solar',
    run: async (page) => {
      await page.goto('/app/p/grid-132kv')
      await expect(page.getByRole('region', { name: 'Mini SLD' })).toBeVisible(LONG)
      await hold(page, HANDLE)
      await hold(page, 4_000)
      await page.goto('/app/p/solar-5mwp')
      await text(page, /STR-28/)
      await expect(page.getByRole('img', { name: 'Site geometry' })).toBeVisible(LONG)
      await hold(page, 5_000)
    },
  },
]

for (const beat of BEATS) {
  test(beat.clip, async ({ page }) => {
    test.setTimeout(180_000)
    await beat.run(page)
    // The banner must be in frame for every clip (by text: an open drawer is a modal and hides the banner role).
    await expect(page.getByText('all companies, people and data are fictional').first()).toBeVisible()
    await hold(page, HANDLE)
    const video = page.video()
    await page.close() // finalises the recording
    await video?.saveAs(path.join(OUT, `${beat.clip}.webm`))
  })
}
