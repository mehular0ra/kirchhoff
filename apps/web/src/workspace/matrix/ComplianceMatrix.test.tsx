import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TooltipProvider } from '@/components/ui/tooltip'
import { CHAIN_COLORS } from '@/lib/agents'
import { fixtureBundle } from '@/test/fixtures'
import { resetStores } from '@/test/render'
import { useUi } from '@/store/ui'
import { WorkspaceProvider } from '../WorkspaceContext'
import { ComplianceMatrix } from './ComplianceMatrix'
import { buildMatrix } from './matrixRows'

function renderMatrix() {
  resetStores()
  return render(
    <TooltipProvider>
      <WorkspaceProvider bundle={fixtureBundle()} source="static">
        <ComplianceMatrix />
      </WorkspaceProvider>
    </TooltipProvider>,
  )
}

test('rows are elements with fails first; columns are R01–R15 plus R04b', () => {
  const { rows, rules } = buildMatrix(fixtureBundle().findings.r1)
  expect(rules.slice(0, 6)).toEqual(['R01', 'R02', 'R03', 'R04', 'R04b', 'R05'])
  expect(rules).toHaveLength(16)
  expect(rows.map((r) => r.element)).toEqual(['FA-01', 'H-Z2', 'BR-R1', 'A-01', 'T-A1'])
  expect(Object.keys(rows[4].cells).sort()).toEqual(['R01', 'R15'])
})

test('matrix renders statuses as icon plus text and counts checks', () => {
  renderMatrix()
  act(() => useUi.getState().setViewRev('r1'))
  const table = screen.getByRole('table', { name: 'Compliance matrix' })
  const fail = within(table).getByRole('button', { name: 'R05 FA-01: Fail' })
  expect(fail).toHaveTextContent('Fail')
  expect(within(table).getByRole('button', { name: 'R10 BR-R1: Warn' })).toHaveTextContent('Warn')
  expect(within(table).getByRole('button', { name: 'R01 T-A1: Pass' })).toHaveTextContent('Pass')
  expect(screen.getByText('6 checks')).toBeInTheDocument()
  expect(screen.getByText('2 fail')).toBeInTheDocument()
  expect(screen.getByText('IEC-based, illustrative values, not for construction')).toBeInTheDocument()
  expect(within(table).getAllByRole('row')[1]).toHaveAttribute('data-tour', 'matrix-row')
})

test('clicking a cell opens that finding; a what-if swaps in the shadow results', async () => {
  const user = userEvent.setup()
  renderMatrix()
  await user.click(screen.getByRole('button', { name: 'R05 FA-01: Pass' }))
  expect(useUi.getState().findingId).toBe('R05:FA-01')
  act(() => useUi.getState().setWhatIf({ result: fixtureBundle().what_ifs[0], origin: 'precomputed' }))
  expect(screen.getByText('What-if view (not saved)')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'R02 A-01: Fail' })).toBeInTheDocument()
})

test('re-sorting rows by worst status keeps the DOM node for an unrelated element, and for a moved element\'s existing cells (rows are keyed by element, not index)', () => {
  resetStores()
  const bundle = fixtureBundle()
  act(() => useUi.getState().setViewRev('r1'))
  const { rerender } = render(
    <TooltipProvider>
      <WorkspaceProvider bundle={bundle} source="static">
        <ComplianceMatrix />
      </WorkspaceProvider>
    </TooltipProvider>,
  )
  // Before: FA-01(fail), H-Z2(fail), BR-R1(warn), A-01(pass), T-A1(pass).
  const unrelatedNode = screen.getByRole('button', { name: 'R11 H-Z2: Fail' })
  const movedElementsOldCell = screen.getByRole('button', { name: 'R02 A-01: Pass' })

  // A new fail lands on A-01 (currently mid-pack), jumping its row to the top.
  const updated = {
    ...bundle,
    findings: {
      ...bundle.findings,
      r1: [...bundle.findings.r1, { id: 'R04:A-01', rule_id: 'R04', element_id: 'A-01', status: 'fail' as const, title: 'Breaker Icu' }],
    },
  }
  rerender(
    <TooltipProvider>
      <WorkspaceProvider bundle={updated} source="static">
        <ComplianceMatrix />
      </WorkspaceProvider>
    </TooltipProvider>,
  )
  // After: A-01(fail), FA-01(fail), H-Z2(fail), BR-R1(warn), T-A1(pass) — every row but T-A1 moved.
  expect(screen.getByRole('button', { name: 'R11 H-Z2: Fail' })).toBe(unrelatedNode)
  expect(screen.getByRole('button', { name: 'R02 A-01: Pass' })).toBe(movedElementsOldCell)
  // The genuinely new finding mounts as its own node.
  expect(screen.getByRole('button', { name: 'R04 A-01: Fail' })).toBeInTheDocument()
})

test('an n/a finding renders icon plus text "N/A" with the right accessible name', () => {
  resetStores()
  const bundle = fixtureBundle()
  bundle.findings.r1 = [...bundle.findings.r1, { id: 'R06:X-01', rule_id: 'R06', element_id: 'X-01', status: 'n/a', title: 'Single points of failure' }]
  render(
    <TooltipProvider>
      <WorkspaceProvider bundle={bundle} source="static">
        <ComplianceMatrix />
      </WorkspaceProvider>
    </TooltipProvider>,
  )
  act(() => useUi.getState().setViewRev('r1'))
  const btn = screen.getByRole('button', { name: 'R06 X-01: N/A' })
  expect(btn).toHaveTextContent('N/A')
})

test('a finding with a rule id outside RULES appends an extra column, sorted after the canonical ones', () => {
  const findings = [...fixtureBundle().findings.r1, { id: 'R99:X-01', rule_id: 'R99', element_id: 'X-01', status: 'fail' as const, title: 'Extra rule' }]
  const { rules } = buildMatrix(findings)
  expect(rules.slice(0, 16)).toEqual(['R01', 'R02', 'R03', 'R04', 'R04b', 'R05', 'R06', 'R07', 'R08', 'R09', 'R10', 'R11', 'R12', 'R13', 'R14', 'R15'])
  expect(rules[16]).toBe('R99')
  expect(rules).toHaveLength(17)

  resetStores()
  render(
    <TooltipProvider>
      <WorkspaceProvider bundle={{ ...fixtureBundle(), findings: { ...fixtureBundle().findings, r1: findings } }} source="static">
        <ComplianceMatrix />
      </WorkspaceProvider>
    </TooltipProvider>,
  )
  act(() => useUi.getState().setViewRev('r1'))
  expect(screen.getByRole('columnheader', { name: 'R99' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'R99 X-01: Fail' })).toBeInTheDocument()
})

test('a what-if introducing an element absent from the base revision shows its row; clearing it restores the base rows', () => {
  renderMatrix()
  expect(screen.queryByRole('button', { name: /CDU-1/ })).not.toBeInTheDocument()
  act(() => useUi.getState().setWhatIf({ result: fixtureBundle().what_ifs[0], origin: 'precomputed' }))
  expect(screen.getByRole('button', { name: 'R08 CDU-1: Fail' })).toBeInTheDocument()
  act(() => useUi.getState().setWhatIf(null))
  expect(screen.queryByRole('button', { name: /CDU-1/ })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'R05 FA-01: Pass' })).toBeInTheDocument()
})

test('I7: the header counts add up — n/a is shown when present, and each count carries its status icon', () => {
  resetStores()
  const bundle = fixtureBundle()
  bundle.findings.r1 = [...bundle.findings.r1, { id: 'R06:X-01', rule_id: 'R06', element_id: 'X-01', status: 'n/a', title: 'Single points of failure' }]
  render(
    <TooltipProvider>
      <WorkspaceProvider bundle={bundle} source="static">
        <ComplianceMatrix />
      </WorkspaceProvider>
    </TooltipProvider>,
  )
  act(() => useUi.getState().setViewRev('r1'))
  expect(screen.getByText('7 checks')).toBeInTheDocument()
  for (const t of ['2 fail', '1 warn', '3 pass', '1 n/a']) expect(screen.getByText(t).querySelector('svg')).not.toBeNull()
  act(() => useUi.getState().setViewRev('r2'))
  expect(screen.queryByText(/n\/a$/)).not.toBeInTheDocument()
})

test('backlog [3]: the matrix is one tab stop; arrow keys move between cells (roving tabindex)', async () => {
  const user = userEvent.setup()
  renderMatrix()
  act(() => useUi.getState().setViewRev('r1'))
  const table = screen.getByRole('table', { name: 'Compliance matrix' })
  const tabbable = [...table.querySelectorAll<HTMLElement>('button')].filter((b) => b.tabIndex === 0)
  expect(tabbable).toHaveLength(1)
  expect(tabbable[0]).toHaveTextContent('FA-01') // first row's element name
  tabbable[0].focus()
  await user.keyboard('{ArrowRight}')
  expect(document.activeElement).toBe(within(table).getByRole('button', { name: 'R05 FA-01: Fail' }))
  await user.keyboard('{ArrowLeft}')
  expect(document.activeElement).toHaveTextContent('FA-01')
  await user.keyboard('{End}')
  expect(document.activeElement).toBe(within(table).getByRole('button', { name: 'R05 FA-01: Fail' }))
  await user.keyboard('{ArrowDown}') // H-Z2 has no R05 cell: the nearest cell in that row
  expect(document.activeElement?.closest('tr')).toHaveTextContent('H-Z2')
  await user.keyboard('{Home}')
  expect(document.activeElement).toHaveTextContent('H-Z2')
  expect([...table.querySelectorAll<HTMLElement>('button')].filter((b) => b.tabIndex === 0)).toEqual([document.activeElement])
  await user.keyboard('{Enter}')
  expect(useUi.getState().focusId).toBe('H-Z2')
})

test('M13: in what-if view the header counts what-if findings, not "checks"', () => {
  renderMatrix()
  act(() => useUi.getState().setWhatIf({ result: fixtureBundle().what_ifs[0], origin: 'precomputed' }))
  expect(screen.getByText('3 what-if findings')).toBeInTheDocument()
  expect(screen.queryByText(/^\d+ checks$/)).not.toBeInTheDocument()
})

test('D6: in what-if view the header shows only non-zero counts and says only failing checks are listed', async () => {
  const b = fixtureBundle()
  resetStores()
  const result = b.what_ifs.find((w) => w.param === 'rack_kw' && w.value === 200)!
  act(() => useUi.getState().setWhatIf({ result, origin: 'precomputed' }))
  render(
    <TooltipProvider>
      <WorkspaceProvider bundle={b} source="static">
        <ComplianceMatrix />
      </WorkspaceProvider>
    </TooltipProvider>,
  )
  const fails = result.findings.filter((f) => f.status === 'fail').length
  expect(screen.getByText(`${fails} fail`)).toBeInTheDocument()
  expect(screen.queryByText('0 pass')).not.toBeInTheDocument()
  expect(screen.queryByText('0 warn')).not.toBeInTheDocument()
  expect(screen.getByText('(only failing checks are listed)')).toBeInTheDocument()
})

test('D6: impact-chain colours stay clear of the pipe blue and the status hues', () => {
  expect(CHAIN_COLORS).toEqual({ electrical: '#fb923c', cooling: '#c084fc' })
})

test('residual: a not-checked cell has an accessible name without adding an element per blank cell', () => {
  renderMatrix()
  const table = screen.getByRole('table', { name: 'Compliance matrix' })
  const blank = within(table).getAllByRole('cell', { name: /: not checked$/ })
  expect(blank.length).toBeGreaterThan(0)
  expect(blank[0]).toBeEmptyDOMElement() // still the CSS dot, no child nodes
  expect(blank[0].getAttribute('aria-label')).toMatch(/^R\d{2}b? [A-Z0-9-]+: not checked$/)
})

test('residual: an element no canvas draws (R12 "BOQ") opens its finding instead of switching to an empty 3D view', async () => {
  const user = userEvent.setup()
  resetStores()
  const b = fixtureBundle()
  const f0 = b.findings.r2[0]
  b.findings.r2 = [...b.findings.r2, { ...f0, id: 'R12:BOQ', rule_id: 'R12', element_id: 'BOQ', status: 'pass', inputs: {} }]
  act(() => useUi.getState().setTab('matrix'))
  render(
    <TooltipProvider>
      <WorkspaceProvider bundle={b} source="static">
        <ComplianceMatrix />
      </WorkspaceProvider>
    </TooltipProvider>,
  )
  await user.click(screen.getByRole('button', { name: 'BOQ' }))
  expect(useUi.getState().tab).toBe('matrix')
  expect(useUi.getState().findingId).toBe('R12:BOQ')
})
