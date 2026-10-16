import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TooltipProvider } from '@/components/ui/tooltip'
import { useChecklist } from '@/onboarding/checklist/checklistStore'
import { ServicesProvider, type Services } from '@/services/services'
import { useUi } from '@/store/ui'
import { normalizeBundle, type ProjectBundle } from '@/lib/types'
import { fixtureBundle } from '@/test/fixtures'
import hallASigned from '@/test/fixtures/hall-a-signed.json'
import { fakeApi, fakeServices, resetStores } from '@/test/render'
import { ComplianceMatrix } from '../matrix/ComplianceMatrix'
import { WorkspaceProvider } from '../WorkspaceContext'
import { chipLabel, chipsFor } from './useWhatIf'
import { WhatIfPanel } from './WhatIfPanel'

function renderPanel(services: Services = fakeServices()) {
  resetStores()
  useChecklist.getState().reload()
  return render(
    <ServicesProvider services={services}>
      <TooltipProvider>
        <WorkspaceProvider bundle={fixtureBundle()} source="static">
          <WhatIfPanel />
        </WorkspaceProvider>
      </TooltipProvider>
    </ServicesProvider>,
  )
}

test('chips are the engine presets plus any precomputed what-if, deduplicated', () => {
  const chips = chipsFor(fixtureBundle().what_ifs)
  expect(chips.map(chipLabel)).toEqual([
    'Racks → 200 kW',
    'Racks → 150 kW',
    'Liquid fraction → 0.9',
    'ΔV limit → 1.5%',
    'Transformer loading cap → 35%',
  ])
})

test('a precomputed chip works offline and lights the two-colour impact chain', async () => {
  const user = userEvent.setup()
  const { container } = renderPanel()
  const chip = screen.getByRole('button', { name: 'Racks → 200 kW' })
  expect(chip).toHaveAttribute('data-tour', 'whatif-chip')
  await user.click(chip)
  expect(useUi.getState().whatIf?.origin).toBe('precomputed')
  const failures = screen.getByRole('list', { name: 'What-if failures' })
  expect(within(failures).getByText('R02 · A-01')).toBeInTheDocument()
  expect(within(failures).getByText('2,343 A')).toBeInTheDocument()
  const chain = screen.getByRole('list', { name: 'Impact chain' })
  expect(within(chain).getByText('R1-01 → A-01 → CB-A1 → A1 → T-A1')).toBeInTheDocument()
  expect(within(chain).getByText('Cooling:')).toBeInTheDocument()
  expect(container.querySelector('[style*="rgb(124, 58, 237)"]')).not.toBeNull() // cooling violet (D6)
  expect(useChecklist.getState().done.run_whatif).toBe(true)
  await user.click(screen.getByRole('button', { name: 'Clear what-if' }))
  expect(useUi.getState().whatIf).toBeNull()
})

test('other chips call POST /api/what-if with the seed revision ref', async () => {
  const user = userEvent.setup()
  const result = { ...fixtureBundle().what_ifs[0], value: 150 }
  const api = fakeApi({ whatIf: vi.fn(async () => result) })
  renderPanel(fakeServices({ api }))
  await user.click(screen.getByRole('button', { name: 'Racks → 150 kW' }))
  expect(api.whatIf).toHaveBeenCalledWith('seed:hall-a@r2', 'rack_kw', 150)
  expect(useUi.getState().whatIf?.origin).toBe('engine')
})

test('an unreachable engine explains that precomputed chips still work', async () => {
  const user = userEvent.setup()
  renderPanel()
  await user.selectOptions(screen.getByRole('combobox', { name: 'What-if parameter' }), 'dv_limit_pct')
  await user.type(screen.getByRole('textbox', { name: 'What-if value' }), '1.8')
  await user.click(screen.getByRole('button', { name: 'Run' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('precomputed chips still work')
})

test('a custom value outside the engine bounds is rejected before any API call', async () => {
  const user = userEvent.setup()
  const api = fakeApi({ whatIf: vi.fn(async () => fixtureBundle().what_ifs[0]) })
  renderPanel(fakeServices({ api }))
  await user.selectOptions(screen.getByRole('combobox', { name: 'What-if parameter' }), 'tx_loading_cap_pct')
  await user.type(screen.getByRole('textbox', { name: 'What-if value' }), '200')
  await user.click(screen.getByRole('button', { name: 'Run' }))
  const alert = await screen.findByRole('alert')
  expect(alert.querySelector('svg')).toBeTruthy()
  expect(api.whatIf).not.toHaveBeenCalled()
})

test('a 422 from the engine is described through describeApiError, with an icon', async () => {
  const user = userEvent.setup()
  const { ApiError } = await import('@/services/apiClient')
  const api = fakeApi({ whatIf: vi.fn(async () => Promise.reject(new ApiError(422, 'boom'))) })
  renderPanel(fakeServices({ api }))
  await user.selectOptions(screen.getByRole('combobox', { name: 'What-if parameter' }), 'dv_limit_pct')
  await user.type(screen.getByRole('textbox', { name: 'What-if value' }), '1.8')
  await user.click(screen.getByRole('button', { name: 'Run' }))
  const alert = await screen.findByRole('alert')
  expect(alert.querySelector('svg')).toBeTruthy()
  expect(alert).toHaveTextContent('422: boom')
})

test('real Hall A bundle: the 200 kW chip resolves from the bundle, shows failing rules and enters the what-if matrix view', async () => {
  // Queries are scoped to the what-if panel: an unscoped getByRole walks (and computes accessible
  // names for) every node of the full Hall A matrix, which is what made this test time out under
  // full-suite load. The full matrix is still rendered, as in the app.
  const user = userEvent.setup()
  resetStores()
  useChecklist.getState().reload()
  const bundle = normalizeBundle(hallASigned as unknown as ProjectBundle)
  render(
    <ServicesProvider services={fakeServices()}>
      <TooltipProvider>
        <WorkspaceProvider bundle={bundle} source="static">
          <WhatIfPanel />
          <ComplianceMatrix />
        </WorkspaceProvider>
      </TooltipProvider>
    </ServicesProvider>,
  )
  const panel = screen.getByLabelText('What-if', { selector: 'section' })
  await user.click(within(panel).getByRole('button', { name: 'Racks → 200 kW' }))
  expect(useUi.getState().whatIf?.origin).toBe('precomputed')
  expect(screen.getByText('What-if view (not saved)')).toBeInTheDocument()
  const chain = within(panel).getByRole('list', { name: 'Impact chain' })
  expect(within(chain).getAllByText('Electrical:').length).toBeGreaterThan(0)
  expect(within(chain).getAllByText('Cooling:').length).toBeGreaterThan(0)
  await user.click(within(panel).getByRole('button', { name: /^Show all \d+ findings$/ }))
  const failures = within(panel).getByRole('list', { name: 'What-if failures' })
  for (const ruleId of ['R01', 'R02', 'R03', 'R05', 'R07', 'R08', 'R09']) {
    expect(within(failures).getAllByText(new RegExp(`^${ruleId} ·`)).length).toBeGreaterThan(0)
  }
  // ~0.3 s alone after the fixes above (was 0.56 s); the margin covers a loaded machine running
  // the suite's workers in parallel with other jobs (it hit 5.3 s at load average 18 on 8 cores).
}, 15_000)

test('M13: the impact chain comes first and long failure lists are collapsed', async () => {
  const user = userEvent.setup()
  renderPanel()
  const base = fixtureBundle().what_ifs[0]
  const many = { ...base, findings: Array.from({ length: 12 }, (_, i) => ({ ...base.findings[1], id: `R02:B-${i}`, element_id: `B-${i}` })) }
  act(() => useUi.getState().setWhatIf({ result: many, origin: 'precomputed' }))
  const chain = screen.getByRole('list', { name: 'Impact chain' })
  const failures = screen.getByRole('list', { name: 'What-if failures' })
  expect(chain.compareDocumentPosition(failures) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  expect(within(failures).getAllByRole('listitem')).toHaveLength(6)
  await user.click(screen.getByRole('button', { name: 'Show all 12 findings' }))
  expect(within(screen.getByRole('list', { name: 'What-if failures' })).getAllByRole('listitem')).toHaveLength(12)
})

test('M13: switching revision clears the what-if overlay (it was computed for another revision)', () => {
  renderPanel()
  act(() => useUi.getState().setWhatIf({ result: fixtureBundle().what_ifs[0], origin: 'precomputed' }))
  act(() => useUi.getState().setViewRev('r1'))
  expect(useUi.getState().whatIf).toBeNull()
})

// #37: the chips run on the head revision unless the visitor picked a revision in the revision bar.
function renderRealHallA(services: Services) {
  resetStores()
  useChecklist.getState().reload()
  const bundle = normalizeBundle(structuredClone(hallASigned) as unknown as ProjectBundle)
  render(
    <ServicesProvider services={services}>
      <TooltipProvider>
        <WorkspaceProvider bundle={bundle} source="static">
          <WhatIfPanel />
        </WorkspaceProvider>
      </TooltipProvider>
    </ServicesProvider>,
  )
  return { bundle, panel: screen.getByLabelText('What-if', { selector: 'section' }) }
}

test('#37: after an automatic switch to r1 (D1, a deep link), the 200 kW chip is the head revision\'s seed result, on the head', async () => {
  const user = userEvent.setup()
  const api = fakeApi({ whatIf: vi.fn(async () => Promise.reject(new Error('the head revision is precomputed'))) })
  const { bundle, panel } = renderRealHallA(fakeServices({ api }))
  const head = bundle.revisions[bundle.revisions.length - 1]
  act(() => useUi.getState().setViewRev('r1'))
  await user.click(within(panel).getByRole('button', { name: 'Racks → 200 kW' }))
  expect(api.whatIf).not.toHaveBeenCalled()
  const seed = bundle.what_ifs.find((w) => w.revision_ref === `seed:hall-a@${head.id}` && w.param === 'rack_kw' && w.value === 200)!
  expect(useUi.getState().whatIf).toMatchObject({ origin: 'precomputed', result: seed })
  expect(useUi.getState().viewRev).toBeNull() // drawn on the revision it was computed for
  expect(within(panel).getByText(`${head.id} (${head.status}) · not saved · precomputed by the engine`)).toBeInTheDocument()
})

test('#37: after a revision-bar pick of r1, the chip asks the engine for r1 and the card names r1', async () => {
  const user = userEvent.setup()
  const real = normalizeBundle(structuredClone(hallASigned) as unknown as ProjectBundle)
  const seed = real.what_ifs.find((w) => w.param === 'rack_kw' && w.value === 200)!
  const whatIf = vi.fn(async () => ({ ...seed, revision_ref: 'seed:hall-a@r1' }))
  const { bundle, panel } = renderRealHallA(fakeServices({ api: fakeApi({ whatIf }) }))
  act(() => useUi.getState().setViewRev('r1', { source: 'user' }))
  await user.click(within(panel).getByRole('button', { name: 'Racks → 200 kW' }))
  expect(whatIf).toHaveBeenCalledWith('seed:hall-a@r1', 'rack_kw', 200)
  expect(useUi.getState()).toMatchObject({ viewRev: 'r1', whatIf: { origin: 'engine' } })
  const r1 = bundle.revisions.find((r) => r.id === 'r1')!
  expect(within(panel).getByText(`r1 (${r1.status}) · not saved · engine, just now`)).toBeInTheDocument()
})
