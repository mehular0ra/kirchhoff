import { mkdirSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test } from '../tests/fixtures'
import { clickAt, glide, highlight, installGuide } from './guide'

/**
 * One real Hall B live run with a visible cursor and labelled highlights at every human gate (Mehul's review, 18 Oct 2026):
 * Ask mode, the tender dropped, the plan approved, the topology chosen, r1 and r2 viewed. It STOPS at the review gate: nothing
 * is signed, so no purchase requisitions or CRM stage move reach the shared sandbox. It starts a real agent run (Gemini, about
 * 7 US cents), so it is opt-in.
 *
 *   E2E_FOOTAGE=1 E2E_LIVE=1 npx playwright test --project=footage -g "guided live run"
 *
 * Writes guided-live-full.webm and guided-live-marks.json (seconds since the test started; the recording starts a moment earlier).
 */
const HERE = path.dirname(fileURLToPath(import.meta.url))
const OUT = process.env.FOOTAGE_OUT ?? path.join(HERE, '..', 'out', 'footage')
mkdirSync(OUT, { recursive: true })
test.skip(process.env.E2E_LIVE !== '1', 'starts a real Hall B run (Gemini): set E2E_LIVE=1')

test('guided live run: one recording with marks', async ({ page }) => {
  test.setTimeout(20 * 60_000)
  const t0 = Date.now()
  const marks: Record<string, number> = {}
  const mark = (name: string) => {
    marks[name] = Math.round((Date.now() - t0) / 100) / 10
  }
  const pause = (ms: number) => page.waitForTimeout(ms)
  await installGuide(page)

  // The tender package, Ask mode (the engineer decides at every gate), then the drop onto the drop zone.
  await page.goto('/app/p/hall-b')
  const zone = page.getByRole('region', { name: 'Drop the tender PDF and drawing to start' })
  await expect(zone).toBeVisible()
  await pause(2_000)
  mark('page_ready')
  const ask = page.getByRole('radio', { name: /^Ask: pause at every gate/ })
  await highlight(page, ask, 'Ask mode: the engineer decides at every gate', 2_600)
  await clickAt(page, ask, 900)
  await pause(800)
  await highlight(page, zone, 'Drop the tender PDF and the drawing to start', 2_200)
  const b = (await zone.boundingBox())!
  await glide(page, { x: b.x + b.width / 2, y: b.y + b.height / 2 }, 900)
  await zone.dispatchEvent('dragover', {})
  await pause(1_400)
  mark('dragover')
  await zone.dispatchEvent('drop', {})
  await expect(page).toHaveURL(/\/app\/p\/hall-b\?run=/, { timeout: 30_000 })
  const runId = new URL(page.url()).searchParams.get('run')
  mark('started')

  // Intake reads the tender; at the plan gate the requirement cards, the quote counter and the open question are on screen.
  await expect(page.getByText('Waiting for you · plan gate')).toBeVisible({ timeout: 5 * 60_000 })
  mark('plan_gate')
  await expect(page.getByText(/quotes verified/).first()).toBeVisible()
  await pause(1_000)
  await highlight(page, page.getByText(/quotes verified/).first(), 'Each requirement carries a verified quote', 3_000)
  const contradiction = page.getByText('Contradiction found').first()
  if (await contradiction.count()) await highlight(page, contradiction, 'And a contradiction in the tender, flagged for the engineer', 3_200)
  const plan = page.getByRole('region', { name: 'Plan' })
  const three = plan.getByRole('radio', { name: 'Compare all three topologies' })
  await highlight(page, plan, 'The plan gate: the engineer reviews it', 2_400)
  await clickAt(page, three, 900)
  await pause(1_200)
  const approve = plan.getByRole('button', { name: 'Approve plan' })
  await highlight(page, approve, 'The engineer approves the plan', 1_800)
  await clickAt(page, approve, 900)
  mark('plan_approved')

  // The agents at work until the option gate.
  const lanes = page.getByRole('navigation', { name: 'Agent lanes' })
  await pause(2_500)
  await highlight(page, lanes, 'Layout, Power and Cooling work in parallel; the engineer watches each lane', 4_200, { pad: 4 })
  const select = page.getByRole('button', { name: 'Select 2N' })
  await expect(select).toBeVisible({ timeout: 5 * 60_000 })
  mark('option_gate')
  await expect(page.getByText(/R15, line transformer/).first()).toBeVisible()
  await pause(1_500)
  await highlight(page, page.getByText(/R15, line transformer/).first(), 'R15: the transformer swapped for one that ships in time', 3_600)
  await pause(2_000)
  mark('option_hold_end')
  await clickAt(page, select, 900)
  mark('option_selected')

  // The 3D hall from the first checked revision (r1, two findings), then the fixed one (r2, all pass) at the review gate.
  try {
    await clickAt(page, page.getByRole('tab', { name: '3D Hall' }), 800)
    const r1 = page.getByRole('button', { name: /-r1/ }).first()
    await expect(r1).toBeVisible({ timeout: 5 * 60_000 })
    await clickAt(page, r1, 800)
    mark('r1_shown')
    await pause(1_500)
    await highlight(page, page.getByText(/R05|R11/).first(), 'The checker found two failures; the fix loop repairs them', 3_800)
  } catch (e) {
    console.warn('guided live: the r1 interlude was skipped:', String(e).split('\n')[0])
  }
  const review = page.locator('[data-tour="sign-off"]', { hasText: 'Review and sign' })
  await expect(review).toBeVisible({ timeout: 8 * 60_000 })
  mark('review_gate')
  try {
    await highlight(page, review, 'Ready for the engineer to review and sign', 2_800)
    await clickAt(page, page.getByRole('button', { name: /-r2/ }).first(), 900)
    mark('r2_shown')
    await pause(1_500)
    await highlight(page, page.getByText(/all pass/).first(), 'r2: every check passes', 3_000)
    mark('r2_held')
  } catch (e) {
    console.warn('guided live: the r2 view was skipped:', String(e).split('\n')[0])
  }
  // Stop here: nothing is signed (the shared ERP/CRM sandbox is untouched).
  await pause(2_000)
  mark('end')
  await expect(page.getByText('all companies, people and data are fictional').first()).toBeVisible()
  writeFileSync(path.join(OUT, 'guided-live-marks.json'), JSON.stringify({ run_id: runId, signed: false, marks_s: marks }, null, 2))
  const video = page.video()
  await page.close()
  await video?.saveAs(path.join(OUT, 'guided-live-full.webm'))
})
