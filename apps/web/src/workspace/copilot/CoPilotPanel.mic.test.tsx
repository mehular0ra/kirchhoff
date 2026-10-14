// Separate from CoPilotPanel.test.tsx (which exercises canRecord() === true, the jsdom default via
// test-setup.ts stubs) so this file can mock canRecord() === false in isolation: when the device has
// no microphone, the voice controls are hidden and a short explanation is shown instead (typed chips
// still work in every mode).
import { render, screen } from '@testing-library/react'
import { TooltipProvider } from '@/components/ui/tooltip'
import { ServicesProvider } from '@/services/services'
import { fixtureBundle } from '@/test/fixtures'
import { fakeServices, resetStores } from '@/test/render'
import { WorkspaceProvider } from '../WorkspaceContext'
import { CoPilotPanel } from './CoPilotPanel'

vi.mock('./voice/pushToTalk', async () => {
  const actual = await vi.importActual<typeof import('./voice/pushToTalk')>('./voice/pushToTalk')
  return { ...actual, canRecord: () => false }
})

test('voice controls are hidden when the device has no microphone', () => {
  resetStores()
  render(
    <ServicesProvider services={fakeServices()}>
      <TooltipProvider>
        <WorkspaceProvider bundle={fixtureBundle()} source="static">
          <CoPilotPanel />
        </WorkspaceProvider>
      </TooltipProvider>
    </ServicesProvider>,
  )
  expect(screen.queryByRole('button', { name: 'Start voice' })).not.toBeInTheDocument()
  expect(screen.getByText(/no microphone access/i)).toBeInTheDocument()
  expect(screen.getByRole('textbox', { name: 'Ask the co-pilot' })).toBeInTheDocument()
})
