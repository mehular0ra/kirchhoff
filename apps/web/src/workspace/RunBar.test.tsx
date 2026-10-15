import { act, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { ServicesProvider } from '@/services/services'
import { fixtureBundle } from '@/test/fixtures'
import { fakeServices, resetStores } from '@/test/render'
import { RunBar } from './RunBar'
import { WorkspaceProvider } from './WorkspaceContext'

test('M2: a live view whose run never appears (stale link, reset, another visitor) stops "connecting" and offers a way out', () => {
  vi.useFakeTimers()
  resetStores()
  const b = { ...fixtureBundle(), runs: [] }
  render(
    <ServicesProvider services={fakeServices()}>
      <MemoryRouter>
        <WorkspaceProvider bundle={b} source="live">
          <RunBar controls={null} />
        </WorkspaceProvider>
      </MemoryRouter>
    </ServicesProvider>,
  )
  expect(screen.getByText('Connecting to your run…')).toBeInTheDocument()
  act(() => vi.advanceTimersByTime(10_000))
  expect(screen.getByRole('alert')).toHaveTextContent(/not in your workspace/)
  expect(screen.getByRole('link', { name: 'Start a new run' })).toHaveAttribute('href', '/app/p/hall-b')
  expect(screen.getByRole('link', { name: 'Watch the recorded run' })).toHaveAttribute('href', '/app/p/hall-a?replay=1')
})

test('M19: a running live run names its phase in words', () => {
  resetStores()
  const b = fixtureBundle()
  b.runs = [{ ...b.runs[0], status: 'running', phase: 'p2', finished_at: null }]
  render(
    <ServicesProvider services={fakeServices()}>
      <MemoryRouter>
        <WorkspaceProvider bundle={b} source="live">
          <RunBar controls={null} />
        </WorkspaceProvider>
      </MemoryRouter>
    </ServicesProvider>,
  )
  expect(screen.getByText('Running · placing racks and weighing options')).toBeInTheDocument()
})
