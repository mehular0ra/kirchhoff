import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { normalizeBundle, type ProjectBundle, type WhatIfResult } from '@/lib/types'
import { ServicesProvider } from '@/services/services'
import { useUi } from '@/store/ui'
import hallASigned from '@/test/fixtures/hall-a-signed.json'
import { fakeServices, resetStores } from '@/test/render'
import { ViewBanner } from './ViewBanner'
import { WorkspaceProvider } from './WorkspaceContext'

const bundle = (signed = true) => {
  const b = normalizeBundle(structuredClone(hallASigned) as unknown as ProjectBundle)
  // An unsigned run: no approval, and no revision marked signed.
  return signed ? b : { ...b, approvals: [], revisions: b.revisions.map((r) => ({ ...r, status: 'checked' as const })) }
}

function show(b = bundle()) {
  resetStores()
  return render(
    <ServicesProvider services={fakeServices()}>
      <MemoryRouter>
        <WorkspaceProvider bundle={b} source="static">
          <ViewBanner />
        </WorkspaceProvider>
      </MemoryRouter>
    </ServicesProvider>,
  )
}

const whatIf = (): { result: WhatIfResult; origin: 'engine' } => ({
  result: { param: 'rack_kw', value: 200, findings: [], impact_chain: [] } as unknown as WhatIfResult,
  origin: 'engine',
})

test('on the approved design with nothing laid over it there is no banner', () => {
  show()
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /^Back to/ })).not.toBeInTheDocument()
})

test('a what-if on screen says so, that it is not saved, and one click puts the approved design back', async () => {
  const user = userEvent.setup()
  show()
  act(() => useUi.getState().setWhatIf(whatIf()))
  const banner = await screen.findByRole('status')
  expect(banner).toHaveTextContent('What-if on screen: Racks → 200 kW on r2 (signed) · not saved')
  await user.click(screen.getByRole('button', { name: 'Back to r2 (signed)' }))
  expect(useUi.getState().whatIf).toBeNull()
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
})

test('another revision on screen says which one, and one click goes back to the signed design', async () => {
  const user = userEvent.setup()
  show()
  act(() => useUi.getState().setViewRev('r1', { source: 'user' }))
  expect(await screen.findByRole('status')).toHaveTextContent('Showing r1 (checked), not the signed design.')
  await user.click(screen.getByRole('button', { name: 'Back to r2 (signed)' }))
  expect(useUi.getState().viewRev).toBeNull()
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
})

test('a what-if laid over another revision is cleared together with the move back', async () => {
  const user = userEvent.setup()
  show()
  act(() => {
    useUi.getState().setViewRev('r1', { source: 'user' })
    useUi.getState().setWhatIf(whatIf())
  })
  expect(await screen.findByRole('status')).toHaveTextContent('What-if on screen: Racks → 200 kW on r1 (checked) · not saved')
  await user.click(screen.getByRole('button', { name: 'Back to r2 (signed)' }))
  expect(useUi.getState()).toMatchObject({ viewRev: null, whatIf: null })
})

test('when a newer revision exists the way back is to the signed one, not to the newest', async () => {
  const user = userEvent.setup()
  const b = bundle()
  const r2 = b.revisions.find((r) => r.id === 'r2')!
  show({ ...b, revisions: [...b.revisions, { ...r2, id: 'r3', parent: 'r2', status: 'draft' as const }] })
  // nothing is on screen but the newest revision, which is not the signed one
  expect(await screen.findByRole('status')).toHaveTextContent('Showing r3 (draft), not the signed design.')
  await user.click(screen.getByRole('button', { name: 'Back to r2 (signed)' }))
  expect(useUi.getState().viewRev).toBe('r2')
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
})

test('with no signed revision the way back is to the latest one', async () => {
  const user = userEvent.setup()
  show(bundle(false))
  act(() => useUi.getState().setViewRev('r1', { source: 'user' }))
  expect(await screen.findByRole('status')).toHaveTextContent('Showing r1 (checked), not the latest design.')
  await user.click(screen.getByRole('button', { name: 'Back to r2 (checked)' }))
  expect(useUi.getState().viewRev).toBeNull()
})

test('the banner names its state in words with an icon, never by colour alone', async () => {
  show()
  act(() => useUi.getState().setWhatIf(whatIf()))
  const banner = await screen.findByRole('status')
  expect(banner.querySelector('svg')).not.toBeNull()
})
