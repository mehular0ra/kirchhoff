import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { TooltipProvider } from '@/components/ui/tooltip'
import { useChecklist } from '@/onboarding/checklist/checklistStore'
import { ApiError, describeApiError, type VoiceResponse } from '@/services/apiClient'
import { clearDebugLog, debugEntries } from '@/lib/debugLog'
import { ServicesProvider, type LiveTurnRecord, type LiveVoiceCall, type LiveVoiceEvent, type Services } from '@/services/services'
import { useConversation } from '@/store/conversation'
import { useUi } from '@/store/ui'
import { normalizeBundle, type Bundle, type ProjectBundle, type WhatIfResult } from '@/lib/types'
import { fixtureBundle } from '@/test/fixtures'
import hallASigned from '@/test/fixtures/hall-a-signed.json'
import { fillPlaceholders, fmtNum, fmtUsd, tidyTokens } from '@/lib/format'
// The golden capture (Jayadratha's PR #43): what the video and the screenshots are shot on.
import hallACaptured from '../../../public/demo/projects/hall-a.json'
import { fakeApi, fakeServices, resetStores } from '@/test/render'
import { RevisionTimeline } from '../RevisionTimeline'
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
  // Gemini gets the engine's record of the element, not just its id, so it can answer questions about it.
  expect(response).toMatchObject({ element_id: 'FA-01', drawn: true })
  expect(String(response.text)).toMatch(/^(Cable|Busway) FA-01: /)
  expect(useUi.getState().focusId).toBe('FA-01')
  expect(screen.getByText(/^(Cable|Busway) FA-01: /)).toBeInTheDocument()
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

const capturedHallA = () => normalizeBundle(structuredClone(hallACaptured) as unknown as ProjectBundle)

test.each([
  // R05: the cost, then the RESULTING voltage drop; the record stores `dv_limit_pct` first, and it is not the result
  ['FA-01', (d: Record<string, number>) => `ΔV ${fmtNum(d.dv_pct)}%`],
  // R11: the cost, then the crossings left, read as a count
  ['H-Z2', (d: Record<string, number>) => `${fmtNum(d.crossings)} ${d.crossings === 1 ? 'crossing' : 'crossings'}`],
])('D1 on the golden capture: "why did %s fail?" cites r1 and the fix by cost and resulting metric', async (element, metric) => {
  const user = userEvent.setup()
  const bundle = capturedHallA()
  const failed = bundle.findings.r1.find((f) => f.element_id === element && f.status === 'fail')!
  const fix = failed.fix!
  const deltas = fix.deltas as Record<string, number>
  renderPanel(fakeServices(), bundle)
  await user.type(screen.getByRole('textbox', { name: 'Ask the co-pilot' }), `why did ${element} fail?{Enter}`)
  const convo = await screen.findByRole('list', { name: 'Conversation' })
  const answer = await within(convo).findByText(/^In r1: /)
  const cost = fmtUsd(deltas.cost_delta ?? (fix.cost_delta as number), true)
  const label = tidyTokens(String(fix.label))
  // (the bubble carries a visually hidden "Co-pilot: " speaker label before the answer)
  expect(answer.textContent!.replace(/^Co-pilot: /, '')).toBe(`In r1: ${fillPlaceholders(failed.explanation || failed.title, failed)} Fixed in r2: ${label} · Cost Δ ${cost} · ${metric(deltas)}.`)
  expect(answer.textContent).not.toMatch(/\b[a-z]+_[a-z_]+\b/) // no raw tier token or snake_case key
  expect(useUi.getState().findingId).toBe(failed.id)
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

/** Push-to-talk: Live fails, the panel switches to "Hold to talk", and one press-and-release posts the clip. */
async function pushToTalk(res: VoiceResponse | (() => Promise<VoiceResponse>)) {
  const user = userEvent.setup()
  const voice = vi.fn(typeof res === 'function' ? res : async () => res)
  renderPanel(fakeServices({ api: fakeApi({ voice }), startLiveVoice: async () => Promise.reject(new Error('blocked')) }), realHallA())
  await user.click(screen.getByRole('button', { name: 'Start voice' }))
  const hold = await screen.findByRole('button', { name: 'Hold to talk' })
  fireEvent.keyDown(hold, { key: ' ' })
  await screen.findByRole('button', { name: 'Release to send' })
  fireEvent.keyUp(screen.getByRole('button', { name: 'Release to send' }), { key: ' ' })
  await waitFor(() => expect(voice).toHaveBeenCalled())
}

const conversation = async () => within(await screen.findByRole('list', { name: 'Conversation' }))

test('D1 in push-to-talk: an explain_finding result citing r1 switches to r1, then opens the finding there', async () => {
  const answer = 'In r1: Voltage drop from the UPS output board to the furthest tap-off via FA-01 is 2.16% against a limit of 2%.'
  await pushToTalk({
    transcript: 'Why did FA-01 fail?',
    answer,
    tool_results: [{ name: 'explain_finding', args: { finding_id: 'R05:FA-01' }, result: { text: answer, revision: 'r1' } }],
  })
  expect(await (await conversation()).findByText(answer)).toBeInTheDocument()
  expect(useUi.getState().viewRev).toBe('r1') // screen and voice agree: the drawer shows r1's failing R05 · FA-01
  expect(useUi.getState().findingId).toBe('R05:FA-01')
})

test('push-to-talk without a cited revision (or with one the bundle does not have) keeps the revision on screen', async () => {
  await pushToTalk({
    transcript: 'Why is FA-02 fine?',
    answer: 'FA-02 carries 1,546 A.',
    tool_results: [
      { name: 'explain_finding', args: { finding_id: 'R02:FA-02' }, result: { text: 'FA-02 carries 1,546 A.' } },
      { name: 'explain_finding', args: { finding_id: 'R05:FA-01' }, result: { text: 'x', revision: 'r9' } },
    ],
  })
  expect(await (await conversation()).findByText('FA-02 carries 1,546 A.')).toBeInTheDocument()
  expect(useUi.getState().viewRev).toBeNull()
  expect(useUi.getState().findingId).toBe('R05:FA-01')
})

test('push-to-talk: a transient model error (503 voice_unavailable) says to try again, with an icon beside the text', async () => {
  await pushToTalk(async () => Promise.reject(new ApiError(503, 'voice_unavailable')))
  const note = await screen.findByText(describeApiError(new ApiError(503, 'voice_unavailable')))
  expect(note.querySelector('svg')).not.toBeNull() // status is icon plus text, never text or colour alone
  expect(screen.queryByText(/voice service is unreachable/)).not.toBeInTheDocument()
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
  const [card, ...others] = (await within(convo).findAllByRole('listitem')).filter((li) => li.hasAttribute('data-turn'))
  expect(others).toHaveLength(0) // one question, one card
  await waitFor(() => expect(card.textContent).toMatch(/Explain finding R\d+ · FA-02/))
  expect(card.textContent).not.toMatch(/In r1/)
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

test('N1: paraphrased "why" questions that name an element and a problem route to the explain tool', () => {
  expect(parseIntent('What caused FA-01 to fail?')).toEqual({ tool: 'explain_finding', element: 'FA-01', rule: undefined })
  expect(parseIntent('what is wrong with H-Z2')).toEqual({ tool: 'explain_finding', element: 'H-Z2', rule: undefined })
  expect(parseIntent('Is FA-01 failing?')).toEqual({ tool: 'explain_finding', element: 'FA-01', rule: undefined })
  expect(parseIntent('any issue on R05 FA-01?')).toEqual({ tool: 'explain_finding', element: 'FA-01', rule: 'R05' })
  expect(parseIntent('Tell me about the problem with h-z2')).toEqual({ tool: 'explain_finding', element: 'H-Z2', rule: undefined })
  expect(parseIntent('What is the cause of the H-Z2 failure')).toEqual({ tool: 'explain_finding', element: 'H-Z2', rule: undefined })
  // a problem word without an element, or an element without one, does not guess
  expect(parseIntent('what failed?')).toBeNull()
  // asking about an element with no problem word asks what it is (its details)
  expect(parseIntent('tell me about FA-01')).toEqual({ tool: 'focus_element', element: 'FA-01' })
  // existing routes are unchanged
  expect(parseIntent('show H-Z2')).toEqual({ tool: 'focus_element', element: 'H-Z2' })
  expect(parseIntent('what if racks go to 200 kW')).toEqual({ tool: 'what_if', param: 'rack_kw', value: 200 })
})

test('N1: "What caused FA-01 to fail?" answers from r1 like "why FA-01", instead of the help line', async () => {
  const user = userEvent.setup()
  renderPanel(fakeServices(), realHallA())
  await user.type(screen.getByRole('textbox', { name: 'Ask the co-pilot' }), 'What caused FA-01 to fail?{Enter}')
  const convo = await screen.findByRole('list', { name: 'Conversation' })
  expect(await within(convo).findByText(/^In r1: Voltage drop .* via FA-01 is 2\.16% against a limit of 2%\./)).toBeInTheDocument()
  expect(within(convo).queryByText(/^Try:/)).not.toBeInTheDocument()
  expect(useUi.getState().findingId).toBe('R05:FA-01')
})

test('N1: the input shows both kinds of question in full — a short placeholder plus a visible hint it is described by', () => {
  renderPanel()
  const box = screen.getByRole('textbox', { name: 'Ask the co-pilot' })
  // the full examples (273 px at 12 px) cannot fit the ~200 px input, so they sit on their own line under it
  expect(box).toHaveAttribute('placeholder', 'Ask why, or “what if…”')
  expect(box).toHaveAccessibleDescription('Try “why FA-01” or “what if racks go to 200 kW”')
  expect(screen.getByText('Try “why FA-01” or “what if racks go to 200 kW”')).toBeVisible()
})

// #37: what-ifs (typed, chip, voice) run on the head revision unless the visitor picked one in the revision bar;
// D1's automatic switch to r1 is not a pick. The answer names the revision it ran on, from the bundle's id and status.

/** The co-pilot with the revision bar under it, as in the workspace, on the real Hall A bundle. */
function renderWithRevisionBar(services: Services) {
  resetStores()
  useChecklist.getState().reload()
  return render(
    <ServicesProvider services={services}>
      <TooltipProvider>
        <MemoryRouter>
          <WorkspaceProvider bundle={realHallA()} source="static">
            <CoPilotPanel />
            <RevisionTimeline />
          </WorkspaceProvider>
        </MemoryRouter>
      </TooltipProvider>
    </ServicesProvider>,
  )
}

/** The head revision and its precomputed 200 kW what-if, as the bundle carries them (60 checks fail on today's Hall A). */
function headWhatIf200() {
  const b = realHallA()
  const head = b.revisions[b.revisions.length - 1]
  const result = b.what_ifs.find((w) => w.revision_ref === `seed:hall-a@${head.id}` && w.param === 'rack_kw' && w.value === 200)!
  return { head, result, fails: result.findings.filter((f) => f.status === 'fail').length }
}

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const ask = async (user: ReturnType<typeof userEvent.setup>, q: string) =>
  user.type(screen.getByRole('textbox', { name: 'Ask the co-pilot' }), `${q}{Enter}`)

async function holdToTalk(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: 'Start voice' }))
  const hold = await screen.findByRole('button', { name: 'Hold to talk' })
  fireEvent.keyDown(hold, { key: ' ' })
  await screen.findByRole('button', { name: 'Release to send' })
  fireEvent.keyUp(screen.getByRole('button', { name: 'Release to send' }), { key: ' ' })
}

test('#37: after "why FA-01" moves the view to r1, a typed 200 kW what-if runs on the head revision and names it', async () => {
  const user = userEvent.setup()
  const whatIf = vi.fn(async (): Promise<WhatIfResult> => Promise.reject(new Error('the head revision is precomputed')))
  renderPanel(fakeServices({ api: fakeApi({ whatIf }) }), realHallA())
  await ask(user, 'Why did FA-01 fail?')
  await (await conversation()).findByText(/^In r1: /)
  expect(useUi.getState().viewRev).toBe('r1') // D1's automatic switch
  await ask(user, 'What if racks go to 200 kW?')
  const { head, fails } = headWhatIf200()
  expect(head.status).toBe('signed')
  const answer = await (await conversation()).findByText(new RegExp(`^On ${escape(head.id)} \\(${head.status}\\): ${fails} checks fail: `))
  expect(answer.textContent).toMatch(/^On r2 \(signed\): /)
  expect(whatIf).not.toHaveBeenCalled() // the head revision's seed what-if, from the bundle
  expect(useUi.getState().whatIf).toMatchObject({ origin: 'precomputed', result: { revision_ref: `seed:hall-a@${head.id}` } })
  expect(useUi.getState().viewRev).toBeNull() // the overlay is drawn on the revision it was computed for: back on the head
})

test('#37: a revision-bar pick of r1 runs the typed what-if on r1, with the engine\'s r1 count, and names r1', async () => {
  const user = userEvent.setup()
  const { result: headResult } = headWhatIf200()
  // r1 has no seed what-if, so the engine answers; this fake engine's r1 answer is a different count from the head's.
  const r1Result: WhatIfResult = { ...headResult, revision_ref: 'seed:hall-a@r1', findings: headResult.findings.slice(0, 7) }
  const whatIf = vi.fn(async () => r1Result)
  renderWithRevisionBar(fakeServices({ api: fakeApi({ whatIf }) }))
  await user.click(screen.getByRole('button', { name: /^r1\b/ }))
  expect(useUi.getState()).toMatchObject({ viewRev: 'r1', viewRevSource: 'user' })
  await ask(user, 'what if racks go to 200 kW')
  expect(whatIf).toHaveBeenCalledWith('seed:hall-a@r1', 'rack_kw', 200)
  const r1 = realHallA().revisions.find((r) => r.id === 'r1')!
  const n = r1Result.findings.filter((f) => f.status === 'fail').length
  expect(await (await conversation()).findByText(new RegExp(`^On r1 \\(${r1.status}\\): ${n} checks fail: `))).toBeInTheDocument()
  expect(useUi.getState().viewRev).toBe('r1')
})

test('#37: "why FA-01" after a revision-bar pick of r1 keeps the pick, so the what-if still runs on r1', async () => {
  const user = userEvent.setup()
  const { result: headResult } = headWhatIf200()
  const whatIf = vi.fn(async () => ({ ...headResult, revision_ref: 'seed:hall-a@r1' }))
  renderWithRevisionBar(fakeServices({ api: fakeApi({ whatIf }) }))
  await user.click(screen.getByRole('button', { name: /^r1\b/ }))
  await ask(user, 'why did FA-01 fail?') // fails on r1 itself: no switch
  await (await conversation()).findByText(/FA-01 is 2\.16% against a limit of 2%/)
  await ask(user, 'what if racks go to 200 kW')
  expect(whatIf).toHaveBeenCalledWith('seed:hall-a@r1', 'rack_kw', 200)
})

test('#37: push-to-talk after the automatic switch to r1 sends the head revision_ref, and the what-if answer names it', async () => {
  const user = userEvent.setup()
  const { head, result } = headWhatIf200()
  const spoken = 'With rack_kw at 200, these checks fail: R01, R02.'
  const voice = vi.fn(
    async (): Promise<VoiceResponse> => ({
      transcript: 'what if racks go to 200 kW',
      answer: spoken,
      tool_results: [{ name: 'what_if', args: { param: 'rack_kw', value: 200 }, result: result as unknown as Record<string, unknown> }],
    }),
  )
  renderPanel(fakeServices({ api: fakeApi({ voice }), startLiveVoice: async () => Promise.reject(new Error('blocked')) }), realHallA())
  await ask(user, 'why did FA-01 fail?')
  await (await conversation()).findByText(/^In r1: /)
  expect(useUi.getState().viewRev).toBe('r1')
  await holdToTalk(user)
  await waitFor(() => expect(voice).toHaveBeenCalled())
  expect(voice).toHaveBeenCalledWith(expect.any(Blob), `seed:hall-a@${head.id}`)
  expect(await (await conversation()).findByText(`On ${head.id} (${head.status}): ${spoken}`)).toBeInTheDocument()
  expect(useUi.getState().viewRev).toBeNull() // the engine result is drawn on the head revision it was computed for
  expect(useUi.getState().whatIf?.origin).toBe('engine')
})

test('#37: push-to-talk after a revision-bar pick of r1 sends r1\'s revision_ref', async () => {
  const user = userEvent.setup()
  const voice = vi.fn(async (): Promise<VoiceResponse> => ({ transcript: 'show FA-01', answer: 'Showing FA-01.', tool_results: [] }))
  renderWithRevisionBar(fakeServices({ api: fakeApi({ voice }), startLiveVoice: async () => Promise.reject(new Error('blocked')) }))
  await user.click(screen.getByRole('button', { name: /^r1\b/ }))
  await holdToTalk(user)
  await waitFor(() => expect(voice).toHaveBeenCalled())
  expect(voice).toHaveBeenCalledWith(expect.any(Blob), 'seed:hall-a@r1')
})

test('#37: a Gemini Live what_if call after the automatic switch runs on the head revision and says so in its data', async () => {
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
  await ask(user, 'why did FA-01 fail?')
  await (await conversation()).findByText(/^In r1: /)
  await user.click(screen.getByRole('button', { name: 'Start voice' }))
  await screen.findByText('Listening (Gemini Live)')
  let response: Record<string, unknown> = {}
  await act(async () => {
    response = await handler!({ name: 'what_if', args: { param: 'rack_kw', value: 200 } })
  })
  const { head, fails } = headWhatIf200()
  expect(response).toMatchObject({ revision: head.id, revision_status: head.status })
  expect((response.failing as unknown[]).length).toBe(fails)
  expect(useUi.getState().viewRev).toBeNull()
})

// ---- The conversation history: what was asked, which engine check answered, what changed, and what Live is doing.

const turnCards = () => screen.queryAllByRole('listitem').filter((li) => li.hasAttribute('data-turn'))

/** A Gemini Live session the test drives by hand: the tool calls and the events the service would send. */
function liveHarness(api = fakeApi()) {
  let onToolCall: (c: LiveVoiceCall) => Promise<Record<string, unknown>> = async () => ({})
  let onEvent: (e: LiveVoiceEvent) => void = () => undefined
  let onDebug: (t: LiveTurnRecord) => void = () => undefined
  const services = fakeServices({
    api,
    startLiveVoice: async (o) => {
      onToolCall = o.onToolCall
      onEvent = o.onEvent ?? onEvent
      onDebug = o.onDebug ?? onDebug
      return { stop: async () => undefined }
    },
  })
  return {
    services,
    call: (c: LiveVoiceCall) => onToolCall(c),
    emit: (e: LiveVoiceEvent) => act(() => onEvent(e)),
    debug: (t: LiveTurnRecord) => act(() => onDebug(t)),
  }
}

async function startLive(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: 'Start voice' }))
  await screen.findByText('Listening (Gemini Live)')
}

test('a typed "why" shows its card: what was asked, the engine check, the answer and what changed on screen', async () => {
  const user = userEvent.setup()
  renderPanel(fakeServices(), realHallA())
  await ask(user, 'why did FA-01 fail?')
  const convo = within(await screen.findByRole('list', { name: 'Conversation' }))
  expect(await convo.findByText('Explain finding R05 · FA-01')).toBeInTheDocument()
  expect(convo.getByText('Engine check')).toBeInTheDocument()
  expect(convo.getByText('You · typed')).toBeInTheDocument()
  expect(convo.getByText('why did FA-01 fail?')).toBeInTheDocument()
  const changes = within(convo.getByRole('list', { name: 'What changed on screen' }))
  expect(changes.getAllByRole('listitem').map((li) => li.textContent)).toEqual([
    expect.stringMatching(/^Switched to r1 \(.*\), where this check failed$/),
    'Opened R05 · FA-01 in the finding drawer',
  ])
})

test('a slow answer stays under its own question and never lands under a later one', async () => {
  const user = userEvent.setup()
  let finish: (v: { text: string }) => void = () => undefined
  const explain = vi.fn(() => new Promise<{ text: string }>((resolve) => (finish = resolve)))
  renderPanel(fakeServices({ api: fakeApi({ explain }) }), realHallA())
  await ask(user, 'why did FA-01 fail?') // waits on the language model's rewrite
  await ask(user, 'show H-Z2') // answers at once
  await within(await screen.findByRole('list', { name: 'Conversation' })).findByText(/^Pipe H-Z2 \(header, DN\d+\) in zone Z2/)
  await act(async () => finish({ text: 'Voltage drop is {value} against {limit}.' }))
  await waitFor(() => expect(turnCards()[0].textContent).toContain('Voltage drop is 2.16% against 2%.'))
  const cards = turnCards()
  expect(cards).toHaveLength(2)
  expect(cards[0].textContent).toContain('why did FA-01 fail?')
  expect(cards[1].textContent).toContain('show H-Z2')
  expect(cards[1].textContent).toContain('Pipe H-Z2 (header')
  expect(cards[1].textContent).not.toContain('Voltage drop')
})

test('a typed question the co-pilot does not understand says no engine check ran', async () => {
  const user = userEvent.setup()
  renderPanel()
  await ask(user, 'hello')
  expect(await screen.findByText('No engine check ran')).toBeInTheDocument()
  expect(screen.getByText(/Try: “what if racks go to 200 kW”/)).toBeInTheDocument()
})

test('Live: the history shows what was said, the engine check behind the answer and what changed, and the status follows the turn', async () => {
  const user = userEvent.setup()
  let finishExplain: (v: { text: string }) => void = () => undefined
  const explain = vi.fn(() => new Promise<{ text: string }>((resolve) => (finishExplain = resolve)))
  const live = liveHarness(fakeApi({ explain }))
  renderPanel(live.services, realHallA())
  await startLive(user)

  await live.emit({ type: 'heard', text: 'Why did' })
  await live.emit({ type: 'heard', text: ' FA-01 fail?' })
  expect(screen.getByText('Hearing you…')).toBeInTheDocument()
  const convo = within(await screen.findByRole('list', { name: 'Conversation' }))
  expect(convo.getByText('You · voice')).toBeInTheDocument()
  expect(convo.getByText('Why did FA-01 fail?')).toBeInTheDocument()
  expect(convo.getByText('Listening…')).toBeInTheDocument()

  let done: Promise<Record<string, unknown>> = Promise.resolve({})
  act(() => {
    done = live.call({ name: 'explain_finding', args: { finding_id: 'R05:FA-01' } })
  })
  expect(await screen.findByText('Checking with the engine…')).toBeInTheDocument()
  await act(async () => {
    finishExplain({ text: 'Voltage drop is {value} against {limit}.' })
    await done
  })
  expect(await convo.findByText('Explain finding R05 · FA-01')).toBeInTheDocument()
  expect(convo.getByText(/^In r1: Voltage drop is 2\.16% against 2%\./)).toBeInTheDocument()
  expect(convo.getByText('Opened R05 · FA-01 in the finding drawer')).toBeInTheDocument()
  expect(useUi.getState().findingId).toBe('R05:FA-01')

  await live.emit({ type: 'speaking' })
  expect(screen.getByText('Gemini is replying…')).toBeInTheDocument()
  await live.emit({ type: 'turn_complete' })
  expect(screen.getByText('Listening (Gemini Live)')).toBeInTheDocument()
  expect(convo.queryByText('No engine check ran')).not.toBeInTheDocument()
  expect(turnCards()).toHaveLength(1)
})

test('Live: a spoken reply with no engine check behind it is flagged, and nothing opens or moves', async () => {
  const user = userEvent.setup()
  const live = liveHarness()
  renderPanel(live.services, realHallA())
  await startLive(user)
  await live.emit({ type: 'heard', text: 'Why did FA-01 fail?' })
  await live.emit({ type: 'speaking' })
  await live.emit({ type: 'turn_complete' })
  const convo = within(await screen.findByRole('list', { name: 'Conversation' }))
  expect(await convo.findByText('No engine check ran')).toBeInTheDocument()
  expect(convo.getByText(/Nothing was verified and nothing changed on screen/)).toBeInTheDocument()
  expect(convo.getByText(/Gemini replied by voice on its own/)).toBeInTheDocument()
  expect(useUi.getState().findingId).toBeNull()
  expect(useUi.getState().viewRev).toBeNull()
})

test('Live: each question is its own card, in the order it was asked', async () => {
  const user = userEvent.setup()
  const live = liveHarness()
  renderPanel(live.services, realHallA())
  await startLive(user)
  await live.emit({ type: 'heard', text: 'Show FA-01' })
  await act(async () => void (await live.call({ name: 'focus_element', args: { element_id: 'FA-01' } })))
  await live.emit({ type: 'speaking' })
  await live.emit({ type: 'turn_complete' })
  await live.emit({ type: 'heard', text: 'Show H-Z2' })
  await act(async () => void (await live.call({ name: 'focus_element', args: { element_id: 'H-Z2' } })))
  await live.emit({ type: 'turn_complete' })
  await waitFor(() => expect(turnCards()).toHaveLength(2))
  const cards = turnCards()
  expect(cards[0].textContent).toContain('Show FA-01')
  expect(cards[0].textContent).toMatch(/(Cable|Busway) FA-01: /)
  expect(cards[1].textContent).toContain('Show H-Z2')
  expect(cards[1].textContent).toContain('Pipe H-Z2 (header')
})

test('Live: a tool that fails tells Gemini so instead of ending the session, and the card says it could not run', async () => {
  const user = userEvent.setup()
  const live = liveHarness()
  renderPanel(live.services, realHallA())
  await startLive(user)
  const focus = useUi.getState().focus
  useUi.setState({
    focus: () => {
      throw new Error('boom')
    },
  })
  try {
    await live.emit({ type: 'heard', text: 'Show FA-01' })
    // The SDK ends the whole conversation if this handler throws, so it must answer instead.
    const response = await act(async () => live.call({ name: 'focus_element', args: { element_id: 'FA-01' } }))
    expect(response).toEqual({ error: 'unavailable' })
  } finally {
    useUi.setState({ focus })
  }
  const convo = within(await screen.findByRole('list', { name: 'Conversation' }))
  expect(convo.getByText('That check could not run.')).toBeInTheDocument()
  expect(screen.getByText('Listening (Gemini Live)')).toBeInTheDocument()
})

test('Live: a tool call that arrives before any transcript still gets a card, and the words fill in when they come', async () => {
  const user = userEvent.setup()
  const live = liveHarness()
  renderPanel(live.services, realHallA())
  await startLive(user)
  await act(async () => void (await live.call({ name: 'focus_element', args: { element_id: 'FA-01' } })))
  const convo = within(await screen.findByRole('list', { name: 'Conversation' }))
  expect(convo.getByText('(your words were not transcribed)')).toBeInTheDocument()
  await live.emit({ type: 'heard', text: 'Show me FA-01' })
  expect(convo.getByText('Show me FA-01')).toBeInTheDocument()
  expect(convo.queryByText('(your words were not transcribed)')).not.toBeInTheDocument()
  expect(turnCards()).toHaveLength(1)
})

test('Live: stopping the voice mid-question closes its card as unchecked', async () => {
  const user = userEvent.setup()
  const live = liveHarness()
  renderPanel(live.services, realHallA())
  await startLive(user)
  await live.emit({ type: 'heard', text: 'Why did FA-01' })
  await user.click(screen.getByRole('button', { name: 'Stop' }))
  expect(await screen.findByText('No engine check ran')).toBeInTheDocument()
  expect(screen.getByText('Voice was stopped before there was an answer.')).toBeInTheDocument()
  expect(await screen.findByRole('button', { name: 'Start voice' })).toBeInTheDocument()
})

test('Live: the model\'s own words never reach the screen, only the engine\'s text', async () => {
  const user = userEvent.setup()
  const live = liveHarness()
  renderPanel(live.services, realHallA())
  await startLive(user)
  await live.emit({ type: 'heard', text: 'Why did FA-01 fail?' })
  await act(async () => void (await live.call({ name: 'explain_finding', args: { finding_id: 'R05:FA-01' } })))
  await live.emit({ type: 'speaking' })
  await live.emit({ type: 'turn_complete' })
  // The only events the service can send are heard/speaking/turn_complete: nothing in them carries the model's speech.
  expect(screen.queryByText(/Gemini said/i)).not.toBeInTheDocument()
  expect(turnCards()[0].textContent).toMatch(/Explain finding R05 · FA-01/)
})

test('push-to-talk writes up the turn too: the transcript, the engine check and what changed', async () => {
  const answer = 'In r1: Voltage drop from the UPS output board to the furthest tap-off via FA-01 is 2.16% against a limit of 2%.'
  await pushToTalk({
    transcript: 'Why did FA-01 fail?',
    answer,
    tool_results: [{ name: 'explain_finding', args: { finding_id: 'R05:FA-01' }, result: { text: answer, revision: 'r1' } }],
  })
  const convo = await conversation()
  expect(await convo.findByText('You · push-to-talk')).toBeInTheDocument()
  expect(convo.getByText('Why did FA-01 fail?')).toBeInTheDocument()
  expect(convo.getByText('Explain finding R05 · FA-01')).toBeInTheDocument()
  expect(convo.getByText('Opened R05 · FA-01 in the finding drawer')).toBeInTheDocument()
  expect(convo.getByText(/^Switched to r1 \(.*\), where this check failed$/)).toBeInTheDocument()
})

test('push-to-talk "what is the power of rack R1-01": the server only showed it, the card has the engine\'s record of the rack', async () => {
  await pushToTalk({
    transcript: 'What is the power of rack R1-01?',
    answer: 'Showing R1-01.',
    tool_results: [{ name: 'focus_element', args: { element_id: 'R1-01' }, result: { focused: 'R1-01' } }],
  })
  const convo = await conversation()
  expect(await convo.findByText('Details of R1-01')).toBeInTheDocument()
  expect(convo.getByText(/^Rack R1-01 \(row R1\): [\d,.]+ kW, liquid fraction [\d.]+, fed by /)).toBeInTheDocument()
  expect(convo.queryByText('Showing R1-01.')).not.toBeInTheDocument()
  expect(convo.getByText('Showing R1-01 on the 3D hall and the SLD')).toBeInTheDocument()
})

test('push-to-talk with no engine check behind the reply says so', async () => {
  await pushToTalk({ transcript: 'Tell me a joke', answer: 'No tool answers that question.', tool_results: [] })
  const convo = await conversation()
  expect(await convo.findByText('No engine check ran')).toBeInTheDocument()
  expect(convo.getByText('No tool answers that question.')).toBeInTheDocument()
})

// ---- The debug log: what was typed, heard, said and answered, kept for debugging (lib/debugLog.ts).

describe('the debug log', () => {
  beforeEach(() => clearDebugLog())
  const kinds = () => debugEntries().map((e) => e.kind)

  test('a typed question is logged with the engine check that ran and the answer it gave', async () => {
    const user = userEvent.setup()
    renderPanel(fakeServices(), realHallA())
    await ask(user, 'show H-Z2')
    await (await conversation()).findByText(/^Pipe H-Z2/)
    expect(kinds()).toEqual(['typed', 'tool_result'])
    expect(debugEntries()[0]).toMatchObject({ text: 'show H-Z2', tool: 'focus_element' })
    expect(debugEntries()[1]).toMatchObject({ via: 'typed', check: 'Details of H-Z2' })
    expect(String(debugEntries()[1].answer)).toMatch(/^Pipe H-Z2/)
  })

  test('a typed question that is not understood is logged too', async () => {
    const user = userEvent.setup()
    renderPanel(fakeServices(), realHallA())
    await ask(user, 'hello')
    expect(debugEntries()).toEqual([expect.objectContaining({ kind: 'typed', text: 'hello', tool: null })])
  })

  test('a Live tool call is logged with its arguments, and the engine data it sent back to Gemini', async () => {
    const user = userEvent.setup()
    const live = liveHarness()
    renderPanel(live.services, realHallA())
    await startLive(user)
    await act(async () => void (await live.call({ name: 'focus_element', args: { element_id: 'R1-01' } })))
    expect(kinds()).toEqual(['tool_call', 'tool_response'])
    expect(debugEntries()[0]).toMatchObject({ via: 'live', name: 'focus_element', args: { element_id: 'R1-01' } })
    expect(debugEntries()[1]).toMatchObject({ via: 'live', name: 'focus_element', data: { kw: expect.any(Number), kind: 'rack' } })
  })

  test('a Live turn is logged with both sides in full, Gemini\'s words included, and they stay off the screen', async () => {
    const user = userEvent.setup()
    const live = liveHarness()
    renderPanel(live.services, realHallA())
    await startLive(user)
    await live.debug({ heard: 'What is the power of rack R1-01?', said: 'I am unable to retrieve that.', interrupted: false })
    expect(debugEntries()).toEqual([
      expect.objectContaining({ kind: 'live_turn', heard: 'What is the power of rack R1-01?', said: 'I am unable to retrieve that.', interrupted: false }),
    ])
    expect(screen.queryByText(/unable to retrieve/)).not.toBeInTheDocument()
  })

  test('a failing Live tool is logged as an error', async () => {
    const user = userEvent.setup()
    const live = liveHarness()
    renderPanel(live.services, realHallA())
    await startLive(user)
    const focus = useUi.getState().focus
    useUi.setState({
      focus: () => {
        throw new Error('boom')
      },
    })
    try {
      await live.emit({ type: 'heard', text: 'Show FA-01' }) // a render, so the panel picks up the swapped focus
      await act(async () => void (await live.call({ name: 'focus_element', args: { element_id: 'FA-01' } })))
    } finally {
      useUi.setState({ focus })
    }
    expect(kinds()).toEqual(['tool_call', 'tool_error'])
    expect(debugEntries()[1]).toMatchObject({ via: 'live', name: 'focus_element', error: expect.stringContaining('boom') })
  })

  test('push-to-talk is logged with what was heard, the tools the server ran, and the answer', async () => {
    await pushToTalk({
      transcript: 'Show R1-01',
      answer: 'Showing R1-01.',
      tool_results: [{ name: 'focus_element', args: { element_id: 'R1-01' }, result: { focused: 'R1-01' } }],
    })
    await (await conversation()).findByText(/^Rack R1-01/)
    expect(debugEntries()).toEqual([
      expect.objectContaining({ kind: 'ptt', transcript: 'Show R1-01', answer: 'Showing R1-01.', tools: [{ name: 'focus_element', args: { element_id: 'R1-01' } }] }),
    ])
  })
})

test('the conversation is filed under the project it was had in', () => {
  renderPanel(fakeServices(), realHallA())
  expect(useConversation.getState().project).toBe(realHallA().project.id)
})
