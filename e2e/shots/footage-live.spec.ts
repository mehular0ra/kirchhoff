import { mkdirSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test } from '../tests/fixtures'

/**
 * Footage from one real Hall B live run (issue #25), recorded as one long clip with a marks file, because the run's own
 * pace is the footage: the drop zone, Intake, the agents at work, the option gate and the sign-off with its PRs and CRM
 * stage. shots/footage_cut.sh slices it into the beat clips with 2 s handles.
 *
 *   E2E_FOOTAGE=1 E2E_LIVE=1 npx playwright test --project=footage -g "live run"
 *
 * This starts a real agent run on the deployed site (Gemini), so it is opt-in. Run it after the UI freeze and after the
 * golden capture, on the final deploy. Pauses are added where a viewer needs time to read. Nothing is typed by hand
 * except the review comment the live spec also uses.
 */
const HERE = path.dirname(fileURLToPath(import.meta.url))
const OUT = process.env.FOOTAGE_OUT ?? path.join(HERE, '..', 'out', 'footage')
mkdirSync(OUT, { recursive: true })
test.skip(process.env.E2E_LIVE !== '1', 'starts a real Hall B run (Gemini): set E2E_LIVE=1')

test('live run: one recording with marks', async ({ page }) => {
  test.setTimeout(20 * 60_000)
  const t0 = Date.now()
  const marks: Record<string, number> = {} // seconds since the test started (the recording starts a moment earlier)
  const mark = (name: string) => {
    marks[name] = Math.round((Date.now() - t0) / 100) / 10
  }
  const pause = (ms: number) => page.waitForTimeout(ms)

  // Beat 4 opening: the tender package, then the drop onto the drop zone (the zone highlights while it is over it).
  await page.goto('/app/p/hall-b')
  const zone = page.getByRole('region', { name: 'Drop the tender PDF and drawing to start' })
  await expect(zone).toBeVisible()
  await page.getByRole('radio', { name: /^Ask: pause at every gate/ }).click()
  await pause(2_500)
  mark('page_ready')
  await zone.dispatchEvent('dragover', {})
  await pause(1_500)
  mark('dragover')
  await zone.dispatchEvent('drop', {})
  await expect(page).toHaveURL(/\/app\/p\/hall-b\?run=/, { timeout: 30_000 })
  const runId = new URL(page.url()).searchParams.get('run')
  mark('started')

  // Intake reads the tender; at the plan gate the requirement cards, the quote counter and the open question are on screen.
  await expect(page.getByText('Waiting for you · plan gate')).toBeVisible({ timeout: 5 * 60_000 })
  mark('plan_gate')
  await expect(page.getByText(/quotes verified/).first()).toBeVisible()
  await pause(5_000) // the cards, the "quote verified" chips and the counter read at full speed
  const plan = page.getByRole('region', { name: 'Plan' })
  await plan.getByRole('radio', { name: 'Compare all three topologies' }).click()
  await pause(2_000)
  await plan.getByRole('button', { name: 'Approve plan' }).click()
  mark('plan_approved')

  // The agents at work (the compressed beat): Layout, Power and Cooling, until the option gate.
  const select = page.getByRole('button', { name: 'Select 2N' })
  await expect(select).toBeVisible({ timeout: 5 * 60_000 })
  mark('option_gate')
  await expect(page.getByText(/R15, line transformer/).first()).toBeVisible() // the swap line on the 2N card
  await pause(9_000) // read the three cards and the R15 swap
  mark('option_hold_end')
  await select.click()
  mark('option_selected')
  // The Options tab stays selected after the gate, and the 3D hall is drawn from the first checked revision: go back to it, so the
  // routing, the two findings and the fix loop are on screen in 3D (the beat-8 picture).
  await page.getByRole('tab', { name: '3D Hall' }).click()
  // In an Ask-mode run the hall stays empty ("No revision yet") until a revision is picked: when r1 exists, show it (the two failing findings in 3D).
  const r1 = page.getByRole('button', { name: /-r1/ }).first()
  await expect(r1).toBeVisible({ timeout: 5 * 60_000 })
  await r1.click()
  mark('r1_shown')
  await pause(5_000)

  // The Checker and the fix loop, then the review gate.
  const review = page.locator('[data-tour="sign-off"]', { hasText: 'Review and sign' })
  await expect(review).toBeVisible({ timeout: 8 * 60_000 })
  mark('review_gate')
  await page.getByRole('button', { name: /-r2/ }).first().click() // the fixed revision, all checks passing
  mark('r2_shown')
  await pause(4_000)
  mark('r2_held')
  if (process.env.E2E_FOOTAGE_SIGN === '0') {
    // Stop here: nothing is signed, so no purchase requisitions reach the shared ERP sandbox and no CRM stage moves (a signed run
    // stays visible to everyone on the Integrations page until the next seed). The marks and the recording are still written;
    // footage_cut.sh (FOOTAGE_SKIP_MISSING=1) skips the clip that needs the sign-off.
    await pause(3_000)
    mark('end')
    await expect(page.getByText('all companies, people and data are fictional').first()).toBeVisible()
    writeFileSync(path.join(OUT, 'live-run-marks.json'), JSON.stringify({ run_id: runId, signed: false, marks_s: marks }, null, 2))
    const unsigned = page.video()
    await page.close()
    await unsigned?.saveAs(path.join(OUT, 'live-run-full.webm'))
    return
  }
  await pause(2_000)
  await review.click()
  await expect(page).toHaveURL(/\/app\/p\/hall-b\/review\//)
  await pause(3_000)
  mark('review_page_ready')
  await page.mouse.wheel(0, 600) // the diff, the assumptions ledger and the "not checked" list
  await pause(3_000)
  await page.mouse.wheel(0, 600)
  await pause(3_000)
  await page.mouse.wheel(0, -1200)
  await pause(1_500)
  await page.getByRole('textbox', { name: 'Review comment' }).fill('Checked the fixes and the assumptions ledger. Approved for procurement.')
  await pause(1_500)
  mark('approve_click')
  await page.getByRole('button', { name: 'Approve and sign as You (Demo Reviewer)' }).click()
  const stamp = page.getByRole('figure', { name: 'Approval stamp' })
  await expect(stamp).toContainText('You (Demo Reviewer)')
  mark('signed')
  await pause(5_000) // the stamp with its time and revision hash
  const handoff = page.getByRole('region', { name: 'Handoff' })
  await expect(handoff).toContainText(/PR-2026-\d{4}/, { timeout: 3 * 60_000 })
  await expect(handoff).toContainText('CRM opportunity moved to Design approved', { timeout: 3 * 60_000 })
  mark('prs_and_crm')
  await pause(6_000)
  mark('end')
  await expect(page.getByText('all companies, people and data are fictional').first()).toBeVisible()

  writeFileSync(path.join(OUT, 'live-run-marks.json'), JSON.stringify({ run_id: runId, marks_s: marks }, null, 2))
  const video = page.video()
  await page.close() // finalises the recording
  await video?.saveAs(path.join(OUT, 'live-run-full.webm'))
})
