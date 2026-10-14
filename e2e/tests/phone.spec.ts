import { expect, test } from './fixtures'

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