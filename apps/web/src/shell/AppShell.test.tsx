import { screen, within } from '@testing-library/react'
import { Route, Routes } from 'react-router'
import { useWorldStore } from '@/data/useWorld'
import { renderWithProviders } from '@/test/render'
import { AppShell } from './AppShell'

beforeEach(() => {
  localStorage.setItem('kirchhoff.welcomed', 'true')
  useWorldStore.setState({ world: null, error: null, loading: false })
})

function shell() {
  return renderWithProviders(
    <Routes>
      <Route path="/app" element={<AppShell />}>
        <Route index element={<p>projects</p>} />
      </Route>
    </Routes>,
    { route: '/app' },
  )
}

test('the main navigation lists Projects, Bids inbox and Integrations', () => {
  shell()
  const nav = screen.getByRole('navigation', { name: 'Main' })
  // Accessible names, not textContent: the inbox link renders a short "Inbox" label below sm (D14)
  // beside "Bids inbox", and its aria-label keeps the name "Bids inbox" at every width.
  expect(within(nav).getAllByRole('link').map((a) => a.getAttribute('aria-label') ?? a.textContent)).toEqual(['Projects', 'Bids inbox', 'Integrations'])
})

// Inside the app the Kirchhoff logo is the way back to the landing page; the Projects link is the way to the dashboard.
test('the Kirchhoff logo links to the landing page, Projects to the dashboard', () => {
  shell()
  expect(screen.getByRole('link', { name: 'Kirchhoff' })).toHaveAttribute('href', '/')
  expect(screen.getByRole('link', { name: 'Projects' })).toHaveAttribute('href', '/app')
})

// jsdom has no layout, so this guards the classes that keep every link on one line at phone width. Measured in a
// real browser at 390 px: without them "Bids inbox" wrapped to two lines (42 px nav in a 38 px header).
test('nav links never wrap and the header tightens its gap on phones', () => {
  shell()
  const nav = screen.getByRole('navigation', { name: 'Main' })
  for (const link of within(nav).getAllByRole('link')) expect(link).toHaveClass('whitespace-nowrap')
  expect(nav.closest('header')).toHaveClass('gap-3', 'sm:gap-6')
})
