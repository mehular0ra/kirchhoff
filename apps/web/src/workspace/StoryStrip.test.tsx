import { render, screen } from '@testing-library/react'
import { normalizeBundle, type ProjectBundle } from '@/lib/types'
import { fixtureBundle } from '@/test/fixtures'
import hallASigned from '@/test/fixtures/hall-a-signed.json'
import { resetStores } from '@/test/render'
import { StoryStrip } from './StoryStrip'
import { WorkspaceProvider } from './WorkspaceContext'

const hallA = () => normalizeBundle(structuredClone(hallASigned) as unknown as ProjectBundle)

function renderStrip(bundle = hallA()) {
  resetStores()
  return render(
    <WorkspaceProvider bundle={bundle} source="static">
      <StoryStrip />
    </WorkspaceProvider>,
  )
}

test('I1: the story strip tells r1 → r2 from counted findings and the approval record', () => {
  renderStrip()
  const strip = screen.getByRole('group', { name: 'Revision story' })
  expect(strip).toHaveTextContent('r1 · 149 checks · 2 fail → r2 · 150 checks · all pass · signed by Priya Raman')
})

test('I1: no strip for a single unsigned revision', () => {
  const b = fixtureBundle()
  b.revisions = b.revisions.slice(0, 1)
  b.approvals = []
  renderStrip(b)
  expect(screen.queryByRole('group', { name: 'Revision story' })).not.toBeInTheDocument()
})
