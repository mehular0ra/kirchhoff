import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useEffect } from 'react'
import { TooltipProvider } from '@/components/ui/tooltip'
import { ServicesProvider } from '@/services/services'
import { useLayout } from '@/store/layout'
import { useUi } from '@/store/ui'
import { normalizeBundle, type Bundle, type ProjectBundle } from '@/lib/types'
import { fixtureBundle } from '@/test/fixtures'
import hallASigned from '@/test/fixtures/hall-a-signed.json'
// The golden capture (Jayadratha's PR #43): what the video and the screenshots are shot on.
import hallACaptured from '../../../public/demo/projects/hall-a.json'
import { fakeApi, fakeServices, resetStores } from '@/test/render'
import { WorkspaceProvider } from '../WorkspaceContext'
import { bboxToCss } from './bbox'
import { fmtKeyValue } from '@/lib/format'
import { FindingDrawer } from './FindingDrawer'
import { readFix } from './fixView'
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

function renderDrawer(services = fakeServices(), bundle: Bundle = fixtureBundle()) {
  resetStores()
  return render(
    <ServicesProvider services={services}>
      <TooltipProvider>
        <WorkspaceProvider bundle={bundle} source="static">
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

test('fix dicts are read into label, reason, deltas (cost first) and the one-line headline', () => {
  const f = fixtureBundle().findings.r1[0]
  expect(readFix(f.fix, f.rule_id)).toEqual({
    label: 'Parallel cable feeder',
    reason: 'Largest ΔV margin for a similar cost',
    deltas: [
      ['cost_delta', 18000],
      ['dv_pct', 0.84],
    ],
    headline: [
      ['cost_delta', 18000],
      ['dv_pct', 0.84],
    ],
  })
})

test('I3: a provisional WS4 fix with a top-level cost_delta shows the cost first, then the labelled deltas', () => {
  const fix = readFix(
    {
      candidate: 'FA-01:cable-CBL-240-8P',
      label: 'Replace FA-01 with a parallel cable feeder',
      reason: 'Power chose this fix: largest voltage-drop margin per dollar.',
      cost_delta: 15580.0,
      deltas: { dv_pct: 0.8362, dv_limit_pct: 2.0, rating_a: 2500.0 },
    },
    'R05',
  )!
  expect(fix.deltas.map(([k, v]) => fmtKeyValue(k, v))).toEqual(['Cost Δ +$15,580', 'ΔV 0.84%', 'ΔV limit 2%', 'Rating 2,500 A'])
  const rejected = readFix({ candidate: 'H-Z2:reroute', label: 'Reroute H-Z2 clear of FB-03', cost_delta: -910.0, deltas: { crossings: 0.0, added_pipe_m: -4.0, changed_pipes: 2.0, index_dp_kpa: 65.51 } }, 'R11')!
  expect(rejected.deltas.map(([k, v]) => fmtKeyValue(k, v))).toEqual(['Cost Δ -$910', '0 crossings', 'Added pipe -4 m', '2 changed pipes', 'Index-circuit Δp 65.51 kPa'])
})

const captured = () => normalizeBundle(structuredClone(hallACaptured) as unknown as ProjectBundle)
/** The resulting metric each captured rule's fix is judged on (engine/fixes.py `_metrics`). */
const PRIMARY: Record<string, string> = { R05: 'dv_pct', R11: 'crossings' }

test('golden capture: every r1 fix record orders by key, cost then the resulting metric then its limit, values unchanged', () => {
  const records = captured().findings.r1.flatMap((f) => [f.fix, f.rejected_fix].filter(Boolean).map((rec) => ({ f, rec: rec! })))
  expect(new Set(records.map(({ f }) => f.rule_id))).toEqual(new Set(['R05', 'R11']))
  for (const { f, rec } of records) {
    const view = readFix(rec, f.rule_id)!
    const recorded = { ...(typeof rec.cost_delta === 'number' ? { cost_delta: rec.cost_delta } : {}), ...(rec.deltas as Record<string, unknown>) }
    expect(Object.fromEntries(view.deltas)).toEqual(recorded) // nothing dropped, added or changed
    expect(view.deltas).toHaveLength(Object.keys(recorded).length)
    const keys = view.deltas.map(([k]) => k)
    expect(keys.slice(0, 2)).toEqual(['cost_delta', PRIMARY[f.rule_id]])
    expect(view.headline).toEqual(view.deltas.slice(0, 2))
    keys.forEach((k, i) => k.includes('limit') && expect(keys[i - 1]).not.toMatch(/limit|cost/)) // a limit follows its result
    expect(view.label).not.toMatch(/\b[a-z]+_[a-z_]+\b/) // tier tokens read as words
  }
})

test.each(['R05:FA-01', 'R11:H-Z2'])('golden capture: the r1 %s drawer lists the cost, then the resulting metric', (id) => {
  const bundle = captured()
  const f = bundle.findings.r1.find((x) => x.id === id)!
  renderDrawer(fakeServices(), bundle)
  act(() => {
    useUi.getState().setViewRev('r1')
    useUi.getState().openFinding(id)
  })
  const card = screen.getByText('Chosen fix').parentElement!
  const items = within(card).getAllByRole('listitem').map((li) => li.textContent)
  const deltas = f.fix!.deltas as Record<string, number>
  const primary = PRIMARY[f.rule_id]
  expect(items.slice(0, 2)).toEqual([fmtKeyValue('cost_delta', deltas.cost_delta ?? (f.fix!.cost_delta as number)), fmtKeyValue(primary, deltas[primary])])
  expect(items).toHaveLength(Object.keys(deltas).length)
  for (const text of [...items, within(card).getByText(/^(Replace|Drop) /).textContent ?? '']) expect(text).not.toMatch(/\b[a-z]+_[a-z_]+\b/)
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
  // Reassurance, not an error (the engine explanation above is still complete): role="status", not "alert".
  const note = await screen.findByRole('status')
  expect(note).toHaveTextContent(/Co-pilot is unavailable/)
  // M1: status is icon + text, never colour alone.
  expect(note.querySelector('svg')).toBeTruthy()
})

test('I5: Show on canvas from the Matrix switches to the 3D hall, focuses the element and closes the drawer', async () => {
  const user = userEvent.setup()
  renderDrawer()
  act(() => {
    useUi.getState().setTab('matrix')
    useUi.getState().setViewRev('r1')
    useUi.getState().openFinding('R05:FA-01')
  })
  await user.click(screen.getByRole('button', { name: /show on canvas/i }))
  expect(useUi.getState()).toMatchObject({ tab: 'hall', focusId: 'FA-01', findingId: null })
})

test('I11: a document opened without a quote never claims a verified quote', () => {
  renderDrawer()
  act(() => useUi.getState().openCitation({ doc_id: 'tender-hall-a', page: 1, quote: '', bbox: null, clause: null }))
  const dlg = screen.getByRole('dialog')
  expect(within(dlg).queryByText(/Verified quote/)).not.toBeInTheDocument()
  expect(within(dlg).getByText('Tender PDF · page 1')).toBeInTheDocument()
})

test('residual: the drawing opens titled "Drawing", not "Tender"', () => {
  renderDrawer()
  act(() => useUi.getState().openCitation({ doc_id: 'hall-a-plan', page: 1, quote: '', bbox: null, clause: null }, 'drawing'))
  const dlg = screen.getByRole('dialog', { name: 'Drawing · page 1' })
  expect(within(dlg).getByText('Drawing PDF · page 1')).toBeInTheDocument()
  expect(within(dlg).queryByText(/Tender/)).not.toBeInTheDocument()
  // without a hint, a plan/drawing doc id is still read as a drawing; a tender clause keeps its title
  act(() => useUi.getState().openCitation({ doc_id: 'hall-a-plan', page: 2, quote: '', bbox: null, clause: null }))
  expect(screen.getByRole('dialog', { name: 'Drawing · page 2' })).toBeInTheDocument()
  act(() => useUi.getState().openCitation({ doc_id: 'tender-hall-a', page: 4, quote: 'shall not exceed 2.0%', bbox: null, clause: '§4.6' }))
  expect(screen.getByRole('dialog', { name: 'Tender §4.6 · page 4' })).toBeInTheDocument()
})

test('D9: a count rule shows "1 crossing (limit 0)" in place of a bar; the formula wraps; tiers read as words', async () => {
  const b = normalizeBundle(structuredClone(hallASigned) as unknown as ProjectBundle)
  resetStores()
  act(() => {
    useUi.getState().setViewRev('r1')
    useUi.getState().openFinding('R11:H-Z2')
  })
  render(
    <ServicesProvider services={fakeServices()}>
      <TooltipProvider>
        <WorkspaceProvider bundle={b} source="static">
          <FindingDrawer />
        </WorkspaceProvider>
      </TooltipProvider>
    </ServicesProvider>,
  )
  const drawer = await screen.findByRole('dialog')
  expect(within(drawer).queryByRole('img', { name: /against limit/ })).not.toBeInTheDocument()
  expect(within(drawer).getByText((_, el) => el?.tagName === 'P' && /Fail · 1 crossing \(limit 0\)/.test(el.textContent ?? ''))).toBeInTheDocument()
  expect(within(drawer).getByText('Drop H-Z2 to the low pipe tier where it crosses FB-03')).toBeInTheDocument()
  expect(within(drawer).getByText('28 m')).toBeInTheDocument()
  expect(within(drawer).getByRole('region', { name: 'Formula' }).querySelector('pre')).toHaveClass('whitespace-pre-wrap')
})

test('residual: a finding without clause or tender refs renders no stray "0"; an empty list input reads "none"', async () => {
  const b = normalizeBundle(structuredClone(hallASigned) as unknown as ProjectBundle)
  resetStores()
  act(() => useUi.getState().openFinding('R12:BOQ'))
  render(
    <ServicesProvider services={fakeServices()}>
      <TooltipProvider>
        <WorkspaceProvider bundle={b} source="static">
          <FindingDrawer />
        </WorkspaceProvider>
      </TooltipProvider>
    </ServicesProvider>,
  )
  const drawer = await screen.findByRole('dialog')
  // the stray "0" was a bare text node directly inside the drawer body (the count row's "0" sits in a <span>)
  const walker = document.createTreeWalker(drawer, NodeFilter.SHOW_TEXT)
  const bare: string[] = []
  for (let n = walker.nextNode(); n; n = walker.nextNode()) if (n.nodeValue === '0' && n.parentElement?.tagName === 'DIV') bare.push(n.nodeValue)
  expect(bare).toEqual([])
  expect(within(drawer).getByText('BOQ is checked as a whole; it is not drawn on the 3D hall or the SLD.')).toBeInTheDocument()
  expect(within(drawer).getByText('none')).toBeInTheDocument()
})

// The drawer must not hide the co-pilot that opened it: on a wide screen it opens beside the co-pilot column (20rem, the
// workspace grid's last column) with no dimming layer, so the conversation, the status and the Stop button stay in view.
describe('beside the co-pilot', () => {
  afterEach(() => vi.restoreAllMocks())

  const media = (wide: boolean) => (query: string) =>
    ({ matches: wide && query.includes('min-width: 1200px'), media: query, onchange: null, addEventListener: () => {}, removeEventListener: () => {}, addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false }) as MediaQueryList

  function renderBesideCoPilot(wide: boolean) {
    vi.spyOn(window, 'matchMedia').mockImplementation(media(wide))
    resetStores()
    const view = render(
      <ServicesProvider services={fakeServices()}>
        <TooltipProvider>
          <WorkspaceProvider bundle={fixtureBundle()} source="static">
            <aside aria-label="Co-pilot">
              <input aria-label="Ask the co-pilot" />
            </aside>
            <button>Somewhere else</button>
            <FindingDrawer />
          </WorkspaceProvider>
        </TooltipProvider>
      </ServicesProvider>,
    )
    act(() => {
      useUi.getState().setViewRev('r1')
      useUi.getState().openFinding('R05:FA-01')
    })
    return view
  }

  beforeEach(() => {
    localStorage.clear()
    useLayout.getState().reset()
  })

  test('on a wide screen it opens beside the co-pilot column, with no dimming layer over the page', () => {
    renderBesideCoPilot(true)
    expect(screen.getByRole('dialog').style.right).toBe('320px') // the co-pilot's usual width
    expect(document.querySelector('[data-slot="sheet-overlay"]')).toBeNull()
  })

  test('it keeps beside the co-pilot however wide the visitor has dragged it', () => {
    useLayout.getState().setCopilotW(480)
    renderBesideCoPilot(true)
    expect(screen.getByRole('dialog').style.right).toBe('480px')
    act(() => useLayout.getState().setCopilotW(400))
    expect(screen.getByRole('dialog').style.right).toBe('400px')
  })

  test('it docks against the co-pilot as drawn, when a small window shows it narrower than saved', () => {
    useLayout.setState({ copilotW: 600, copilotUsed: 350 })
    renderBesideCoPilot(true)
    expect(screen.getByRole('dialog').style.right).toBe('350px')
  })

  test('with the co-pilot hidden it opens at the screen edge, still without dimming the page', () => {
    useLayout.getState().toggleCopilot()
    renderBesideCoPilot(true)
    expect(screen.getByRole('dialog').style.right).toBe('0px')
    expect(document.querySelector('[data-slot="sheet-overlay"]')).toBeNull()
  })

  test('on a wide screen the co-pilot stays usable while the drawer is open', async () => {
    const user = userEvent.setup()
    renderBesideCoPilot(true)
    await user.click(screen.getByRole('textbox', { name: 'Ask the co-pilot' }))
    await user.keyboard('why FA-01')
    expect(screen.getByRole('textbox', { name: 'Ask the co-pilot' })).toHaveValue('why FA-01')
    expect(screen.getByRole('dialog')).toBeInTheDocument() // working in the co-pilot does not close the finding
  })

  test('on a wide screen a click anywhere else on the page still closes the drawer', async () => {
    const user = userEvent.setup()
    renderBesideCoPilot(true)
    await user.click(screen.getByRole('button', { name: 'Somewhere else' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  test('on a narrow screen it is the dimmed overlay over the right edge, as before', () => {
    renderBesideCoPilot(false)
    expect(screen.getByRole('dialog').style.right).toBe('')
    expect(document.querySelector('[data-slot="sheet-overlay"]')).not.toBeNull()
  })
})
