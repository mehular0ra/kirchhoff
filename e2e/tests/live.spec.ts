import { mkdirSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from './fixtures'

const OPTION = process.env.E2E_OPTION ?? '2N' // Task 14 records a second run with E2E_OPTION=DR for Pune Edge
const OUT = fileURLToPath(new URL('../out/', import.meta.url))

// Opt-in: this journey starts real agent runs (Gemini) on the deployed site, so it is never part of the default,
// deterministic suite (issue #7). Run it with `make e2e-live` (sets E2E_LIVE=1) when the controller asks for it.
test.skip(process.env.E2E_LIVE !== '1', 'live Hall B run is opt-in: set E2E_LIVE=1 (it calls the deployed agents)')

// Dry run (issue #24, runbook Step 0): E2E_MODE=auto runs the Auto autonomy mode (plan and option gates resolve by the
// tender's rules, so only the review gate waits for us); E2E_RELOAD=1 reloads the page mid-intake to prove the run
// resumes. Every gate is timed and the run's console errors and 5xx responses are written beside the run id, so the
// numbers to post on the issue are in e2e/out/*.json. The default (Ask, no reload) is the golden-capture path.
const MODE = process.env.E2E_MODE === 'auto' ? 'auto' : 'ask'
const RELOAD = process.env.E2E_RELOAD === '1'
// `make capture-export` reads live-run-<OPTION>.json for the Ask run, so that name must not change.
const OUT_FILE = `${OUT}live-run-${OPTION}${MODE === 'auto' ? '-auto' : ''}.json`

test('Hall B live run through every gate → sign-off → PRs and CRM stage visible', async ({ page }) => {
  test.setTimeout(15 * 60_000)
  const t0 = Date.now()
  const marks: Record<string, number> = {} // seconds since the run started, per milestone
  const consoleErrors: string[] = []
  const serverErrors: string[] = []
  const info: Record<string, unknown> = {}
  const mark = (name: string) => {
    marks[name] = Math.round((Date.now() - t0) / 100) / 10
  }
  const save = () => writeFileSync(OUT_FILE, JSON.stringify({ ...info, mode: MODE, option: OPTION, marks_s: marks, console_errors: consoleErrors, server_errors: serverErrors }, null, 2))
  page.on('console', (m) => {
    if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 300))
  })
  page.on('response', (r) => {
    if (r.status() >= 500) serverErrors.push(`${r.status()} ${r.request().method()} ${new URL(r.url()).pathname}`)
  })
  mkdirSync(OUT, { recursive: true })

  await page.goto('/app/p/hall-b')
  await page.getByRole('radio', { name: MODE === 'auto' ? /^Auto: resolve plan and option gates/ : /^Ask: pause at every gate/ }).click()
  await page.getByRole('button', { name: 'Start live run' }).click()
  await expect(page).toHaveURL(/\/app\/p\/hall-b\?run=/, { timeout: 30_000 })
  const runId = new URL(page.url()).searchParams.get('run')
  Object.assign(info, { run_id: runId, url: page.url() })
  mark('started')
  save() // written now, so a failed run still leaves its run id behind

  if (RELOAD) {
    // The heartbeat and the lease must hold over the long intake step, and a reload must pick the same run up again.
    await expect(page.getByRole('navigation', { name: 'Agent lanes' })).toBeVisible({ timeout: 60_000 })
    await page.waitForTimeout(20_000)
    await page.reload()
    await expect(page).toHaveURL(new RegExp(`run=${runId}`))
    await expect(page.getByRole('navigation', { name: 'Agent lanes' })).toBeVisible({ timeout: 60_000 })
    mark('reloaded_and_resumed')
    save()
  }

  if (MODE === 'ask') {
    // Plan gate (end of P1): §4.2 vs Appendix B → compare all three, then approve.
    await expect(page.getByText('Waiting for you · plan gate')).toBeVisible({ timeout: 5 * 60_000 })
    mark('plan_gate')
    const plan = page.getByRole('region', { name: 'Plan' })
    await plan.getByRole('radio', { name: 'Compare all three topologies' }).click()
    await plan.getByRole('button', { name: 'Approve plan' }).click()

    // Option gate (end of P2): costed options; 2N is the golden path (DR for the Pune Edge capture).
    const select = page.getByRole('button', { name: `Select ${OPTION}` })
    await expect(select).toBeVisible({ timeout: 5 * 60_000 })
    mark('option_gate')
    // Which option carries a "recommended" marker (the runbook asks for it: the plan-gate answer can move it).
    const marked = page.locator('article[aria-label^="Option "]').filter({ hasText: /recommended/i })
    info.recommended_option = (await marked.count()) ? await marked.first().getAttribute('aria-label') : null
    save()
    await select.click()
  }

  // Review gate (end of P3: routing, checker, fix loop, docs).
  const review = page.locator('[data-tour="sign-off"]', { hasText: 'Review and sign' })
  await expect(review).toBeVisible({ timeout: 8 * 60_000 })
  mark('review_gate')
  save()
  await review.click()
  await expect(page).toHaveURL(/\/app\/p\/hall-b\/review\//)
  await page.getByRole('textbox', { name: 'Review comment' }).fill('Checked the fixes and the assumptions ledger. Approved for procurement.')
  await page.getByRole('button', { name: 'Approve and sign as You (Demo Reviewer)' }).click()
  const stamp = page.getByRole('figure', { name: 'Approval stamp' })
  await expect(stamp).toContainText('You (Demo Reviewer)')
  await expect(stamp).toContainText('Reviewer')
  mark('signed')

  // P4: PRs in the ERP sandbox and the CRM stage.
  const handoff = page.getByRole('region', { name: 'Handoff' })
  await expect(handoff).toContainText(/PR-2026-\d{4}/, { timeout: 3 * 60_000 })
  await expect(handoff).toContainText('CRM opportunity moved to Design approved', { timeout: 3 * 60_000 })
  mark('prs_and_crm')
  save()
  await page.goto('/app/integrations')
  const latest = page.getByRole('region', { name: 'Latest handoff' })
  await expect(latest).toContainText('hall-b · revision')
  await expect(latest).toContainText('Hall B design-build')
  await expect(page.getByRole('status').filter({ hasText: 'showing cached snapshot' })).toHaveCount(0)
})
