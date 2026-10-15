import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes, useLocation } from 'react-router'
import { vi } from 'vitest'
import { useWorldStore } from '@/data/useWorld'
import { useBundleStore } from '@/store/bundles'
import { AppShell } from '@/shell/AppShell'
import { ApiError } from '@/services/apiClient'
import { fakeApi, fakeServices, renderWithProviders } from '@/test/render'
import { fixtureBundle } from '@/test/fixtures'
import { completeItem, useChecklist } from './checklist/checklistStore'
import { useTour } from './tour/tour'
import { firstFailure, stepBody, TOUR_STEPS } from './tour/tourSteps'

/** window.location.assign cannot be spied directly in jsdom (its descriptor forbids redefining
 * the method in place), so swap the whole `location` object for the duration of one test. */
function stubLocationAssign() {
  const assign = vi.fn()
  const original = window.location
  Object.defineProperty(window, 'location', { value: { ...original, assign }, writable: true, configurable: true })
  return {
    assign,
    restore: () => Object.defineProperty(window, 'location', { value: original, writable: true, configurable: true }),
  }
}

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
  expect(TOUR_STEPS[4].target).toBe('[data-tour="whatif-chip"]')
  expect(TOUR_STEPS).toHaveLength(7)
})

test('D7: step 3 promises a highlight only when the cited quote carries a pdfplumber box', () => {
  const b = fixtureBundle()
  const withBox = b.findings.r1.find((f) => f.id === 'R05:FA-01')!
  withBox.tender_refs = (withBox.tender_refs ?? []).map((c) => ({ ...c, bbox: [10, 20, 200, 40] }))
  expect(stepBody(TOUR_STEPS[2], { hallA: b })).toMatch(/opens at the clause, highlighted/)
  withBox.tender_refs = (withBox.tender_refs ?? []).map((c) => ({ ...c, bbox: null }))
  expect(stepBody(TOUR_STEPS[2], { hallA: b })).toMatch(/opens at the clause\.$/)
  expect(stepBody(TOUR_STEPS[2], { hallA: b })).not.toMatch(/highlighted/)
  expect(stepBody(TOUR_STEPS[2], { hallA: null })).not.toMatch(/highlighted/)
})

const rectAt = (x: number, y: number, width: number, height: number) =>
  ({ x, y, left: x, top: y, width, height, right: x + width, bottom: y + height, toJSON: () => ({}) }) as DOMRect

test('C1: the spotlight keeps re-measuring a target that is still sliding in (drawer) until its rect is stable', async () => {
  app()
  const target = screen.getByText('projects')
  let calls = 0
  // First frames: mid-slide (off to the right). Then the drawer settles.
  vi.spyOn(target, 'getBoundingClientRect').mockImplementation(() => (++calls < 4 ? rectAt(900, 148, 105, 33) : rectAt(500, 148, 105, 33)))
  act(() => useTour.getState().start())
  await screen.findByRole('dialog', { name: 'Guided tour' })
  await waitFor(() => expect(screen.getByTestId('tour-anchor').style.left).toBe('494px'))
  expect(calls).toBeGreaterThanOrEqual(4)
})

test('C1: the spotlight is clamped to the viewport for a target taller than the screen', async () => {
  app()
  const target = screen.getByText('projects')
  vi.spyOn(target, 'getBoundingClientRect').mockImplementation(() => rectAt(175, -518, 817, 1997))
  act(() => useTour.getState().start())
  await screen.findByRole('dialog', { name: 'Guided tour' })
  const anchor = screen.getByTestId('tour-anchor')
  await waitFor(() => expect(parseFloat(anchor.style.top)).toBeGreaterThanOrEqual(0))
  expect(parseFloat(anchor.style.top) + parseFloat(anchor.style.height)).toBeLessThanOrEqual(window.innerHeight)
})

test('C1: a viewport resize re-measures the spotlight', async () => {
  app()
  const target = screen.getByText('projects')
  let x = 300
  vi.spyOn(target, 'getBoundingClientRect').mockImplementation(() => rectAt(x, 100, 80, 30))
  act(() => useTour.getState().start())
  await screen.findByRole('dialog', { name: 'Guided tour' })
  await waitFor(() => expect(screen.getByTestId('tour-anchor').style.left).toBe('294px'))
  await new Promise((r) => setTimeout(r, 800)) // let the post-find tracking settle and stop
  x = 200
  act(() => {
    window.dispatchEvent(new Event('resize'))
  })
  await waitFor(() => expect(screen.getByTestId('tour-anchor').style.left).toBe('194px'))
})

test('M6: step 3 re-navigates to the failing finding once Hall A loads after the step started', async () => {
  renderWithProviders(
    <Routes>
      <Route path="/app" element={<AppShell />}>
        <Route index element={<Where />} />
        <Route path="p/:pid" element={<Where />} />
      </Route>
    </Routes>,
    { route: '/app' },
  )
  act(() => {
    useTour.getState().start()
    useTour.getState().next()
    useTour.getState().next()
  })
  await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('/app/p/hall-a?tab=matrix'))
  expect(screen.getByTestId('where')).not.toHaveTextContent('finding=')
  act(() => useBundleStore.getState().setBundle('hall-a:static', fixtureBundle(), 'static'))
  await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('finding=R05%3AFA-01'))
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

test('the tour moves focus into the popover and returns it to the opener on Escape', async () => {
  const user = userEvent.setup()
  app()
  const opener = document.createElement('button')
  opener.textContent = 'Opener'
  document.body.appendChild(opener)
  opener.focus()
  expect(document.activeElement).toBe(opener)

  act(() => useTour.getState().start())
  const tour = await screen.findByRole('dialog', { name: 'Guided tour' })
  const next = within(tour).getByRole('button', { name: 'Next' })
  await waitFor(() => expect(document.activeElement).toBe(next))

  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Guided tour' })).not.toBeInTheDocument())
  expect(document.activeElement).toBe(opener)

  opener.remove()
})

test('a tour step whose target never appears falls back to the centred popover; Next and Skip still work', async () => {
  const user = userEvent.setup()
  app()
  act(() => {
    useTour.getState().start()
    // Step 4 ("whatif") targets [data-tour="whatif-chip"], which does not exist until Task 16
    // and is not rendered by any route fixture here either — a permanently missing anchor.
    useTour.getState().next()
    useTour.getState().next()
    useTour.getState().next()
    useTour.getState().next()
  })
  const tour = await screen.findByRole('dialog', { name: 'Guided tour' })
  expect(within(tour).getByText('Step 5 of 7')).toBeInTheDocument()
  expect(within(tour).getByText('Loading this part of the workspace…')).toBeInTheDocument()
  await user.click(within(tour).getByRole('button', { name: 'Next' }))
  expect(await screen.findByText('Step 6 of 7')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Skip tour' }))
  expect(useTour.getState().active).toBe(false)
})

test('the tour completes every step with every api.* call rejecting (backend down)', async () => {
  const user = userEvent.setup()
  // fakeServices()'s default ApiClient rejects every call with ApiError(503, 'offline').
  app()
  act(() => useTour.getState().start())
  for (let i = 0; i < TOUR_STEPS.length - 1; i++) {
    const tour = await screen.findByRole('dialog', { name: 'Guided tour' })
    await user.click(within(tour).getByRole('button', { name: 'Next' }))
  }
  const last = await screen.findByRole('dialog', { name: 'Guided tour' })
  await user.click(within(last).getByRole('button', { name: 'Finish' }))
  expect(useTour.getState()).toMatchObject({ active: false, step: 0, done: true })
})

test('? -> "Restart the tour" works after the tour has finished', async () => {
  const user = userEvent.setup()
  useTour.getState().stop(true) // simulate a previously finished tour
  app()
  await user.keyboard('?')
  const help = await screen.findByRole('dialog', { name: 'Help and shortcuts' })
  await user.click(within(help).getByRole('button', { name: 'Restart the tour' }))
  expect(useTour.getState().active).toBe(true)
  expect(await screen.findByText('Step 1 of 7')).toBeInTheDocument()
})

test('a throwing localStorage does not crash render or the tour', async () => {
  const user = userEvent.setup()
  app()
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new DOMException('blocked', 'SecurityError')
  })
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new DOMException('blocked', 'SecurityError')
  })
  expect(() => act(() => useTour.getState().start())).not.toThrow()
  const tour = await screen.findByRole('dialog', { name: 'Guided tour' })
  expect(within(tour).getByText('Step 1 of 7')).toBeInTheDocument()
  await user.click(within(tour).getByRole('button', { name: 'Next' }))
  expect(await screen.findByText('Step 2 of 7')).toBeInTheDocument()
  expect(() => act(() => completeItem('open_signed'))).not.toThrow() // store update re-renders the checklist: inside act (backlog [5])
  await user.click(screen.getByRole('button', { name: 'Skip tour' }))
})

test('reset on a 409 (run_in_progress) keeps local storage and shows an icon with the message', async () => {
  const user = userEvent.setup()
  localStorage.setItem('kirchhoff.checklist', JSON.stringify({ open_signed: true }))
  const api = fakeApi({ resetWorkspace: vi.fn(() => Promise.reject(new ApiError(409, 'run_in_progress'))) })
  renderWithProviders(
    <Routes>
      <Route path="/app" element={<AppShell />}>
        <Route index element={<div />} />
      </Route>
    </Routes>,
    { route: '/app', services: fakeServices({ api }) },
  )
  await user.keyboard('?')
  const help = await screen.findByRole('dialog', { name: 'Help and shortcuts' })
  await user.click(within(help).getByRole('button', { name: 'Reset demo workspace' }))
  await user.click(within(help).getByRole('button', { name: 'Confirm: reset my demo workspace' }))
  const alert = await within(help).findByRole('alert')
  expect(alert.querySelector('svg')).toBeTruthy()
  expect(localStorage.getItem('kirchhoff.checklist')).not.toBeNull()
})

test('reset on a non-409 failure clears local storage, shows an icon, and waits for dismiss before navigating', async () => {
  const user = userEvent.setup()
  const loc = stubLocationAssign()
  localStorage.setItem('kirchhoff.checklist', JSON.stringify({ open_signed: true }))
  const api = fakeApi({ resetWorkspace: vi.fn(() => Promise.reject(new ApiError(503, 'offline'))) })
  renderWithProviders(
    <Routes>
      <Route path="/app" element={<AppShell />}>
        <Route index element={<div />} />
      </Route>
    </Routes>,
    { route: '/app', services: fakeServices({ api }) },
  )
  await user.keyboard('?')
  const help = await screen.findByRole('dialog', { name: 'Help and shortcuts' })
  await user.click(within(help).getByRole('button', { name: 'Reset demo workspace' }))
  await user.click(within(help).getByRole('button', { name: 'Confirm: reset my demo workspace' }))
  const alert = await within(help).findByRole('alert')
  expect(alert.querySelector('svg')).toBeTruthy()
  expect(localStorage.getItem('kirchhoff.checklist')).toBeNull()
  expect(loc.assign).not.toHaveBeenCalled()
  await user.click(within(alert).getByRole('button', { name: 'Dismiss' }))
  expect(loc.assign).toHaveBeenCalledWith('/app')
  loc.restore()
})

test('presentation mode disables ?, g p and g i so a recording never pops the dialog', async () => {
  const user = userEvent.setup()
  document.documentElement.dataset.present = '1'
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
  expect(screen.getByTestId('where')).toHaveTextContent('/app')
  await user.keyboard('?')
  expect(screen.queryByRole('dialog', { name: 'Help and shortcuts' })).not.toBeInTheDocument()
  document.documentElement.dataset.present = '0'
})
