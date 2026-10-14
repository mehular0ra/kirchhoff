import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useEffect } from 'react'
import { TooltipProvider } from '@/components/ui/tooltip'
import { ServicesProvider } from '@/services/services'
import { useUi } from '@/store/ui'
import { fixtureBundle } from '@/test/fixtures'
import { fakeApi, fakeServices, resetStores } from '@/test/render'
import { WorkspaceProvider } from '../WorkspaceContext'
import { bboxToCss } from './bbox'
import { fmtKeyValue } from '@/lib/format'
import { FindingDrawer, readFix } from './FindingDrawer'
import PdfViewer from './PdfViewer'

vi.mock('react-pdf', () => ({
  pdfjs: { GlobalWorkerOptions: {} },
  Document: ({ children, file }: { children: React.ReactNode; file: string }) => (
    <div data-testid="pdf-doc" data-file={file}>
      {children}
    </div>
  ),
  Page: ({ pageNumber, onRenderSuccess }: { pageNumber: number; onRenderSuccess?: () => void }) => {
    useEffect(() => onRenderSuccess?.(), [onRenderSuccess])
    return <div data-testid="pdf-page">page {pageNumber}</div>
  },
}))

function renderDrawer(services = fakeServices()) {
  resetStores()
  return render(
    <ServicesProvider services={services}>
      <TooltipProvider>
        <WorkspaceProvider bundle={fixtureBundle()} source="static">
          <FindingDrawer />
          <PdfViewer />
        </WorkspaceProvider>
      </TooltipProvider>
    </ServicesProvider>,
  )
}

test('bbox converts pdfplumber points to CSS pixels at the render scale', () => {
  expect(bboxToCss([72, 310.5, 290.2, 324], 2, 0)).toEqual({ left: 144, top: 621, width: 436.4, height: 27 })
  expect(bboxToCss(null, 2)).toBeNull()
})

test('fix dicts are read into label, reason and deltas', () => {
  const f = fixtureBundle().findings.r1[0]
  expect(readFix(f.fix)).toEqual({
    label: 'Parallel cable feeder',
    reason: 'Largest ΔV margin for a similar cost',
    deltas: [
      ['dv_pct', 0.84],
      ['cost_delta', 18000],
    ],
  })
})

test('I3: a real WS4 fix with a top-level cost_delta shows the cost first, then the labelled deltas', () => {
  // r1 R05:FA-01 in public/demo/projects/hall-a.json (cost_delta sits beside `deltas`, not inside it).
  const fix = readFix({
    candidate: 'FA-01:cable-CBL-240-8P',
    label: 'Replace FA-01 with a parallel cable feeder',
    reason: 'Power chose this fix: largest voltage-drop margin per dollar.',
    cost_delta: 15580.0,
    deltas: { dv_pct: 0.8362, dv_limit_pct: 2.0, rating_a: 2500.0 },
  })!
  expect(fix.deltas.map(([k, v]) => fmtKeyValue(k, v))).toEqual(['Cost Δ +$15,580', 'ΔV 0.84%', 'ΔV limit 2%', 'Rating 2,500 A'])
  const rejected = readFix({ candidate: 'H-Z2:reroute', label: 'Reroute H-Z2 clear of FB-03', cost_delta: -910.0, deltas: { crossings: 0.0, added_pipe_m: -4.0, changed_pipes: 2.0, index_dp_kpa: 65.51 } })!
  expect(rejected.deltas.map(([k, v]) => fmtKeyValue(k, v))).toEqual(['Cost Δ -$910', 'Crossings 0', 'Added pipe -4 m', 'Changed pipes 2', 'Index-circuit Δp 65.51 kPa'])
})

test('drawer fills placeholders and shows formula, value vs limit and both fixes', () => {
  renderDrawer()
  act(() => {
    useUi.getState().setViewRev('r1')
    useUi.getState().openFinding('R05:FA-01')
  })
  const dlg = screen.getByRole('dialog')
  expect(within(dlg).getByText('FA-01 drops 2.16% at failover current, above the 2% limit of §4.6.')).toBeInTheDocument()
  expect(within(dlg).getByText('ΔU% = 100·√3·I·L·(R cosφ + X sinφ)/U')).toBeInTheDocument()
  expect(within(dlg).getByText('1,546 A')).toBeInTheDocument() // M15: inputs carry their unit
  expect(within(dlg).getByRole('img', { name: 'Value 2.16% against limit 2%: Fail' })).toBeInTheDocument()
  expect(within(dlg).getByText('Chosen fix')).toBeInTheDocument()
  expect(within(dlg).getByText('Rejected alternative')).toBeInTheDocument()
  expect(within(dlg).getByText('ΔV 1.66%')).toBeInTheDocument()
  expect(within(dlg).getByText('IEC 60364-5-52 §525')).toBeInTheDocument()
})

test('tender chip opens the PDF at the cited page with a highlight box', async () => {
  const user = userEvent.setup()
  renderDrawer()
  act(() => {
    useUi.getState().setViewRev('r1')
    useUi.getState().openFinding('R05:FA-01')
  })
  await user.click(screen.getByRole('button', { name: 'Open tender §4.6 · p.4' }))
  expect(await screen.findByText('page 4')).toBeInTheDocument()
  expect(screen.getByTestId('pdf-doc')).toHaveAttribute('data-file', '/demo/docs/tender-hall-a.pdf')
  expect(screen.getByTestId('citation-highlight')).toHaveStyle({ left: '91.6px' })
  expect(screen.getByText('Verified quote: “shall not exceed 2.0%”')).toBeInTheDocument()
})

test('ask-why falls back to the engine explanation when the API is down', async () => {
  const user = userEvent.setup()
  renderDrawer(fakeServices({ api: fakeApi() }))
  act(() => {
    useUi.getState().setViewRev('r1')
    useUi.getState().openFinding('R05:FA-01')
  })
  await user.click(screen.getByRole('button', { name: /ask the co-pilot why/i }))
  expect(await screen.findByText(/Co-pilot is unavailable/)).toBeInTheDocument()
})
