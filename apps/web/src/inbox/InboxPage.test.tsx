import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { vi } from 'vitest'
import { useWorldStore } from '@/data/useWorld'
import type { PursueResult } from '@/lib/types'
import { fixtureInbox } from '@/test/fixtures'
import { fakeApi, fakeServices, renderWithProviders } from '@/test/render'
import { InboxPage } from './InboxPage'
import { resetInboxStore } from './useInbox'

beforeEach(() => {
  useWorldStore.setState({ world: null, error: null, loading: false })
  resetInboxStore()
})

function inboxAt(route: string, services = fakeServices()) {
  return renderWithProviders(
    <Routes>
      <Route path="/app/inbox" element={<InboxPage />} />
      <Route path="/app/inbox/:emailId" element={<InboxPage />} />
    </Routes>,
    { route, services },
  )
}

const PURSUED: PursueResult = {
  email_id: 'em-hall-b',
  project_id: 'hall-b',
  project_name: null,
  project_created: false,
  opportunity_id: 'opp-hall-b',
  opportunity_name: 'Hall B design-build',
  stage: 'Qualification',
  previous_stage: 'Design in progress',
  opportunity_created: false,
  open: '/app/p/hall-b',
}

test('static first: the list renders from /demo/inbox.json, newest first, verdicts as icon + text', async () => {
  inboxAt('/app/inbox')
  const list = await screen.findByRole('list', { name: 'Emails' })
  const rows = within(list).getAllByRole('link')
  expect(rows.map((r) => r.getAttribute('href'))).toEqual([
    '/app/inbox/em-hall-b',
    '/app/inbox/em-tapti-brochure',
    '/app/inbox/em-vindhya-boq',
    '/app/inbox/em-narmada-400kv',
  ])
  expect(['Pursue', 'Not a bid', 'Clarify', 'Decline'].map((v, i) => within(rows[i]).getByText(v))).toHaveLength(4)
  expect(within(rows[0]).getByText('New')).toBeInTheDocument()
  expect(screen.getByText('Recorded triage (static)')).toBeInTheDocument()
  expect(screen.getByText('bids@meridian-power.example')).toBeInTheDocument()
  expect(screen.getByText(/Appetite: AI data halls, grid, solar · 2–120 MW/)).toBeInTheDocument()
  expect(screen.getByText('Select an email')).toBeInTheDocument()
})

test('with the API up, the live inbox (visitor overlay) replaces the static one', async () => {
  const live = fixtureInbox()
  live.emails[0] = { ...live.emails[0], status: 'pursued', pursue: PURSUED }
  inboxAt('/app/inbox', fakeServices({ api: fakeApi({ inbox: vi.fn(async () => live) }) }))
  expect(await screen.findByText('Live · your workspace')).toBeInTheDocument()
  expect(within(screen.getByRole('list', { name: 'Emails' })).getByText('Pursued')).toBeInTheDocument()
})

test('Hall B detail: attachment chips by class, CRM link, verified fields, fit card with the supply line', async () => {
  inboxAt('/app/inbox/em-hall-b')
  const chips = await screen.findByRole('list', { name: 'Attachments' })
  const links = within(chips).getAllByRole('link')
  expect(links.map((a) => a.textContent)).toEqual([
    'TenderDC-HA-TS-001 Rev 0 technical requirements.pdf',
    'DrawingData hall general arrangement.pdf',
    'AddendumAddendum 1, Hall B.pdf',
  ])
  expect(links[0]).toHaveAttribute('href', '/demo/docs/tender-hall-a.pdf')
  expect(screen.getByRole('link', { name: 'Deccan Compute · Hall B design-build (Design in progress)' })).toHaveAttribute(
    'href',
    '/app/integrations',
  )
  expect(screen.getByText(/recorded triage · 7\/7 quotes verified/)).toBeInTheDocument()
  const fields = screen.getByRole('table', { name: 'Extracted fields' })
  expect(within(fields).getAllByText('quote verified')).toHaveLength(7)
  expect(within(within(fields).getByRole('row', { name: /Load/ })).getByText('6.34 MW')).toBeInTheDocument()
  const fit = screen.getByRole('region', { name: 'Fit verdict' })
  expect(within(fit).getByText('Pursue')).toBeInTheDocument()
  expect(within(fit).getAllByText('Pass')).toHaveLength(5)
  expect(within(fit).getByText(/expect an in-stock swap to TX-3150 \(3\.15 MVA, 6 in stock\)/)).toBeInTheDocument()
})

test('a scanned BOQ is marked unverified (scan); only the Hall B email offers live triage', async () => {
  inboxAt('/app/inbox/em-vindhya-boq')
  const fields = await screen.findByRole('table', { name: 'Extracted fields' })
  const load = within(fields).getByRole('row', { name: /Load/ })
  expect(within(load).getByText('unverified (scan)')).toBeInTheDocument()
  expect(within(load).getByText('Not verified (scan)')).toBeInTheDocument()
  expect(within(screen.getByRole('list', { name: 'Attachments' })).getByText('scan')).toBeInTheDocument()
  expect(within(screen.getByRole('region', { name: 'Fit verdict' })).getByText('Clarify')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /triage live/i })).not.toBeInTheDocument()
})

test('declined and not-a-bid emails offer no Pursue', async () => {
  inboxAt('/app/inbox/em-narmada-400kv')
  expect(await screen.findByText('Declined by the fit rules.')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Pursue' })).not.toBeInTheDocument()
})

test('Pursue with the API up shows the CRM move and opens Hall B intake', async () => {
  const user = userEvent.setup()
  const api = fakeApi({ pursue: vi.fn(async () => PURSUED) })
  inboxAt('/app/inbox/em-hall-b', fakeServices({ api }))
  await user.click(await screen.findByRole('button', { name: 'Pursue' }))
  const card = await screen.findByRole('region', { name: 'Pursued' })
  expect(within(card).getByText(/Hall B design-build → Qualification \(was Design in progress\)/)).toBeInTheDocument()
  expect(within(card).getByRole('link', { name: /and run intake/ })).toHaveAttribute('href', '/app/p/hall-b')
  expect(api.pursue).toHaveBeenCalledWith('em-hall-b')
})

test('Pursue with the backend down still opens Hall B (static fallback)', async () => {
  const user = userEvent.setup()
  inboxAt('/app/inbox/em-hall-b')
  await user.click(await screen.findByRole('button', { name: 'Pursue' }))
  expect(await screen.findByRole('status')).toHaveTextContent('the CRM was not updated')
  expect(screen.getByRole('link', { name: /^Open .*hall.b/i })).toHaveAttribute('href', '/app/p/hall-b')
})

test('keyboard: the email rows are reachable with Tab and open with Enter; opening marks the email read', async () => {
  const user = userEvent.setup()
  inboxAt('/app/inbox')
  const first = within(await screen.findByRole('list', { name: 'Emails' })).getAllByRole('link')[0]
  first.focus()
  expect(first).toHaveFocus()
  await user.keyboard('{Enter}')
  expect(await screen.findByRole('heading', { level: 2 })).toHaveTextContent('Tender: Deccan AI Campus Hall B')
  expect(within(screen.getAllByRole('link', { name: /Deccan Compute/ })[0]).queryByText('New')).not.toBeInTheDocument()
  expect(JSON.parse(localStorage.getItem('kirchhoff.inbox.read') ?? '[]')).toEqual(['em-hall-b'])
})
