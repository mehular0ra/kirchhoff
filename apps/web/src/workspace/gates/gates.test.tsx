import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { TooltipProvider } from '@/components/ui/tooltip'
import type { DataSource } from '@/lib/select'
import type { Bundle } from '@/lib/types'
import { ApiError } from '@/services/apiClient'
import { ServicesProvider, type Services } from '@/services/services'
import { fixtureBundle } from '@/test/fixtures'
import { fakeApi, fakeServices, resetStores } from '@/test/render'
import { DocsTab } from '../docs/DocsTab'
import { HeaderActions } from '../HeaderActions'
import { WorkspaceProvider } from '../WorkspaceContext'
import { OptionCards } from './OptionCards'
import { PlanGate } from './PlanGate'

function wrap(ui: ReactNode, { bundle = fixtureBundle(), source = 'static' as DataSource, services = fakeServices() as Services } = {}) {
  resetStores()
  return render(
    <ServicesProvider services={services}>
      <TooltipProvider>
        <MemoryRouter>
          <WorkspaceProvider bundle={bundle} source={source}>
            {ui}
          </WorkspaceProvider>
        </MemoryRouter>
      </TooltipProvider>
    </ServicesProvider>,
  )
}

function atGate(gate: 'plan' | 'option'): Bundle {
  const b = fixtureBundle()
  b.runs = [{ ...b.runs[0], status: 'at_gate', gate, selected_option: gate === 'option' ? null : b.runs[0].selected_option }]
  return b
}

test('option cards show engine metrics, swaps and the selected option', () => {
  wrap(<OptionCards />)
  const card = screen.getByRole('article', { name: 'Option 2N' })
  expect(within(card).getByText('18.9 MVA')).toBeInTheDocument()
  expect(within(card).getByText('38% / 76%')).toBeInTheDocument()
  expect(within(card).getByText('$4,200,000')).toBeInTheDocument()
  expect(within(card).getByText('12 weeks')).toBeInTheDocument()
  expect(within(card).getByText('Selected')).toBeInTheDocument()
  expect(within(card).getByRole('list', { name: 'Swaps applied' })).toHaveTextContent('TX-2500 TX-3150(R15, line T-A1)')
  expect(screen.queryByRole('button', { name: /select/i })).not.toBeInTheDocument()
  expect(screen.getByText('IEC-based, illustrative values, not for construction')).toBeInTheDocument()
})

test('at a live option gate the engineer picks a topology through the API', async () => {
  const user = userEvent.setup()
  const api = fakeApi({ optionGate: vi.fn(async () => undefined) })
  wrap(<OptionCards />, { bundle: atGate('option'), source: 'live', services: fakeServices({ api }) })
  await user.click(screen.getByRole('button', { name: 'Select DR' }))
  expect(api.optionGate).toHaveBeenCalledWith('run-hall-a', 'DR')
})

test('a select error at the option gate shows the described API error with an icon', async () => {
  const user = userEvent.setup()
  const api = fakeApi({
    optionGate: vi.fn(async () => {
      throw new ApiError(409, 'wrong_state')
    }),
  })
  wrap(<OptionCards />, { bundle: atGate('option'), source: 'live', services: fakeServices({ api }) })
  await user.click(screen.getByRole('button', { name: 'Select DR' }))
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('The run is no longer waiting at this gate; the view catches up in a moment.')
  expect(alert.querySelector('svg')).toBeTruthy()
})

test('plan gate: answer the open question, add a note, approve', async () => {
  const user = userEvent.setup()
  const api = fakeApi({ planGate: vi.fn(async () => undefined) })
  const b = atGate('plan')
  wrap(<PlanGate run={b.runs[0]} interactive />, { bundle: b, source: 'live', services: fakeServices({ api }) })
  expect(screen.getByText('Plan gate · waiting for you')).toBeInTheDocument()
  await user.click(screen.getByRole('radio', { name: '2N' }))
  await user.type(screen.getByRole('textbox', { name: 'Note for Place racks (default placement)' }), 'keep R1 short')
  await user.click(screen.getByRole('button', { name: 'Approve plan' }))
  expect(api.planGate).toHaveBeenCalledWith('run-hall-a', { 'Q-redundancy': '2N' }, { 'p2.place_racks': 'keep R1 short' })
})

test('plan gate approve error shows an icon alongside the text', async () => {
  const user = userEvent.setup()
  const api = fakeApi({
    planGate: vi.fn(async () => {
      throw new ApiError(422, 'invalid_answer')
    }),
  })
  const b = atGate('plan')
  wrap(<PlanGate run={b.runs[0]} interactive />, { bundle: b, source: 'live', services: fakeServices({ api }) })
  await user.click(screen.getByRole('button', { name: 'Approve plan' }))
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('That answer is not one of the offered options.')
  expect(alert.querySelector('svg')).toBeTruthy()
})

test('a recorded plan is read-only and shows how the question was resolved', () => {
  const b = fixtureBundle()
  wrap(<PlanGate run={b.runs[0]} interactive={false} />)
  expect(screen.getByText('Compare all three topologies')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Approve plan' })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Open tender §4.2 · p.3' })).toBeInTheDocument()
})

test('docs tab lists inputs, exports and the assumptions ledger', () => {
  wrap(<DocsTab />)
  expect(screen.getByRole('button', { name: /tender-hall-a\.pdf/ })).toBeInTheDocument()
  // A public export URL is a plain link (opens without a popup blocker getting in the way).
  expect(screen.getByRole('link', { name: /Calc report/ })).toHaveAttribute('href', '/demo/files/hall-a/calc-report.pdf')
  const notChecked = screen.getByRole('region', { name: 'Not checked in v0.1' })
  expect(notChecked).toHaveTextContent('Earth-fault loop impedance')
})

test('docs tab mounts the read-only plan with the resolved open question for a run past the plan gate', () => {
  wrap(<DocsTab />)
  expect(screen.getByRole('button', { name: 'Open tender §4.2 · p.3' })).toBeInTheDocument()
  expect(screen.getByText('Compare all three topologies')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Approve plan' })).not.toBeInTheDocument()
})

test('header actions: sign-off links to the latest revision; autonomy is locked to the run', () => {
  wrap(<HeaderActions />)
  expect(screen.getByRole('link', { name: /request sign-off/i })).toHaveAttribute('href', '/app/p/hall-a/review/r2')
  expect(screen.getByRole('radio', { name: /^Ask/ })).toBeDisabled()
})
