import { expect, test } from './fixtures'

type Snapshot = {
  emails: { id: string; subject: string; attachments: { name: string }[]; triage: { fit: { verdict: string | null } } | null }[]
}

const OFFLINE = [/\/api\//, /firestore\.googleapis\.com/, /firebaseappcheck\.googleapis\.com/]
const load = async (request: import('@playwright/test').APIRequestContext) =>
  (await (await request.get('/demo/inbox.json')).json()) as Snapshot

test('the dashboard links to the bids inbox with the unread count', async ({ page }) => {
  await page.goto('/app')
  await page.getByRole('link', { name: /^Bids inbox · \d+ new$/ }).click()
  await expect(page).toHaveURL(/\/app\/inbox$/)
  await expect(page.getByRole('heading', { name: 'Bids inbox', level: 1 })).toBeVisible()
  await expect(page.getByText('sandbox (simulated)').first()).toBeVisible()
})

test('every seeded email is listed, newest first, from the static bundle', async ({ page, request }) => {
  const snap = await load(request)
  expect(snap.emails).toHaveLength(6)
  await page.goto('/app/inbox')
  const rows = page.locator('a[href^="/app/inbox/em-"]')
  await expect(rows).toHaveCount(6)
  await expect(rows.first()).toHaveAttribute('href', '/app/inbox/em-hall-b')
  for (const e of snap.emails) await expect(page.getByText(e.subject, { exact: true }).first()).toBeVisible()
})

test('Hall B: its three attachments are listed and Pursue opens Hall B with the API down', async ({ page, request }) => {
  for (const pattern of OFFLINE) await page.route(pattern, (route) => route.abort('connectionrefused'))
  const hallB = (await load(request)).emails.find((e) => e.id === 'em-hall-b')!
  await page.goto('/app/inbox/em-hall-b')
  const detail = page.getByRole('region', { name: 'Email' })
  await expect(detail.getByRole('heading', { name: hallB.subject })).toBeVisible()
  for (const a of hallB.attachments) await expect(detail.getByRole('link', { name: new RegExp(a.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) })).toBeVisible()
  if (hallB.triage === null) {
    // Before the golden capture is folded in (plan step 15) there is no recorded triage to show.
    await expect(detail.getByText(/Not triaged yet/)).toBeVisible()
    return
  }
  const fit = detail.getByRole('region', { name: 'Fit verdict' })
  await expect(fit).toContainText('Pursue')
  await expect(fit).toContainText('Day-zero supply')
  await detail.getByRole('button', { name: 'Pursue' }).click()
  await expect(detail.getByRole('status')).toContainText('You can still open the project; the CRM was not updated.')
  await detail.getByRole('link', { name: /^Open .*Hall B/ }).click()
  await expect(page).toHaveURL(/\/app\/p\/hall-b/)
})

test('the scanned BOQ is marked as a scan, never verified', async ({ page, request }) => {
  const vindhya = (await load(request)).emails.find((e) => e.id === 'em-vindhya-boq')!
  await page.goto('/app/inbox/em-vindhya-boq')
  const detail = page.getByRole('region', { name: 'Email' })
  await expect(detail.getByRole('link', { name: /Switchyard BOQ \(scan\)\.pdf/ })).toBeVisible()
  if (vindhya.triage === null) {
    await expect(detail.getByText(/Not triaged yet/)).toBeVisible()
    return
  }
  await expect(detail.getByText('Not verified (scan)').first()).toBeVisible()
  await expect(detail.getByRole('region', { name: 'Fit verdict' })).toContainText('Clarify')
})

test('the inbox works with /api, Firestore and App Check unreachable', async ({ page }) => {
  for (const pattern of OFFLINE) await page.route(pattern, (route) => route.abort('connectionrefused'))
  await page.goto('/app/inbox')
  await expect(page.locator('a[href^="/app/inbox/em-"]')).toHaveCount(6)
  await page.goto('/app/inbox/em-narmada-400kv')
  await expect(page.getByRole('region', { name: 'Email' })).toContainText('RFQ: 400 kV GIS substation at Bharuch, EPC')
})
