import { BANNER, expect, startTour, test, tourCardPositions } from './fixtures'

type Snapshot = { erp: { prs: { id: string; project_id: string }[] } }
type Bundle = { events?: unknown[]; what_ifs?: unknown[] }

const TOUR: (string | RegExp)[] = [
  "Your firm's live projects",
  'Every number is checked and cited',
  'Open a finding and its source',
  /agents designed this|The agents that designed this/,
  'Try it: racks to 200 kW',
  'Approval pushed these PRs to ERP and moved the CRM deal',
  'Now run it live yourself',
]

test.describe('first visit', () => {
  test.use({ welcomed: false })

  test('landing → welcome → all seven tour steps', async ({ page }) => {
    // Known bug (issue #10): at 1440x900 the tour card of step 1 is placed above the viewport, so Next cannot be
    // pressed. Playwright reports "expected to fail but passed" once it is fixed: then delete this line.
    test.fail(true, 'issue #10: tour card off-screen on step 1')
    await page.goto('/')
    await page.getByRole('link', { name: 'Enter the demo workspace (no login)' }).click()
    await expect(page.getByRole('note').filter({ hasText: BANNER })).toBeVisible()
    await page.getByRole('button', { name: 'Take the 2-minute tour' }).click()
    const tour = page.getByRole('dialog', { name: 'Guided tour' })
    for (const [i, title] of TOUR.entries()) {
      await expect(tour.getByText(`Step ${i + 1} of ${TOUR.length}`)).toBeVisible()
      await expect(tour.getByRole('heading', { name: title })).toBeVisible()
      await expect(tour.getByText('Loading this part of the workspace…')).toBeHidden({ timeout: 20_000 })
      // A short action timeout: a card that cannot be pressed fails here, not by exhausting the whole test timeout.
      await tour.getByRole('button', { name: i === TOUR.length - 1 ? 'Finish' : 'Next' }).click({ timeout: 5_000 })
    }
    await expect(tour).toBeHidden()
  })

  test('every tour card stays inside the viewport (desktop)', async ({ page }) => {
    // Known bug (issue #10): the cards of steps 1, 3 and 4 are outside the viewport.
    test.fail(true, 'issue #10: tour cards of steps 1, 3 and 4 are off-screen')
    await startTour(page)
    const cards = await tourCardPositions(page)
    expect(cards.filter((c) => !c.inView), 'cards outside the viewport').toEqual([])
  })
})

test('Hall A: the signed revision is clean and the first one cites the tender', async ({ page, request }) => {
  const bundle = (await (await request.get('/demo/projects/hall-a.json')).json()) as { findings: Record<string, unknown[]> }
  const hasBbox = /"bbox":\s*\[/.test(JSON.stringify(bundle.findings))
  await page.goto('/app/p/hall-a?tab=matrix')
  await expect(page.getByRole('table', { name: 'Compliance matrix' })).toBeVisible()
  await expect(page.getByRole('button', { name: /: Fail$/ })).toHaveCount(0)
  await page.goto('/app/p/hall-a?tab=matrix&rev=r1')
  await expect(page.getByRole('button', { name: 'R11 H-Z2: Fail' })).toBeVisible()
  await page.getByRole('button', { name: 'R05 FA-01: Fail' }).click()
  await expect(page.getByRole('img', { name: /^Value .+ against limit .+: Fail$/ })).toBeVisible()
  await page.getByRole('button', { name: /^Open tender §4\.6 · p\.\d+$/ }).first().click()
  const source = page.getByRole('dialog', { name: /^Tender §4\.6 · page \d+$/ })
  await expect(source).toBeVisible()
  await expect(source).toContainText('Verified quote:')
  await expect(source.locator('canvas').first()).toBeVisible({ timeout: 20_000 }) // the PDF page rendered
  if (hasBbox) {
    await expect(page.getByTestId('citation-highlight').first()).toBeVisible({ timeout: 20_000 })
  } else {
    // Issue #11: the provisional bundle has no pdfplumber boxes until the golden capture (Task 14).
    test.info().annotations.push({ type: 'no-bbox-until-golden-capture', description: 'issue #11' })
  }
})

test('what-if chip lights the impact chain within the spec budget', async ({ page }) => {
  await page.goto('/app/p/hall-a')
  const chip = page.locator('[data-tour="whatif-chip"]')
  await expect(chip).toHaveAccessibleName('Racks → 200 kW')
  const started = Date.now()
  await chip.click()
  await expect(page.getByRole('list', { name: 'Impact chain' })).toBeVisible()
  await expect(page.getByRole('list', { name: 'What-if failures' })).toContainText('R01')
  expect(Date.now() - started).toBeLessThan(5_000) // spec §6.4: < 3 s, plus rendering slack
})

test('Integrations: Hall A PRs in ERP and the CRM stage, labelled sandbox', async ({ page, request }) => {
  const snap = (await (await request.get('/demo/integrations.json')).json()) as Snapshot
  const hallA = snap.erp.prs.filter((p) => p.project_id === 'hall-a').map((p) => p.id)
  expect(hallA.length).toBeGreaterThan(0)
  await page.goto('/app/integrations')
  const handoff = page.getByRole('region', { name: 'Latest handoff' })
  for (const id of hallA) await expect(handoff).toContainText(id)
  await expect(handoff).toContainText('Hall A design-build')
  await expect(handoff).toContainText('CRM stage: Design approved')
  await expect(page.getByText('sandbox (simulated)').first()).toBeVisible()
})

test('asset packs render from their static bundles', async ({ page, request }) => {
  for (const pid of ['grid-132kv', 'solar-5mwp']) {
    const res = await request.get(`/demo/projects/${pid}.json`)
    const isBundle = res.ok() && (res.headers()['content-type'] ?? '').includes('json')
    test.skip(!isBundle, `${pid}.json not generated yet (WS1 asset packs)`)
    await page.goto(`/app/p/${pid}`)
    await expect(page.getByRole('table', { name: 'Asset options' })).toBeVisible()
  }
  await page.goto('/app/p/grid-132kv')
  await expect(page.getByRole('region', { name: 'Mini SLD' })).toBeVisible()
})

test('the static Hall A bundle carries a recorded run and the five chips', async ({ request }) => {
  const bundle = (await (await request.get('/demo/projects/hall-a.json')).json()) as Bundle
  // Red by design until the golden capture (Task 14) lands: then this runs as a normal test with no edit needed.
  test.fail(!bundle.events?.length, 'Hall A has no recorded events until the golden capture (Task 14)')
  expect(bundle.events?.length ?? 0, 'golden capture (Task 14) adds the recorded events').toBeGreaterThan(0)
  expect(bundle.what_ifs?.length ?? 0, 'precomputed chip what-ifs (spec §6.4)').toBe(5)
})
