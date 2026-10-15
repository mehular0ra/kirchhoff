import { render, screen, within } from '@testing-library/react'
import { TooltipProvider } from '@/components/ui/tooltip'
import { ServicesProvider } from '@/services/services'
import { fixtureBundle } from '@/test/fixtures'
import { fakeServices, resetStores, STATIC_FILES } from '@/test/render'
import { WorkspaceProvider } from '../WorkspaceContext'
import { DocsTab } from './DocsTab'

test('M9: a recorded design without a brief or export events lists its documents from the static snapshot', async () => {
  resetStores()
  const b = { ...fixtureBundle(), brief: null, events: [], runs: [], steps: [] }
  const snap = structuredClone(STATIC_FILES['/demo/integrations.json']) as { documents: unknown[] }
  snap.documents.push({ id: 'doc-2', project_id: 'hall-a', name: 'calc-report.pdf', kind: 'calc_report', url: '/demo/files/hall-a/calc-report.pdf', updated_at: 1 })
  const services = fakeServices({ getJson: vi.fn(async (url: string) => (url === '/demo/integrations.json' ? snap : Promise.reject(new Error('404')))) })
  render(
    <ServicesProvider services={services}>
      <TooltipProvider>
        <WorkspaceProvider bundle={b} source="static">
          <DocsTab />
        </WorkspaceProvider>
      </TooltipProvider>
    </ServicesProvider>,
  )
  const inputs = screen.getByRole('region', { name: 'Inputs' })
  expect(await within(inputs).findByRole('button', { name: /tender-hall-a\.pdf/ })).toBeInTheDocument()
  const exports = screen.getByRole('region', { name: 'Exports' })
  expect(await within(exports).findByRole('link', { name: /calc-report\.pdf/ })).toHaveAttribute('href', '/demo/files/hall-a/calc-report.pdf')
  expect(screen.queryByText(/publishes the calc report and BOQ before the review gate/)).not.toBeInTheDocument()
})
