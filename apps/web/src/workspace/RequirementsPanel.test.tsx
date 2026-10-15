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
