import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { vi } from 'vitest'
import { useWorldStore } from '@/data/useWorld'
import { ApiError } from '@/services/apiClient'
import { fixtureInbox } from '@/test/fixtures'
import { fakeApi, fakeServices, renderWithProviders, STATIC_FILES } from '@/test/render'
import { InboxPage } from './InboxPage'
import { resetInboxStore } from './useInbox'

beforeEach(() => {
  useWorldStore.setState({ world: null, error: null, loading: false })
  resetInboxStore()
})

function open(emailId: string, services = fakeServices()) {
  return renderWithProviders(
    <Routes>
      <Route path="/app/inbox/:emailId" element={<InboxPage />} />
    </Routes>,
    { route: `/app/inbox/${emailId}`, services },
  )
}
const hallB = (services = fakeServices()) => open('em-hall-b', services)

test('live triage shows progress, then the live result', async () => {
  const user = userEvent.setup()
  const live = { ...fixtureInbox().emails[0].triage!, source: 'live' as const }
  let resolve: (v: typeof live) => void = () => {}
  const api = fakeApi({ triage: vi.fn(() => new Promise<typeof live>((r) => (resolve = r))) })
  hallB(fakeServices({ api }))
  await user.click(await screen.findByRole('button', { name: 'Triage live' }))
  const progress = screen.getByRole('status')
  expect(progress).toHaveTextContent('Reading the email and its attachments')
  expect(progress.querySelector('svg')).toHaveClass('motion-reduce:animate-none')
  resolve(live)
  expect(await screen.findByText('Live triage complete.')).toBeInTheDocument()
  expect(screen.getByText(/live triage · 7\/7 quotes verified/)).toBeInTheDocument()
  expect(api.triage).toHaveBeenCalledWith('em-hall-b')
})

test('with the API down or slow, the recorded triage stays and says why', async () => {
  const user = userEvent.setup()
  const api = fakeApi({ triage: vi.fn(async () => Promise.reject(new ApiError(504, 'timeout'))) })
  hallB(fakeServices({ api }))
  await user.click(await screen.findByRole('button', { name: 'Triage live' }))
  expect(await screen.findByRole('status')).toHaveTextContent(
    'Live triage unavailable: The engine took too long to answer; try again. The recorded triage stays on screen.',
  )
  expect(screen.getByText(/recorded triage · 7\/7 quotes verified/)).toBeInTheDocument()
  expect(within(screen.getByRole('region', { name: 'Fit verdict' })).getByText('Pursue')).toBeInTheDocument()
})

test('only the Hall B email can be triaged live', async () => {
  open('em-vindhya-boq')
  const detail = await screen.findByRole('article')
  expect(within(detail).getByRole('heading', { name: /Captive power switchyard/ })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Triage/ })).not.toBeInTheDocument()
})

test('before the golden capture there is no recorded triage to fall back to, and the page does not claim one', async () => {
  const user = userEvent.setup()
  const snapshot = fixtureInbox()
  snapshot.emails[0].triage = null
  const getJson = vi.fn(async (url: string) =>
    url === '/demo/inbox.json' ? structuredClone(snapshot) : structuredClone(STATIC_FILES[url]),
  )
  const api = fakeApi({ triage: vi.fn(async () => Promise.reject(new ApiError(503, 'offline'))) })
  hallB(fakeServices({ api, getJson }))
  expect(within(await screen.findByRole('article')).getByText(/Not triaged yet/)).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Triage live' }))
  const status = await screen.findByRole('status')
  expect(status).toHaveTextContent('Live triage unavailable:')
  expect(status).not.toHaveTextContent('recorded triage stays')
})

test('a failed live triage can be retried and then succeeds', async () => {
  const user = userEvent.setup()
  const live = { ...fixtureInbox().emails[0].triage!, source: 'live' as const }
  const triage = vi.fn().mockRejectedValueOnce(new ApiError(502, 'triage_failed')).mockResolvedValueOnce(live)
  hallB(fakeServices({ api: fakeApi({ triage }) }))
  await user.click(await screen.findByRole('button', { name: 'Triage live' }))
  expect(await screen.findByRole('status')).toHaveTextContent('The Inbox agent could not finish this triage.')
  await user.click(screen.getByRole('button', { name: 'Triage live' }))
  expect(await screen.findByText('Live triage complete.')).toBeInTheDocument()
  expect(screen.queryByText(/Live triage unavailable/)).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Triage again' })).toBeEnabled()
  expect(triage).toHaveBeenCalledTimes(2)
})

test('the button is reachable and usable from the keyboard, and is disabled while it runs', async () => {
  const user = userEvent.setup()
  const live = { ...fixtureInbox().emails[0].triage!, source: 'live' as const }
  let resolve: (v: typeof live) => void = () => {}
  const triage = vi.fn(() => new Promise<typeof live>((r) => (resolve = r)))
  hallB(fakeServices({ api: fakeApi({ triage }) }))
  const button = await screen.findByRole('button', { name: 'Triage live' })
  button.focus()
  expect(button).toHaveFocus()
  await user.keyboard('{Enter}')
  expect(screen.getByRole('button', { name: 'Triage live' })).toBeDisabled()
  await user.keyboard('{Enter}') // a second press while running must not start a second call
  expect(triage).toHaveBeenCalledTimes(1)
  resolve(live)
  expect(await screen.findByText('Live triage complete.')).toBeInTheDocument()
})
