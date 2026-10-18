import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes, useNavigate } from 'react-router'
import { vi } from 'vitest'
import vindhya from '@/test/fixtures/vindhya-lv.json'
import { fakeServices, renderWithProviders, STATIC_FILES } from '@/test/render'
import { useLayout } from '@/store/layout'
import { useUi } from '@/store/ui'
import { WorkspacePage } from './WorkspacePage'

const open = (route = '/app/p/hall-a') => renderWithProviders(<WorkspacePage />, { route, path: '/app/p/:pid' })

test('workspace renders lanes with status text and counters from the static bundle', async () => {
  open()
  const lanes = await screen.findByRole('navigation', { name: 'Agent lanes' })
  expect(within(lanes).getByText('Intake')).toBeInTheDocument()
  expect(within(lanes).getAllByText('Done').length).toBeGreaterThan(5)
  expect(within(lanes).getByText('2/3 quotes verified')).toBeInTheDocument()
  expect(within(lanes).getByText('Drawing read · DXF agrees')).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: /Deccan AI Campus · Hall A/ })).toBeInTheDocument()
  expect(screen.getByText('Recorded design')).toBeInTheDocument()
})

// ---- The side panels can be resized and hidden.

const gridOf = () => screen.getByRole('separator', { name: 'Resize the agents lane' }).parentElement as HTMLElement

beforeEach(() => {
  localStorage.clear()
  useLayout.getState().reset()
})

test('the agents lane and the co-pilot each have a draggable edge, with the canvas between them', async () => {
  open()
  await screen.findByRole('navigation', { name: 'Agent lanes' })
  const lanes = screen.getByRole('separator', { name: 'Resize the agents lane' })
  const copilot = screen.getByRole('separator', { name: 'Resize the co-pilot' })
  expect(lanes).toHaveAttribute('aria-valuenow', '256')
  expect(copilot).toHaveAttribute('aria-valuenow', '320')
  expect(gridOf().style.gridTemplateColumns).toBe('256px 6px minmax(22rem,1fr) 6px 320px')
})

test('the arrow keys on an edge change that panel\'s width, and the canvas takes the difference', async () => {
  const user = userEvent.setup()
  open()
  await screen.findByRole('navigation', { name: 'Agent lanes' })
  screen.getByRole('separator', { name: 'Resize the agents lane' }).focus()
  await user.keyboard('{ArrowRight}{ArrowRight}')
  expect(useLayout.getState().lanesW).toBe(288)
  screen.getByRole('separator', { name: 'Resize the co-pilot' }).focus()
  await user.keyboard('{ArrowLeft}')
  expect(useLayout.getState().copilotW).toBe(336)
  expect(gridOf().style.gridTemplateColumns).toBe('288px 6px minmax(22rem,1fr) 6px 336px')
})

test('a double click on an edge puts that panel back to its usual width', async () => {
  const user = userEvent.setup()
  open()
  await screen.findByRole('navigation', { name: 'Agent lanes' })
  act(() => useLayout.getState().setCopilotW(500))
  await user.dblClick(screen.getByRole('separator', { name: 'Resize the co-pilot' }))
  expect(useLayout.getState().copilotW).toBe(320)
})

test('the top bar hides and shows the agents lane and the co-pilot, and the canvas stays', async () => {
  const user = userEvent.setup()
  open()
  await screen.findByRole('navigation', { name: 'Agent lanes' })
  const lanes = screen.getByRole('button', { name: 'Agents lane', pressed: true })
  const copilot = screen.getByRole('button', { name: 'Co-pilot', pressed: true })
  await user.click(copilot)
  expect(screen.queryByRole('complementary', { name: 'Co-pilot' })).not.toBeInTheDocument()
  expect(screen.queryByRole('separator', { name: 'Resize the co-pilot' })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Co-pilot', pressed: false })).toBeInTheDocument()
  expect(gridOf().style.gridTemplateColumns).toBe('256px 6px minmax(22rem,1fr) 0px 0px')
  await user.click(lanes)
  expect(screen.queryByRole('navigation', { name: 'Agent lanes' })).not.toBeInTheDocument()
  expect(screen.getByRole('region', { name: 'Canvas' })).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Agents lane', pressed: false }))
  await user.click(screen.getByRole('button', { name: 'Co-pilot', pressed: false }))
  expect(await screen.findByRole('navigation', { name: 'Agent lanes' })).toBeInTheDocument()
  expect(screen.getByRole('complementary', { name: 'Co-pilot' })).toBeInTheDocument()
})

test('a hidden co-pilot stays mounted: what was half typed in it is still there when it comes back', async () => {
  const user = userEvent.setup()
  open()
  await screen.findByRole('navigation', { name: 'Agent lanes' })
  await user.type(screen.getByRole('textbox', { name: 'Ask the co-pilot' }), 'half a quest')
  await user.click(screen.getByRole('button', { name: 'Co-pilot', pressed: true }))
  await user.click(screen.getByRole('button', { name: 'Co-pilot', pressed: false }))
  // component state (not the global store) survives only if hiding did not unmount the panel
  expect(screen.getByRole('textbox', { name: 'Ask the co-pilot' })).toHaveValue('half a quest')
})

describe('on a window too small for the saved widths', () => {
  const clientWidth = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'clientWidth')
  afterEach(() => {
    if (clientWidth) Object.defineProperty(HTMLElement.prototype, 'clientWidth', clientWidth)
  })

  test('the panels give way so the canvas keeps its minimum, and the separators report the widths in use', async () => {
    Object.defineProperty(HTMLElement.prototype, 'clientWidth', { configurable: true, get: () => 700 })
    open()
    await screen.findByRole('navigation', { name: 'Agent lanes' })
    // 700 px: the canvas keeps 352, so the lane may be 160 at most and the co-pilot 260 at most
    expect(gridOf().style.gridTemplateColumns).toBe('160px 6px minmax(22rem,1fr) 6px 260px')
    const lanes = screen.getByRole('separator', { name: 'Resize the agents lane' })
    expect(Number(lanes.getAttribute('aria-valuenow'))).toBeLessThanOrEqual(Number(lanes.getAttribute('aria-valuemax')))
    // the finding drawer docks against the co-pilot as drawn, not as saved
    expect(useLayout.getState().copilotUsed).toBe(260)
  })
})

test('the agents lane toggle sits at the left of the top bar and the co-pilot toggle at the right, each beside its own panel', async () => {
  open()
  await screen.findByRole('navigation', { name: 'Agent lanes' })
  const lanes = screen.getByRole('button', { name: 'Agents lane' })
  const copilot = screen.getByRole('button', { name: 'Co-pilot' })
  const crumbs = screen.getByRole('navigation', { name: 'Breadcrumb' })
  expect(lanes.compareDocumentPosition(crumbs) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  expect(crumbs.compareDocumentPosition(copilot) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
})

test('Reset layout hands the keyboard focus on instead of dropping it when the button goes away', async () => {
  const user = userEvent.setup()
  open()
  await screen.findByRole('navigation', { name: 'Agent lanes' })
  act(() => useLayout.getState().setLanesW(400))
  const reset = await screen.findByRole('button', { name: 'Reset panel layout' })
  reset.focus()
  await user.keyboard('{Enter}')
  expect(screen.queryByRole('button', { name: 'Reset panel layout' })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Agents lane' })).toHaveFocus()
})

test('Reset layout appears once the layout is changed, and puts everything back', async () => {
  const user = userEvent.setup()
  open()
  await screen.findByRole('navigation', { name: 'Agent lanes' })
  expect(screen.queryByRole('button', { name: 'Reset panel layout' })).not.toBeInTheDocument()
  act(() => {
    useLayout.getState().setLanesW(400)
    useLayout.getState().toggleCopilot()
  })
  await user.click(await screen.findByRole('button', { name: 'Reset panel layout' }))
  expect(useLayout.getState()).toMatchObject({ lanesW: 256, copilotOpen: true })
  expect(screen.queryByRole('button', { name: 'Reset panel layout' })).not.toBeInTheDocument()
})

test('a what-if laid over the canvas says so above it, and its button goes back to the approved design', async () => {
  const user = userEvent.setup()
  open()
  const canvas = await screen.findByRole('region', { name: 'Canvas' })
  act(() => useUi.getState().setWhatIf({ result: { param: 'rack_kw', value: 200, findings: [], impact_chain: [] } as never, origin: 'engine' }))
  const back = await within(canvas).findByRole('button', { name: 'Back to r2 (signed)' })
  expect(within(canvas).getByRole('status')).toHaveTextContent('What-if on screen: Racks → 200 kW')
  await user.click(back)
  expect(useUi.getState().whatIf).toBeNull()
  expect(within(canvas).queryByRole('button', { name: /^Back to/ })).not.toBeInTheDocument()
})

test('revision timeline shows fail counts, the signer and switches revisions', async () => {
  const user = userEvent.setup()
  open()
  const footer = await screen.findByRole('contentinfo', { name: 'Revisions' })
  expect(within(footer).getByRole('button', { name: /r1 2 fail/ })).toBeInTheDocument()
  expect(within(footer).getByText(/signed by Priya Raman/)).toBeInTheDocument()
  await user.click(within(footer).getByRole('button', { name: /r1/ }))
  expect(useUi.getState().viewRev).toBe('r1')
  expect(within(footer).getByRole('link', { name: 'Open review' })).toHaveAttribute('href', '/app/p/hall-a/review/r1')
})

test('requirement cards show verified quotes with tender chips', async () => {
  const user = userEvent.setup()
  open()
  const reqs = await screen.findByRole('region', { name: 'Requirements' })
  expect(within(reqs).getAllByText('quote verified')).toHaveLength(2)
  await user.click(within(reqs).getByRole('button', { name: 'Open tender §4.6 · p.4' }))
  expect(useUi.getState().citation?.page).toBe(4)
})

test('?tab= deep link selects the canvas tab', async () => {
  open('/app/p/hall-a?tab=matrix')
  await screen.findByRole('navigation', { name: 'Agent lanes' })
  expect(screen.getByRole('tab', { name: 'Matrix' })).toHaveAttribute('aria-selected', 'true')
})

test('?rev= and ?finding= are applied again when only the query changes (tour step 3)', async () => {
  const user = userEvent.setup()
  function Jump() {
    const navigate = useNavigate()
    return <button onClick={() => navigate('/app/p/hall-a?tab=matrix&rev=r1&finding=R05:FA-01')}>jump</button>
  }
  renderWithProviders(
    <Routes>
      <Route
        path="/app/p/:pid"
        element={
          <>
            <Jump />
            <WorkspacePage />
          </>
        }
      />
    </Routes>,
    { route: '/app/p/hall-a?tab=matrix' },
  )
  await screen.findByRole('navigation', { name: 'Agent lanes' })
  await user.click(screen.getByRole('button', { name: 'jump' }))
  expect(useUi.getState().findingId).toBe('R05:FA-01')
  expect(useUi.getState().viewRev).toBe('r1')
})

test('D4: a signed recorded design says so in the header, links to its review, and names the signer\'s role once', async () => {
  open()
  const header = (await screen.findByRole('heading', { name: /Deccan AI Campus · Hall A/ })).closest('div')!
  expect(within(header).getByText('Recorded design')).toBeInTheDocument()
  expect(within(header).getByText('signed r2')).toBeInTheDocument()
  expect(within(header).queryByText('No agents working')).not.toBeInTheDocument()
  const signed = within(header).getByRole('link', { name: 'Signed · view review' })
  expect(signed).toHaveAttribute('href', '/app/p/hall-a/review/r2')
  expect(within(header).queryByRole('link', { name: /Request sign-off/ })).not.toBeInTheDocument()
  const footer = screen.getByRole('contentinfo', { name: 'Revisions' })
  expect(within(footer).getByText('signed by Priya Raman · Lead Electrical Engineer (Reviewer)')).toBeInTheDocument()
})

test('D11: an unknown project says "Project not found" with a way back, never a raw JSON error', async () => {
  const services = fakeServices({
    getJson: vi.fn(async (url: string) => {
      if (url in STATIC_FILES) return structuredClone(STATIC_FILES[url])
      throw new SyntaxError(`Unexpected token '<', "<!doctype "... is not valid JSON`) // Hosting serves index.html
    }),
  })
  renderWithProviders(<WorkspacePage />, { route: '/app/p/no-such-project', path: '/app/p/:pid', services })
  expect(await screen.findByText('Project not found')).toBeInTheDocument()
  expect(screen.queryByText(/Unexpected token/)).not.toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Back to projects' })).toHaveAttribute('href', '/app')
})

test('D11: a network failure offers Try again and Back to projects, never "Failed to fetch"', async () => {
  const services = fakeServices({ getJson: vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))) })
  renderWithProviders(<WorkspacePage />, { route: '/app/p/hall-a', path: '/app/p/:pid', services })
  expect(await screen.findByText("Couldn't load this page")).toBeInTheDocument()
  expect(screen.getByText('Check your connection and try again.')).toBeInTheDocument()
  expect(screen.queryByText(/Failed to fetch/)).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Back to projects' })).toHaveAttribute('href', '/app')
})

test('D12: an archived project without revisions opens a read-only summary with its PRs, not an empty workspace', async () => {
  const services = fakeServices({
    getJson: vi.fn(async (url: string) => {
      if (url === '/demo/projects/vindhya-lv.json') return structuredClone(vindhya)
      if (url in STATIC_FILES) return structuredClone(STATIC_FILES[url])
      throw new Error(`${url}: 404`)
    }),
  })
  renderWithProviders(<WorkspacePage />, { route: '/app/p/vindhya-lv', path: '/app/p/:pid', services })
  expect(await screen.findByText('Archived · read-only')).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Vindhya Steel · Mill LV upgrade' })).toBeInTheDocument()
  const prs = screen.getByRole('table', { name: 'Purchase requisitions' })
  expect(within(prs).getByText('PR-2026-0101')).toBeInTheDocument()
  expect(within(prs).getByText(/2 × TX-2000-11/)).toBeInTheDocument()
  expect(screen.queryByRole('navigation', { name: 'Agent lanes' })).not.toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Back to projects' })).toHaveAttribute('href', '/app')
})

test('D13: the workspace carries a dismissible "Best on a desktop" note for phones, pointing at the pages that read well there', async () => {
  const user = userEvent.setup()
  open()
  const note = await screen.findByRole('note', { name: 'Best on a desktop' }) // N8: announced as a note
  expect(note).toHaveClass('md:hidden') // phones only
  expect(within(note).getByRole('link', { name: 'review page' })).toHaveAttribute('href', '/app/p/hall-a/review/r2')
  expect(within(note).getByRole('link', { name: 'Integrations' })).toHaveAttribute('href', '/app/integrations')
  await user.click(within(note).getByRole('button', { name: 'Dismiss' }))
  expect(screen.queryByLabelText('Best on a desktop')).not.toBeInTheDocument()
  expect(localStorage.getItem('kirchhoff.desktopNote.dismissed')).toBe('true')
})
