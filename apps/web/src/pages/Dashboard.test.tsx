import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { useWorldStore } from '@/data/useWorld'
import { resetInboxStore } from '@/inbox/useInbox'
import { INBOX_TOUR_STEP } from '@/inbox/inboxTour'
import { renderWithProviders } from '@/test/render'
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
