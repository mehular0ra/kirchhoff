import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { ApiError } from '@/services/apiClient'
import { useUi } from '@/store/ui'
import { fakeApi, fakeServices, renderWithProviders } from '@/test/render'
import { WorkspacePage } from './WorkspacePage'

function openHallB(services = fakeServices()) {
  return renderWithProviders(
    <Routes>
      <Route path="/app/p/:pid" element={<WorkspacePage />} />
    </Routes>,
    { route: '/app/p/hall-b', services },
  )
}

test('Hall B without a run shows the start panel; starting creates the workspace and opens ?run=', async () => {
  const user = userEvent.setup()
  const api = fakeApi({
    ensureWorkspace: vi.fn(async () => ({ uid: 'visitor-1', created: true })),
    startRun: vi.fn(async () => ({ run_id: 'run-42' })),
  })
  openHallB(fakeServices({ api }))
  expect(screen.getByRole('heading', { name: /Hall B/ })).toBeInTheDocument()
  await user.click(screen.getByRole('radio', { name: /^Auto/ }))
  await user.click(screen.getByRole('button', { name: /start live run/i }))
  expect(api.ensureWorkspace).toHaveBeenCalled()
  expect(api.startRun).toHaveBeenCalledWith('hall-b', 'auto')
  expect(localStorage.getItem('kirchhoff.lastRun.hall-b')).toBe('"run-42"')
  // the run view needs Firestore; the fake has none, so it reports that instead of hanging
  expect(await screen.findByText(/live data is unavailable/i)).toBeInTheDocument()
  expect(useUi.getState().autonomy).toBe('auto')
})

test('the live-run cap offers the replay instead', async () => {
  const user = userEvent.setup()
  const api = fakeApi({
    ensureWorkspace: vi.fn(async () => ({ uid: 'visitor-1', created: false })),
    startRun: vi.fn(async () => {
      throw new ApiError(429, 'global_cap') // WS2: 429 {"detail": "global_cap", "offer": "replay"}
    }),
  })
  openHallB(fakeServices({ api }))
  await user.click(screen.getByRole('button', { name: /start live run/i }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Live runs are at capacity right now. Watch the recorded run instead.')
  expect(screen.getByRole('link', { name: /replay a recorded run/i })).toHaveAttribute('href', '/app/p/hall-a?replay=1')
})

test('replay shows the recorded elapsed clock and time-compression label', async () => {
  renderWithProviders(
    <Routes>
      <Route path="/app/p/:pid" element={<WorkspacePage />} />
    </Routes>,
    { route: '/app/p/hall-a?replay=1' },
  )
  expect(await screen.findByText('Time-compressed replay of a recorded run')).toBeInTheDocument()
  expect(screen.getByText(/Elapsed \(recorded\)/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /pause replay|play replay/i })).toBeInTheDocument()
})
