import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes, useNavigate } from 'react-router'
import { renderWithProviders } from '@/test/render'
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
