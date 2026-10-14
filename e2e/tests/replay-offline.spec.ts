import { expect, test } from './fixtures'

type Bundle = { events?: unknown[]; what_ifs?: unknown[] }
const OFFLINE = [/\/api\//, /firestore\.googleapis\.com/, /firebaseappcheck\.googleapis\.com/]

test.describe('static-first: /api, Firestore and App Check unreachable (spec §11)', () => {
  test.beforeEach(async ({ page }) => {
    for (const pattern of OFFLINE) await page.route(pattern, (route) => route.abort('connectionrefused'))
  })

  test('a recorded run replays from the static bundle', async ({ page, request }) => {
    const bundle = (await (await request.get('/demo/projects/hall-a.json')).json()) as Bundle
    test.skip(!bundle.events?.length, 'Hall A has no recorded events until the golden capture (Task 14)')
    await page.goto('/app/p/hall-a?replay=1')
    await expect(page.getByText('Time-compressed replay of a recorded run')).toBeVisible()
    await expect(page.getByRole('button', { name: /^(Pause|Play) replay$/ })).toBeVisible()
    await expect(page.getByRole('navigation', { name: 'Agent lanes' })).toContainText('Intake', { timeout: 30_000 })
  })

  test('the signed Hall A and its first-pass findings load', async ({ page }) => {
    await page.goto('/app/p/hall-a?tab=matrix&rev=r1')
    await expect(page.getByRole('button', { name: 'R05 FA-01: Fail' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'R11 H-Z2: Fail' })).toBeVisible()
  })

  test('a precomputed what-if chip works offline', async ({ page, request }) => {
    const bundle = (await (await request.get('/demo/projects/hall-a.json')).json()) as Bundle
    test.skip(!bundle.what_ifs?.length, 'chip what-ifs are precomputed once WS1 ships what_if (P1 Task 15)')
    await page.goto('/app/p/hall-a')
    await page.locator('[data-tour="whatif-chip"]').click()
    await expect(page.getByRole('list', { name: 'Impact chain' })).toBeVisible()
  })

  test('Integrations falls back to the cached snapshot', async ({ page }) => {
    await page.goto('/app/integrations')
    await expect(page.getByRole('status').filter({ hasText: 'API unreachable — showing cached snapshot' })).toBeVisible()
    await expect(page.getByRole('region', { name: 'Latest handoff' })).toContainText('PR-2026-0142')
  })
})
