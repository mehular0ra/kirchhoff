import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TooltipProvider } from '@/components/ui/tooltip'
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
