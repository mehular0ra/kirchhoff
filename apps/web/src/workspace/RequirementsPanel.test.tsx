import { render, screen, within } from '@testing-library/react'
import { TooltipProvider } from '@/components/ui/tooltip'
import { fixtureBundle } from '@/test/fixtures'
import { resetStores } from '@/test/render'
import { RequirementsPanel } from './RequirementsPanel'
import { WorkspaceProvider } from './WorkspaceContext'

test('I11: an unverified requirement shows the "not accepted" sentence, never its text or the verified wording', () => {
  resetStores()
  const b = fixtureBundle()
  const [first, ...rest] = b.brief!.requirements
  b.brief = {
    ...b.brief!,
    requirements: [{ ...first, id: 'REQ-X', verified: false, text: 'Racks shall be 200 kW', citation: { ...first.citation, quote: '' } }, ...rest],
  }
  render(
    <TooltipProvider>
      <WorkspaceProvider bundle={b} source="static">
        <RequirementsPanel />
      </WorkspaceProvider>
    </TooltipProvider>,
  )
  expect(screen.queryByText('Racks shall be 200 kW')).not.toBeInTheDocument()
  const card = screen.getAllByRole('listitem')[0]
  expect(card).toHaveTextContent('Requirement not accepted: the quote was not found on the cited page.')
  expect(within(card).getByText('quote not verified')).toBeInTheDocument()
  expect(within(card).queryByText('quote verified')).not.toBeInTheDocument()
})

const SAMPLE_LINE = 'This sample includes the checked design, findings and sign-off; the tender requirements are in the Docs tab.'

test('D10: a recorded design without a brief says what the sample includes; a live run keeps "appear when Intake has read"', () => {
  resetStores()
  const b = fixtureBundle()
  b.brief = null
  const { unmount } = render(
    <TooltipProvider>
      <WorkspaceProvider bundle={b} source="static">
        <RequirementsPanel />
      </WorkspaceProvider>
    </TooltipProvider>,
  )
  expect(screen.getByText(SAMPLE_LINE)).toBeInTheDocument()
  expect(screen.queryByText(/appear when Intake has read/)).not.toBeInTheDocument()
  unmount()
  render(
    <TooltipProvider>
      <WorkspaceProvider bundle={b} source="live">
        <RequirementsPanel />
      </WorkspaceProvider>
    </TooltipProvider>,
  )
  expect(screen.getByText('Requirement cards appear when Intake has read the tender.')).toBeInTheDocument()
})

test('N5: a replay without a brief also shows the sample sentence, not "appear when Intake has read" (?replay=1)', () => {
  resetStores()
  const b = fixtureBundle()
  b.brief = null
  render(
    <TooltipProvider>
      <WorkspaceProvider bundle={b} source="replay">
        <RequirementsPanel />
      </WorkspaceProvider>
    </TooltipProvider>,
  )
  expect(screen.getByText(SAMPLE_LINE)).toBeInTheDocument()
  expect(screen.queryByText(/appear when Intake has read/)).not.toBeInTheDocument()
})
