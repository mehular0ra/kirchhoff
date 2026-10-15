import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { useWorldStore } from '@/data/useWorld'
import { resetInboxStore } from '@/inbox/useInbox'
import { INBOX_TOUR_STEP } from '@/inbox/inboxTour'
import { vi } from 'vitest'
import { fakeServices, renderWithProviders } from '@/test/render'
import { AppShell } from '@/shell/AppShell'
import { Dashboard } from './Dashboard'
import { Landing } from './Landing'

beforeEach(() => {
  useWorldStore.setState({ world: null, error: null, loading: false })
  resetInboxStore()
})

function shellAt(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/app" element={<AppShell />}>
        <Route index element={<Dashboard />} />
        <Route path="p/:pid" element={<p>workspace</p>} />
      </Route>
    </Routes>,
    { route },
  )
}

test('dashboard groups world projects by asset pack with text state badges and the fictional banner', async () => {
  localStorage.setItem('kirchhoff.welcomed', 'true')
  shellAt('/app')
  expect(screen.getByRole('note')).toHaveTextContent('Demo workspace — all companies, people and data are fictional')
  expect(await screen.findByText('Deccan AI Campus · Hall A')).toBeInTheDocument()
  const halls = screen.getByRole('group', { name: 'AI data halls' })
  expect(within(halls).getAllByRole('article')).toHaveLength(3)
  expect(within(halls).getByText('Signed')).toBeInTheDocument()
  expect(within(halls).getByText('Not started')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /run it live/i })).toHaveAttribute('href', '/app/p/hall-b')
  expect(screen.getByText('You (Demo Reviewer)')).toBeInTheDocument()
})

test('welcome shows on first visit only and the choice persists', async () => {
  const user = userEvent.setup()
  const { unmount } = shellAt('/app')
  expect(await screen.findByRole('dialog', { name: /welcome/i })).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /explore on my own/i }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(localStorage.getItem('kirchhoff.welcomed')).toBe('true')
  unmount()
  shellAt('/app')
  await screen.findByText('Deccan AI Campus · Hall A')
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

test('landing has one primary CTA into the demo workspace', () => {
  renderWithProviders(<Landing />)
  expect(screen.getByRole('link', { name: /enter the demo workspace \(no login\)/i })).toHaveAttribute('href', '/app')
  expect(screen.getByRole('link', { name: /replay a recorded run/i })).toHaveAttribute('href', '/app/p/hall-a?replay=1')
})

test('the dashboard links the bids inbox with its count of new emails (tour hook, not a tour step)', async () => {
  localStorage.setItem('kirchhoff.welcomed', 'true')
  localStorage.setItem('kirchhoff.inbox.read', JSON.stringify(['em-hall-b']))
  shellAt('/app')
  const entry = await screen.findByRole('link', { name: 'Bids inbox · 3 new' })
  expect(entry).toHaveAttribute('href', '/app/inbox')
  expect(entry).toHaveAttribute('data-tour', 'inbox')
  expect(document.querySelector(INBOX_TOUR_STEP.target)).toBe(entry)
  expect(screen.getByRole('navigation', { name: 'Main' })).toHaveTextContent('Bids inbox')
})

test('PR #5 follow-up / M4: on the dashboard the Getting-started checklist sits in the side column, never floating over the inbox entry or cards', async () => {
  localStorage.setItem('kirchhoff.welcomed', 'true')
  shellAt('/app')
  await screen.findByText('Deccan AI Campus · Hall A')
  const lists = screen.getAllByRole('complementary', { name: 'Getting started' })
  expect(lists).toHaveLength(1)
  expect(lists[0].className).not.toMatch(/\bfixed\b/)
  expect(lists[0].closest('[data-dashboard-side]')).not.toBeNull()
})

test('M4: on a page without a dock the checklist still floats', async () => {
  localStorage.setItem('kirchhoff.welcomed', 'true')
  shellAt('/app/p/x')
  const list = await screen.findByRole('complementary', { name: 'Getting started' })
  expect(list.className).toMatch(/\bfixed\b/)
})

test('M12: a stored live run does not claim the run is still "Running" (it may be done or expired)', async () => {
  localStorage.setItem('kirchhoff.welcomed', 'true')
  localStorage.setItem('kirchhoff.lastRun.hall-b', JSON.stringify('run-1'))
  shellAt('/app')
  const card = (await screen.findByText('Deccan AI Campus · Hall B')).closest('article')!
  expect(within(card).queryByText('Running')).not.toBeInTheDocument()
  expect(within(card).getByText('Your live run')).toBeInTheDocument()
})

test('D2: dashboard times read against the labelled demo clock, not the browser clock', async () => {
  localStorage.setItem('kirchhoff.welcomed', 'true')
  const world = {
    org: { name: 'Meridian Power Engineering' },
    people: [],
    projects: [
      { id: 'hall-b', name: 'Deccan AI Campus · Hall B', client: 'Deccan Compute', asset_pack: 'datahall', state: 'not_started', sample: true, updated_at: 1792132200 + 3600 },
    ],
    activity: [{ id: 'a1', ts: 1792132200 - 2 * 3600, actor: 'Procurement agent', text: 'submitted PR-2026-0148 to the ERP sandbox (1 lines)' }],
  }
  renderWithProviders(<Dashboard />, {
    services: fakeServices({ getJson: vi.fn(async (url: string) => (url === '/demo/world.json' ? world : Promise.reject(new Error('404')))) }),
  })
  expect(await screen.findByText('Demo world as of 16 Oct 2026, 12:00 IST')).toBeInTheDocument()
  expect(screen.getByText('2 hours ago')).toBeInTheDocument()
  expect(screen.getByText('submitted PR-2026-0148 to the ERP sandbox (1 line)')).toBeInTheDocument()
  // later than the demo clock: a date, never "in 1 hour"
  expect(screen.getByText('16 Oct 2026, 13:00')).toBeInTheDocument()
  expect(screen.queryByText(/^in \d/)).not.toBeInTheDocument()
})

test('D10: the Hall B card offers Replay only when Hall A carries a recorded run', async () => {
  localStorage.setItem('kirchhoff.welcomed', 'true')
  const { STATIC_FILES } = await import('@/test/render')
  const noEvents = { ...(STATIC_FILES['/demo/projects/hall-a.json'] as object), events: [] }
  renderWithProviders(<Dashboard />, {
    services: fakeServices({
      getJson: vi.fn(async (url: string) => (url === '/demo/projects/hall-a.json' ? structuredClone(noEvents) : structuredClone(STATIC_FILES[url]))),
    }),
  })
  expect(await screen.findByRole('link', { name: /run it live/i })).toBeInTheDocument()
  await vi.waitFor(() => expect(screen.queryByRole('link', { name: /^Replay$/ })).not.toBeInTheDocument())
})

test('D10: with a recorded run in Hall A, the Hall B card keeps Replay', async () => {
  localStorage.setItem('kirchhoff.welcomed', 'true')
  renderWithProviders(<Dashboard />)
  expect(await screen.findByRole('link', { name: /^Replay$/ })).toHaveAttribute('href', '/app/p/hall-a?replay=1')
})

test('D11: when the demo world cannot load, the dashboard offers Try again instead of a raw error', async () => {
  renderWithProviders(<Dashboard />, { services: fakeServices({ getJson: vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))) }) })
  expect(await screen.findByText("Couldn't load the projects")).toBeInTheDocument()
  expect(screen.queryByText(/Failed to fetch/)).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
})
