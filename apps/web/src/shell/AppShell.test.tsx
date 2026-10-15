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
  expect(within(nav).getAllByRole('link').map((a) => a.textContent)).toEqual(['Projects', 'Bids inbox', 'Integrations'])
})

// jsdom has no layout, so this guards the classes that keep every link on one line at phone width. Measured in a
// real browser at 390 px: without them "Bids inbox" wrapped to two lines (42 px nav in a 38 px header).
test('nav links never wrap and the header tightens its gap on phones', () => {
  shell()
  const nav = screen.getByRole('navigation', { name: 'Main' })
  for (const link of within(nav).getAllByRole('link')) expect(link).toHaveClass('whitespace-nowrap')
  expect(nav.closest('header')).toHaveClass('gap-3', 'sm:gap-6')
})
