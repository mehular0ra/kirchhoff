import { act, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { ServicesProvider } from '@/services/services'
import { fixtureBundle } from '@/test/fixtures'
import { fakeServices, resetStores } from '@/test/render'
import { RunBar } from './RunBar'
import { WorkspaceProvider } from './WorkspaceContext'

test('M2: a live view whose run never appears (stale link, reset, another visitor) stops "connecting" and offers a way out', async () => {
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
  // A cold start can take longer than 10 s: keep waiting (the listener stays live) and say so (residual).
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  expect(screen.getByRole('status')).toHaveTextContent(/Still waiting for your run/)
  act(() => vi.advanceTimersByTime(50_000))
  await act(async () => {}) // Hall A's static bundle (does it carry a recorded run?) has loaded
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

function renderLiveBar(status: 'running' | 'at_gate' | 'done' | 'failed' | 'expired') {
  resetStores()
  const b = fixtureBundle()
  b.runs = [{ ...b.runs[0], status, phase: 'p3', gate: status === 'at_gate' ? 'option' : null, finished_at: status === 'running' || status === 'at_gate' ? null : 1_000 }]
  render(
    <ServicesProvider services={fakeServices()}>
      <MemoryRouter>
        <WorkspaceProvider bundle={b} source="live">
          <RunBar controls={null} />
        </WorkspaceProvider>
      </MemoryRouter>
    </ServicesProvider>,
  )
}

test('a finished run offers another run, and says that what-ifs only re-check and do not redesign', () => {
  renderLiveBar('done')
  expect(screen.getByText('Run complete')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Run Hall B again' })).toHaveAttribute('href', '/app/p/hall-b')
  expect(screen.getByText(/What-ifs only re-check this design/)).toBeInTheDocument()
})

test('a failed run keeps Resume and also offers a new run', () => {
  renderLiveBar('failed')
  expect(screen.getByRole('button', { name: /Resume/ })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Start a new run' })).toHaveAttribute('href', '/app/p/hall-b')
})

test('a run in progress does not offer a second one', () => {
  renderLiveBar('running')
  expect(screen.queryByRole('link', { name: /again|new run/i })).not.toBeInTheDocument()
  renderLiveBar('at_gate')
  expect(screen.queryByRole('link', { name: /again|new run/i })).not.toBeInTheDocument()
})

test('residual: a run that appears after the first wait replaces the waiting note', () => {
  vi.useFakeTimers()
  resetStores()
  const empty = { ...fixtureBundle(), runs: [] }
  const tree = (b: ReturnType<typeof fixtureBundle>) => (
    <ServicesProvider services={fakeServices()}>
      <MemoryRouter>
        <WorkspaceProvider bundle={b} source="live">
          <RunBar controls={null} />
        </WorkspaceProvider>
      </MemoryRouter>
    </ServicesProvider>
  )
  const { rerender } = render(tree(empty))
  act(() => vi.advanceTimersByTime(20_000))
  expect(screen.getByRole('status')).toHaveTextContent(/Still waiting/)
  rerender(tree(fixtureBundle()))
  expect(screen.queryByText(/Still waiting/)).not.toBeInTheDocument()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  vi.useRealTimers()
})

test('D10: a replay of a bundle with no recorded events explains itself instead of "event 0/0" controls', () => {
  resetStores()
  const b = { ...fixtureBundle(), events: [] }
  render(
    <ServicesProvider services={fakeServices()}>
      <MemoryRouter>
        <WorkspaceProvider bundle={b} source="replay">
          <RunBar replay={{ cursor: 0, total: 0, playing: false, speed: 1, elapsedS: 0 }} controls={null} />
        </WorkspaceProvider>
      </MemoryRouter>
    </ServicesProvider>,
  )
  expect(screen.getByText(/This demo snapshot has no recorded run to replay/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /replay$/ })).not.toBeInTheDocument()
  expect(screen.queryByText('16×')).not.toBeInTheDocument()
})
