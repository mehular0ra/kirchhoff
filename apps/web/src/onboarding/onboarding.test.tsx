import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes, useLocation } from 'react-router'
import { useWorldStore } from '@/data/useWorld'
import { AppShell } from '@/shell/AppShell'
import { renderWithProviders } from '@/test/render'
import { fixtureBundle } from '@/test/fixtures'
import { completeItem, useChecklist } from './checklist/checklistStore'
import { useTour } from './tour/tour'
import { firstFailure, TOUR_STEPS } from './tour/tourSteps'

function Where() {
  const l = useLocation()
  return <p data-testid="where">{l.pathname + l.search}</p>
}

function app(route = '/app') {
  return renderWithProviders(
    <Routes>
      <Route path="/app" element={<AppShell />}>
        <Route index element={<div data-tour="projects">projects</div>} />
        <Route path="p/:pid" element={<div data-tour="matrix-row">matrix</div>} />
        <Route path="integrations" element={<p>integrations page</p>} />
      </Route>
    </Routes>,
    { route },
  )
}

beforeEach(() => {
  localStorage.setItem('kirchhoff.welcomed', 'true')
  useWorldStore.setState({ world: null, error: null, loading: false })
  useTour.getState().reload()
  useChecklist.getState().reload()
})

test('checklist progress persists in localStorage and renders as "n of 6"', () => {
  completeItem('open_signed')
  completeItem('run_whatif')
  completeItem('run_whatif')
  expect(JSON.parse(localStorage.getItem('kirchhoff.checklist')!)).toEqual({ open_signed: true, run_whatif: true })
  app()
  const card = screen.getByRole('complementary', { name: 'Getting started' })
  expect(within(card).getByText('2 of 6')).toBeInTheDocument()
  expect(within(card).getAllByLabelText('done')).toHaveLength(2)
})

test('tour persists its step in localStorage and resumes after a reload', async () => {
  const user = userEvent.setup()
  const { unmount } = app()
  act(() => useTour.getState().start())
  const tour = await screen.findByRole('dialog', { name: 'Guided tour' })
  expect(within(tour).getByText('Step 1 of 7')).toBeInTheDocument()
  expect(within(tour).getByText("Your firm's live projects")).toBeInTheDocument()
  await user.click(within(tour).getByRole('button', { name: 'Next' }))
  expect(JSON.parse(localStorage.getItem('kirchhoff.tour')!)).toEqual({ active: true, step: 1, done: false })
  expect(await screen.findByText('Every number is checked and cited')).toBeInTheDocument()
  unmount()
  useTour.getState().reload()
  app('/app/p/hall-a?tab=matrix')
  expect(await screen.findByText('Step 2 of 7')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Skip tour' }))
  expect(JSON.parse(localStorage.getItem('kirchhoff.tour')!).active).toBe(false)
})

test('tour step 3 opens the first failing finding; step 4 counts agents from the bundle', () => {
  const b = fixtureBundle()
  expect(firstFailure(b)).toEqual({ rev: 'r1', id: 'R05:FA-01' })
  expect(TOUR_STEPS[2].route({ hallA: b })).toBe('/app/p/hall-a?tab=matrix&rev=r1&finding=R05%3AFA-01')
  expect(TOUR_STEPS[3].title({ hallA: b })).toBe("8 agents designed this; here's what each did")
  expect(TOUR_STEPS).toHaveLength(7)
})

test('keyboard: g i goes to integrations, g p to projects, ? opens help with tour restart', async () => {
  const user = userEvent.setup()
  renderWithProviders(
    <Routes>
      <Route path="/app" element={<AppShell />}>
        <Route index element={<Where />} />
        <Route path="integrations" element={<Where />} />
      </Route>
    </Routes>,
    { route: '/app' },
  )
  await user.keyboard('gi')
  expect(screen.getByTestId('where')).toHaveTextContent('/app/integrations')
  await user.keyboard('gp')
  expect(screen.getByTestId('where')).toHaveTextContent('/app')
  await user.keyboard('?')
  const help = await screen.findByRole('dialog', { name: 'Help and shortcuts' })
  await user.click(within(help).getByRole('button', { name: 'Restart the tour' }))
  expect(useTour.getState().active).toBe(true)
})
