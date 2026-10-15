import { expect, startTour, test, tourCardPositions } from './fixtures'

// Exploratory QA at phone width (Pixel 7, 412 px): every main screen must fit the width and keep its banner and nav.
const PAGES = ['/app', '/app/inbox', '/app/inbox/em-hall-b', '/app/p/hall-a', '/app/integrations']

for (const path of PAGES) {
  test(`phone: ${path} fits the screen without sideways scrolling`, async ({ page }) => {
    await page.goto(path)
    await expect(page.getByRole('note').filter({ hasText: 'all companies, people and data are fictional' })).toBeVisible()
    await expect(page.getByRole('navigation', { name: 'Main' })).toBeVisible()
    await page.waitForLoadState('networkidle')
    const { scrollWidth, innerWidth } = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      innerWidth: window.innerWidth,
    }))
    expect(scrollWidth, `page is ${scrollWidth}px wide in a ${innerWidth}px viewport`).toBeLessThanOrEqual(innerWidth)
  })
}

test('phone: the main nav links stay on one line', async ({ page }) => {
  await page.goto('/app')
  const nav = page.getByRole('navigation', { name: 'Main' })
  const heights = await nav.getByRole('link').evaluateAll((els) => els.map((e) => Math.round(e.getBoundingClientRect().height)))
  expect(Math.max(...heights), `link heights ${heights.join(', ')}`).toBeLessThanOrEqual(30)
})
// Issue #38: the floating "Getting started" chip sat over the first card's title on Integrations (and over rows on
// the email and review pages). On a phone it must never cover page content, at any scroll position.
for (const path of ['/app/integrations', '/app/inbox/em-hall-b', '/app/p/hall-a/review/r2']) {
  test(`phone: the Getting started chip covers no content on ${path}`, async ({ page }) => {
    await page.goto(path)
    const chip = page.getByRole('complementary', { name: 'Getting started' })
    await expect(chip).toBeVisible()
    await expect(chip.getByRole('button', { name: /Getting started/ })).toBeEnabled() // still reachable
    const c = (await chip.boundingBox())!
    const m = (await page.locator('main').boundingBox())!
    const overlap = c.x < m.x + m.width && c.x + c.width > m.x && c.y < m.y + m.height && c.y + c.height > m.y
    expect(overlap, `chip ${JSON.stringify(c)} over the scroll area ${JSON.stringify(m)}`).toBe(false)
  })
}

test.describe('first visit on a phone', () => {
  test.use({ welcomed: false })

  test('phone: every tour card stays inside the viewport', async ({ page }) => {
    // Issue #20 (follow-up to #10): on a 412 px phone the cards of steps 3 and 4 used to be partly off-screen. The UX-2
    // round fixes it, so this is a real assertion: it fails on a build without UX-2, by design.
    await startTour(page)
    const cards = await tourCardPositions(page)
    expect(cards.filter((c) => !c.inView), 'cards outside the viewport').toEqual([])
  })
})