import { mkdirSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from './fixtures'

const OPTION = process.env.E2E_OPTION ?? '2N' // Task 14 records a second run with E2E_OPTION=DR for Pune Edge
const OUT = fileURLToPath(new URL('../out/', import.meta.url))

// Opt-in: this journey starts real agent runs (Gemini) on the deployed site, so it is never part of the default,
// deterministic suite (issue #7). Run it with `make e2e-live` (sets E2E_LIVE=1) when the controller asks for it.
test.skip(process.env.E2E_LIVE !== '1', 'live Hall B run is opt-in: set E2E_LIVE=1 (it calls the deployed agents)')

test('Hall B live run through every gate → sign-off → PRs and CRM stage visible', async ({ page }) => {
  test.setTimeout(15 * 60_000)
  await page.goto('/app/p/hall-b')
  await page.getByRole('radio', { name: /^Ask: pause at every gate/ }).click()
  await page.getByRole('button', { name: 'Start live run' }).click()
  await expect(page).toHaveURL(/\/app\/p\/hall-b\?run=/, { timeout: 30_000 })
  const runId = new URL(page.url()).searchParams.get('run')
  mkdirSync(OUT, { recursive: true })
  writeFileSync(`${OUT}live-run-${OPTION}.json`, JSON.stringify({ run_id: runId, option: OPTION, url: page.url() }, null, 2))

  // Plan gate (end of P1): §4.2 vs Appendix B → compare all three, then approve.
  await expect(page.getByText('Waiting for you · plan gate')).toBeVisible({ timeout: 5 * 60_000 })
  const plan = page.getByRole('region', { name: 'Plan' })
  await plan.getByRole('radio', { name: 'Compare all three topologies' }).click()
  await plan.getByRole('button', { name: 'Approve plan' }).click()

  // Option gate (end of P2): costed options; 2N is the golden path (DR for the Pune Edge capture).
  const select = page.getByRole('button', { name: `Select ${OPTION}` })
  await expect(select).toBeVisible({ timeout: 5 * 60_000 })
  await select.click()

  // Review gate (end of P3: routing, checker, fix loop, docs).
  const review = page.locator('[data-tour="sign-off"]', { hasText: 'Review and sign' })
  await expect(review).toBeVisible({ timeout: 8 * 60_000 })
  await review.click()
  await expect(page).toHaveURL(/\/app\/p\/hall-b\/review\//)
  await page.getByRole('textbox', { name: 'Review comment' }).fill('Checked the fixes and the assumptions ledger. Approved for procurement.')
  await page.getByRole('button', { name: 'Approve and sign as You (Demo Reviewer)' }).click()
  const stamp = page.getByRole('figure', { name: 'Approval stamp' })
  await expect(stamp).toContainText('You (Demo Reviewer)')
  await expect(stamp).toContainText('Reviewer')

  // P4: PRs in the ERP sandbox and the CRM stage.
  const handoff = page.getByRole('region', { name: 'Handoff' })
  await expect(handoff).toContainText(/PR-2026-\d{4}/, { timeout: 3 * 60_000 })
  await expect(handoff).toContainText('CRM opportunity moved to Design approved', { timeout: 3 * 60_000 })
  await page.goto('/app/integrations')
  const latest = page.getByRole('region', { name: 'Latest handoff' })
  await expect(latest).toContainText('hall-b · revision')
  await expect(latest).toContainText('Hall B design-build')
  await expect(page.getByRole('status').filter({ hasText: 'showing cached snapshot' })).toHaveCount(0)
})
