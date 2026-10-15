import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TooltipProvider } from '@/components/ui/tooltip'
import { useChecklist } from '@/onboarding/checklist/checklistStore'
import { ServicesProvider, type LiveVoiceCall, type Services } from '@/services/services'
import { useUi } from '@/store/ui'
import { normalizeBundle, type Bundle, type ProjectBundle } from '@/lib/types'
import { fixtureBundle } from '@/test/fixtures'
import hallASigned from '@/test/fixtures/hall-a-signed.json'
import { fakeServices, resetStores } from '@/test/render'
import { WorkspaceProvider } from '../WorkspaceContext'
import { CoPilotPanel } from './CoPilotPanel'
import { parseIntent } from './intent'

function renderPanel(services: Services = fakeServices(), bundle: Bundle = fixtureBundle()) {
  resetStores()
  useChecklist.getState().reload()
  return render(
    <ServicesProvider services={services}>
      <TooltipProvider>
        <WorkspaceProvider bundle={bundle} source="static">
          <CoPilotPanel />
        </WorkspaceProvider>
      </TooltipProvider>
    </ServicesProvider>,
  )
}

test('typed intents map onto the three co-pilot tools', () => {
  expect(parseIntent('What if racks go to 200 kW?')).toEqual({ tool: 'what_if', param: 'rack_kw', value: 200 })
  expect(parseIntent('what if the ΔV limit is 1.5%')).toEqual({ tool: 'what_if', param: 'dv_limit_pct', value: 1.5 })
  expect(parseIntent('what if liquid fraction 0.9')).toEqual({ tool: 'what_if', param: 'liquid_fraction', value: 0.9 })
  expect(parseIntent('why R05 FA-01?')).toEqual({ tool: 'explain_finding', element: 'FA-01', rule: 'R05' })
  expect(parseIntent('show h-z2')).toEqual({ tool: 'focus_element', element: 'H-Z2' })
  expect(parseIntent('hello')).toBeNull()
})

test('typed what-if answers with an engine-built summary and lights the chain', async () => {
  const user = userEvent.setup()
  renderPanel()
  await user.type(screen.getByRole('textbox', { name: 'Ask the co-pilot' }), 'what if racks go to 200 kW{Enter}')
  const convo = await screen.findByRole('list', { name: 'Conversation' })
  expect(
    await within(convo).findByText(/3 checks fail: R01 T-A1 114% vs 100%; R02 A-01 2,343 A vs 1,600 A; R08 CDU-1 2.56 MW vs 2.4 MW/),
  ).toBeInTheDocument()
  expect(useUi.getState().whatIf?.origin).toBe('precomputed')
  expect(useChecklist.getState().done.ask_copilot).toBe(true)
})

test('typed focus and unknown questions', async () => {
  const user = userEvent.setup()
  renderPanel()
  const box = screen.getByRole('textbox', { name: 'Ask the co-pilot' })
  await user.type(box, 'show H-Z2{Enter}')
  expect(useUi.getState().focusId).toBe('H-Z2')
  await user.type(box, 'hello{Enter}')
  expect(await screen.findByText(/Try: “what if racks go to 200 kW”/)).toBeInTheDocument()
})

test('Gemini Live tool calls run in the browser and return engine data', async () => {
  const user = userEvent.setup()
  let handler: ((c: LiveVoiceCall) => Promise<Record<string, unknown>>) | null = null
  const stop = vi.fn(async () => undefined)
  renderPanel(
    fakeServices({
      startLiveVoice: async ({ onToolCall }) => {
        handler = onToolCall
        return { stop }
      },
    }),
  )
  await user.click(screen.getByRole('button', { name: 'Start voice' }))
  expect(await screen.findByText('Listening (Gemini Live)')).toBeInTheDocument()
  let response: Record<string, unknown> = {}
  await act(async () => {
    response = await handler!({ name: 'focus_element', args: { element_id: 'fa-01' } })
  })
  expect(response).toEqual({ element_id: 'FA-01' })
  expect(useUi.getState().focusId).toBe('FA-01')
  expect(screen.getByText('Showing FA-01.')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Stop' }))
  expect(stop).toHaveBeenCalled()
})

test('when Gemini Live fails the panel switches to push-to-talk automatically', async () => {
  const user = userEvent.setup()
  renderPanel(fakeServices({ startLiveVoice: async () => Promise.reject(new Error('app check')) }))
  await user.click(screen.getByRole('button', { name: 'Start voice' }))
  expect(await screen.findByText('Gemini Live could not connect; switched to push-to-talk.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Hold to talk' })).toBeInTheDocument()
})

const realHallA = () => normalizeBundle(structuredClone(hallASigned) as unknown as ProjectBundle)

test('D1: "why did FA-01 fail?" on signed r2 answers from r1, where R05 failed, and opens that finding', async () => {
  const user = userEvent.setup()
  renderPanel(fakeServices(), realHallA())
  expect(useUi.getState().viewRev).toBeNull() // the workspace opens on the latest revision, r2 (all pass)
  await user.type(screen.getByRole('textbox', { name: 'Ask the co-pilot' }), 'why did FA-01 fail?{Enter}')
  const convo = await screen.findByRole('list', { name: 'Conversation' })
  // the engine explanation of r1's R05 failure, filled from the finding record — never r2's passing R02
  const answer = await within(convo).findByText(/^In r1: Voltage drop .* via FA-01 is 2\.16% against a limit of 2%\./)
  expect(answer.textContent).not.toMatch(/2,500 A|1,546/)
  // the chosen fix, from the fix record: label, cost and ΔV
  expect(answer.textContent).toMatch(/Fixed in r2: Replace FA-01 with a parallel cable feeder .*\+\$15,580.*ΔV 0\.84%/)
  expect(useUi.getState().viewRev).toBe('r1')
  expect(useUi.getState().findingId).toBe('R05:FA-01')
})

test('D1: a Gemini Live explain_finding call with r2\'s passing finding id also walks back to r1', async () => {
  const user = userEvent.setup()
  let handler: ((c: LiveVoiceCall) => Promise<Record<string, unknown>>) | null = null
  renderPanel(
    fakeServices({
      startLiveVoice: async ({ onToolCall }) => {
        handler = onToolCall
        return { stop: async () => undefined }
      },
    }),
    realHallA(),
  )
  await user.click(screen.getByRole('button', { name: 'Start voice' }))
  await screen.findByText('Listening (Gemini Live)')
  let response: Record<string, unknown> = {}
  await act(async () => {
    response = await handler!({ name: 'explain_finding', args: { finding_id: 'R11:H-Z2' } })
  })
  expect(response).toMatchObject({ finding_id: 'R11:H-Z2', revision: 'r1', status: 'fail', value: 1, limit: 0 })
  expect(useUi.getState().viewRev).toBe('r1')
  expect(useUi.getState().findingId).toBe('R11:H-Z2')
})

test('D1: on the revision that fails, "why" answers there without switching or a prefix', async () => {
  const user = userEvent.setup()
  renderPanel(fakeServices(), realHallA())
  act(() => useUi.getState().setViewRev('r1'))
  await user.type(screen.getByRole('textbox', { name: 'Ask the co-pilot' }), 'why R11 H-Z2{Enter}')
  const convo = await screen.findByRole('list', { name: 'Conversation' })
  expect(await within(convo).findByText(/^H-Z2 runs above electrical run FB-03 on a higher tier\./)).toBeInTheDocument()
  expect(useUi.getState().viewRev).toBe('r1')
  expect(useUi.getState().findingId).toBe('R11:H-Z2')
})

test('D1: an element that never failed keeps the current revision\'s answer', async () => {
  const user = userEvent.setup()
  renderPanel(fakeServices(), realHallA())
  await user.type(screen.getByRole('textbox', { name: 'Ask the co-pilot' }), 'why FA-02{Enter}')
  const convo = await screen.findByRole('list', { name: 'Conversation' })
  const items = await within(convo).findAllByRole('listitem')
  expect(items).toHaveLength(2)
  expect(items[1].textContent).toMatch(/^Co-pilot: .*FA-02/)
  expect(items[1].textContent).not.toMatch(/In r1/)
  expect(useUi.getState().viewRev).toBeNull()
})

test('residual: "show BOQ" says the element is not drawn on a canvas and keeps the view', async () => {
  const user = userEvent.setup()
  renderPanel(fakeServices(), realHallA())
  act(() => useUi.getState().setTab('matrix'))
  await user.type(screen.getByRole('textbox', { name: 'Ask the co-pilot' }), 'show BOQ{Enter}')
  const convo = await screen.findByRole('list', { name: 'Conversation' })
  expect(await within(convo).findByText(/BOQ is not drawn on the 3D hall or the SLD/)).toBeInTheDocument()
  expect(useUi.getState().tab).toBe('matrix')
})
