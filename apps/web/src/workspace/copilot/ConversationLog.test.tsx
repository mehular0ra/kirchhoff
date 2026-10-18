import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { clearDebugLog, debugEntries, logDebug } from '@/lib/debugLog'
import { useConversation } from '@/store/conversation'
import { useLayout } from '@/store/layout'
import { ConversationLog } from './ConversationLog'

beforeEach(() => act(() => useConversation.setState({ project: null, turns: [], saved: {} })))

const store = () => useConversation.getState()

describe('the debug log download', () => {
  let saved: { blob: Blob; name: string } | null
  beforeEach(() => {
    saved = null
    clearDebugLog()
    URL.createObjectURL = vi.fn((b: Blob) => {
      saved = { blob: b, name: '' }
      return 'blob:debug'
    })
    URL.revokeObjectURL = vi.fn()
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      if (saved) saved.name = this.download
    })
  })

  const text = (b: Blob) =>
    new Promise<string>((resolve) => {
      const r = new FileReader()
      r.onload = () => resolve(String(r.result))
      r.readAsText(b)
    })

  test('one button downloads the whole record as a JSON file', async () => {
    const user = userEvent.setup()
    store().enter('hall-b')
    const id = store().start('typed', 'show R1-01', 'answered')
    store().addStep(id, { check: 'Details of R1-01', answer: 'Rack R1-01 (row R1): 132 kW', actions: [] })
    logDebug('live_turn', { heard: 'What is the power of rack R1-01?', said: 'It has 132 kW.' })
    render(<ConversationLog />)
    await user.click(screen.getByRole('button', { name: 'Download debug log' }))
    expect(saved?.name).toMatch(/^kirchhoff-debug-.*\.json$/)
    const doc = JSON.parse(await text(saved!.blob))
    expect(doc).toMatchObject({ app: 'kirchhoff', project: 'hall-b' })
    expect(doc.conversation.turns[0]).toMatchObject({ asked: 'show R1-01' })
    expect(doc.entries[0]).toMatchObject({ kind: 'live_turn', said: 'It has 132 kW.' })
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:debug')
  })

  test('it can be downloaded even before anything was asked on this page, if an earlier page left a record', async () => {
    const user = userEvent.setup()
    logDebug('typed', { text: 'earlier' })
    render(<ConversationLog />)
    await user.click(screen.getByRole('button', { name: 'Download debug log' }))
    expect(JSON.parse(await text(saved!.blob)).entries).toHaveLength(1)
  })

  test('the debug record has its own Clear button, since it holds what was said and heard', async () => {
    const user = userEvent.setup()
    logDebug('live_turn', { heard: 'a', said: 'b' })
    render(<ConversationLog />)
    await user.click(screen.getByRole('button', { name: 'Clear debug log' }))
    expect(debugEntries()).toEqual([])
  })

  test('Clear conversation does not throw the debug record away', async () => {
    const user = userEvent.setup()
    store().start('typed', 'a', 'working')
    logDebug('typed', { text: 'a' })
    render(<ConversationLog />)
    await user.click(screen.getByRole('button', { name: 'Clear conversation' }))
    expect(debugEntries()).toHaveLength(1)
  })
})

describe('a spoken question\'s words', () => {
  test('while its turn is still going the card says it is listening, not that nothing was transcribed', () => {
    const id = store().start('live', null, 'working')
    store().addStep(id, { check: 'Details of R1-01', answer: 'Rack R1-01 …', actions: [] })
    render(<ConversationLog />)
    expect(screen.getByText('Listening for your words…')).toBeInTheDocument()
    expect(screen.queryByText('(your words were not transcribed)')).not.toBeInTheDocument()
  })

  test('once the turn has ended without words it says so', () => {
    const id = store().start('live', null, 'working')
    store().setEnded(id, true)
    render(<ConversationLog />)
    expect(screen.getByText('(your words were not transcribed)')).toBeInTheDocument()
  })
})

describe('what Gemini said aloud', () => {
  beforeEach(() => useLayout.setState({ showSaid: false }))
  const withSaid = () => {
    const id = store().start('live', 'Why FA-01', 'answered')
    store().setSaid(id, 'The drop is a little over the limit.')
    store().setEnded(id, true)
  }

  test('is not on the screen by default: the engine writes the answer', () => {
    withSaid()
    render(<ConversationLog />)
    expect(screen.queryByText(/a little over the limit/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Show what Gemini said' })).toHaveAttribute('aria-pressed', 'false')
  })

  test('is shown, marked as spoken and not checked by the engine, when the visitor switches it on', async () => {
    const user = userEvent.setup()
    withSaid()
    render(<ConversationLog />)
    await user.click(screen.getByRole('button', { name: 'Show what Gemini said' }))
    const card = screen.getByText(/a little over the limit/).closest('[data-turn]') as HTMLElement
    expect(within(card).getByText('What Gemini said (spoken, not checked by the engine)')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Show what Gemini said' })).toHaveAttribute('aria-pressed', 'true')
  })

  test('a card with nothing said shows no such block, whatever the switch', () => {
    useLayout.setState({ showSaid: true })
    store().start('typed', 'why FA-01', 'answered')
    render(<ConversationLog />)
    expect(screen.queryByText(/What Gemini said/)).not.toBeInTheDocument()
  })
})

test('with no questions yet it says how to start and shows no list', () => {
  render(<ConversationLog />)
  expect(screen.getByText(/Ask by typing or by voice/)).toBeInTheDocument()
  expect(screen.queryByRole('list', { name: 'Conversation' })).not.toBeInTheDocument()
})

test('an empty hall says where the questions asked in other halls are', () => {
  store().enter('hall-a')
  store().start('typed', 'why FA-01', 'answered')
  store().enter('hall-b')
  render(<ConversationLog />)
  expect(screen.getByText(/Ask by typing or by voice/)).toBeInTheDocument()
  expect(screen.getByText('Questions you asked in other projects are kept with them.')).toBeInTheDocument()
})

test('with no history anywhere there is no pointer to other halls', () => {
  render(<ConversationLog />)
  expect(screen.queryByText(/kept with them/)).not.toBeInTheDocument()
})

test('a typed question shows what was asked, which engine check answered, the answer, and what changed on screen', () => {
  const id = store().start('typed', 'why FA-01', 'working')
  store().addStep(id, {
    check: 'Explain finding R05 · FA-01',
    answer: 'In r1: Voltage drop is 2.16% against a limit of 2%.',
    actions: ['Switched to r1 (checked), where this check failed', 'Opened R05 · FA-01 in the finding drawer'],
  })
  store().setPhase(id, 'answered')
  render(<ConversationLog />)
  const turn = within(screen.getByRole('list', { name: 'Conversation' })).getAllByRole('listitem')[0]
  expect(within(turn).getByText('You · typed')).toBeInTheDocument()
  expect(within(turn).getByText('why FA-01')).toBeInTheDocument()
  expect(within(turn).getByText('Engine check')).toBeInTheDocument()
  expect(within(turn).getByText('Explain finding R05 · FA-01')).toBeInTheDocument()
  // the answer is its own element, holding only the engine's text
  expect(within(turn).getByText('In r1: Voltage drop is 2.16% against a limit of 2%.').textContent).toBe('In r1: Voltage drop is 2.16% against a limit of 2%.')
  const changes = within(turn).getByRole('list', { name: 'What changed on screen' })
  expect(within(changes).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
    'Switched to r1 (checked), where this check failed',
    'Opened R05 · FA-01 in the finding drawer',
  ])
  expect(within(turn).queryByText(/No engine check ran/)).not.toBeInTheDocument()
})

test('a spoken question shows the transcript and that it was voice', () => {
  const id = store().start('live', 'Why did FA-01 fail?', 'working')
  store().addStep(id, { check: 'Explain finding R05 · FA-01', answer: 'a', actions: [] })
  store().setPhase(id, 'answered')
  render(<ConversationLog />)
  expect(screen.getByText('You · voice')).toBeInTheDocument()
  expect(screen.getByText('Why did FA-01 fail?')).toBeInTheDocument()
})

test('push-to-talk is labelled as such', () => {
  store().start('ptt', 'show H-Z2', 'working')
  render(<ConversationLog />)
  expect(screen.getByText('You · push-to-talk')).toBeInTheDocument()
})

test('a spoken question that was not transcribed says so instead of showing nothing', () => {
  store().setEnded(store().start('live', null, 'working'), true)
  render(<ConversationLog />)
  expect(screen.getByText('(your words were not transcribed)')).toBeInTheDocument()
})

test('waiting for the engine and listening are shown with an icon beside the text', () => {
  store().start('typed', 'why FA-01', 'working')
  store().start('live', 'Why did', 'hearing')
  render(<ConversationLog />)
  const waiting = screen.getByText('Waiting for the engine…')
  const listening = screen.getByText('Listening…')
  expect(waiting.parentElement!.querySelector('svg')).not.toBeNull()
  expect(listening.parentElement!.querySelector('svg')).not.toBeNull()
})

test('a turn where no engine check ran says nothing was verified or changed, with the reason', () => {
  const id = store().start('live', 'Why did FA-01 fail?', 'hearing')
  store().setPhase(id, 'unchecked', 'The model answered by voice without running an engine check.')
  render(<ConversationLog />)
  const note = screen.getByText('No engine check ran')
  expect(note.parentElement!.querySelector('svg')).not.toBeNull()
  expect(screen.getByText(/Nothing was verified and nothing changed on screen/)).toBeInTheDocument()
  expect(screen.getByText('The model answered by voice without running an engine check.')).toBeInTheDocument()
})

test('a typed question the co-pilot did not understand shows its help line', () => {
  const id = store().start('typed', 'hello', 'working')
  store().setPhase(id, 'unchecked', 'Try: “what if racks go to 200 kW”, “why FA-01”, “show H-Z2”.')
  render(<ConversationLog />)
  expect(screen.getByText(/Try: “what if racks go to 200 kW”/)).toBeInTheDocument()
})

test('a check that could not run says why', () => {
  const id = store().start('typed', 'why FA-01', 'working')
  store().setPhase(id, 'failed', 'That check could not run.')
  render(<ConversationLog />)
  expect(screen.getByText('That check could not run.')).toBeInTheDocument()
})

test('questions stay in the order they were asked, however late the answers come', () => {
  const first = store().start('typed', 'first question', 'working')
  store().start('typed', 'second question', 'working')
  store().addStep(first, { check: 'c', answer: 'late answer', actions: [] })
  render(<ConversationLog />)
  const items = within(screen.getByRole('list', { name: 'Conversation' })).getAllByRole('listitem', { hidden: false })
  const turns = items.filter((li) => li.getAttribute('data-turn'))
  expect(turns.map((li) => li.textContent)).toEqual([expect.stringContaining('first question'), expect.stringContaining('second question')])
  expect(turns[0].textContent).toContain('late answer')
})

test('Clear forgets the conversation', async () => {
  const user = userEvent.setup()
  store().start('typed', 'why FA-01', 'working')
  render(<ConversationLog />)
  await user.click(screen.getByRole('button', { name: 'Clear conversation' }))
  expect(store().turns).toEqual([])
  expect(screen.getByText(/Ask by typing or by voice/)).toBeInTheDocument()
})

test('the header counts the questions and says where the written answers come from', () => {
  store().start('typed', 'a', 'working')
  store().start('typed', 'b', 'working')
  render(<ConversationLog />)
  expect(screen.getByText('Conversation')).toBeInTheDocument()
  expect(screen.getByText('2 questions')).toBeInTheDocument()
  expect(screen.getByText(/The engine writes every answer/)).toBeInTheDocument()
})
