import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import type { Bundle, ProjectBundle } from '@/lib/types'
import { normalizeBundle } from '@/lib/types'
import { useChecklist } from '@/onboarding/checklist/checklistStore'
import { fixtureBundle } from '@/test/fixtures'
import hallASigned from '@/test/fixtures/hall-a-signed.json'
import { fakeApi, fakeServices, renderWithProviders } from '@/test/render'
import { ReviewPage, ReviewView } from './ReviewPage'

test('signed revision: stamp with name, role, time and hash; diff, ledger and handoff', async () => {
  renderWithProviders(
    <Routes>
      <Route path="/app/p/:pid/review/:rev" element={<ReviewPage />} />
    </Routes>,
    { route: '/app/p/hall-a/review/r2' },
  )
  const stamp = await screen.findByRole('figure', { name: 'Approval stamp' })
  expect(within(stamp).getByText('Approved')).toBeInTheDocument()
  expect(within(stamp).getByText('Priya Raman')).toBeInTheDocument()
  expect(within(stamp).getByText('Lead Electrical Engineer (Reviewer)')).toBeInTheDocument()
  expect(within(stamp).getByText('9 Oct 2025, 14:31')).toBeInTheDocument()
  expect(within(stamp).getByText('Revision r2 · sha256 f9e8d7c6b5a4…')).toBeInTheDocument()
  const changes = screen.getByRole('region', { name: 'Changes from parent' })
  expect(within(changes).getByText('catalogue_id: BW-1600 → CBL-8x240')).toBeInTheDocument()
  expect(within(changes).getByText('tier: pipe_high → pipe_low')).toBeInTheDocument()
  expect(within(screen.getByRole('region', { name: 'Not checked in v0.1' })).getByText(/Earth-fault loop/)).toBeInTheDocument()
  const handoff = screen.getByRole('region', { name: 'Handoff' })
  expect(within(handoff).getByText('PR-2026-0142')).toBeInTheDocument()
  expect(within(handoff).getByText('sandbox (simulated)')).toBeInTheDocument()
  expect(within(handoff).getByText('Design approved')).toBeInTheDocument()
})

function atReview(): Bundle {
  const b = fixtureBundle()
  b.runs = [{ ...b.runs[0], status: 'at_gate', gate: 'review' }]
  b.approvals = []
  return b
}

test('live review gate: Approve is disabled while findings fail', () => {
  renderWithProviders(<ReviewView bundle={atReview()} source="live" revId="r1" runQuery="?run=run-hall-a" />)
  expect(screen.getByRole('alert')).toHaveTextContent('Approve is disabled: 2 findings still fail')
  expect(screen.getByRole('button', { name: /approve and sign/i })).toBeDisabled()
})

test('live review gate: approving posts the decision and ticks the checklist', async () => {
  const user = userEvent.setup()
  useChecklist.getState().reload()
  const api = fakeApi({ reviewGate: vi.fn(async () => undefined) })
  renderWithProviders(<ReviewView bundle={atReview()} source="live" revId="r2" runQuery="?run=run-hall-a" />, {
    services: fakeServices({ api }),
  })
  await user.type(screen.getByRole('textbox', { name: 'Review comment' }), 'Looks right')
  await user.click(screen.getByRole('button', { name: 'Approve and sign as You (Demo Reviewer)' }))
  expect(api.reviewGate).toHaveBeenCalledWith('run-hall-a', 'approved', 'Looks right')
  expect(await screen.findByText(/Approval sent/)).toBeInTheDocument()
  expect(useChecklist.getState().done.approve).toBe(true)
})

test('real signed Hall A bundle: stamp hash matches the bundle, diff shows the real FA-01 and H-Z2 changes, ledger and PRs render', () => {
  const bundle = normalizeBundle(hallASigned as unknown as ProjectBundle)
  const r2 = bundle.revisions.find((r) => r.id === 'r2')!
  renderWithProviders(<ReviewView bundle={bundle} source="static" revId="r2" runQuery="" />)
  const stamp = screen.getByRole('figure', { name: 'Approval stamp' })
  expect(within(stamp).getByText('Priya Raman')).toBeInTheDocument()
  expect(within(stamp).getByText('Lead Electrical Engineer (Reviewer)')).toBeInTheDocument()
  expect(within(stamp).getByText(`Revision r2 · sha256 ${r2.hash.slice(0, 12)}…`)).toBeInTheDocument()

  const changes = screen.getByRole('region', { name: 'Changes from parent' })
  expect(within(changes).getByText('catalogue_id: BW-1600 → CBL-240-8P')).toBeInTheDocument()
  const hZ2 = within(changes).getByText('H-Z2').closest('li')!
  expect(within(hZ2).getByText('route: rerouted')).toBeInTheDocument()

  expect(screen.getByRole('region', { name: 'Not checked in v0.1' })).toBeInTheDocument()

  const handoff = screen.getByRole('region', { name: 'Handoff' })
  for (const prId of ['PR-2026-0142', 'PR-2026-0143', 'PR-2026-0144', 'PR-2026-0145', 'PR-2026-0146', 'PR-2026-0147', 'PR-2026-0148']) {
    expect(within(handoff).getByText(prId)).toBeInTheDocument()
  }
  expect(within(handoff).getByText('Design approved')).toBeInTheDocument()
})
