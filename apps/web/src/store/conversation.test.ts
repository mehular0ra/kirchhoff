import { useConversation } from './conversation'

beforeEach(() => {
  localStorage.clear()
  useConversation.setState({ project: null, turns: [], saved: {} })
})

/** A page reload: the store module is evaluated again and reads what the last page left in storage. */
async function reload() {
  vi.resetModules()
  return (await import('./conversation')).useConversation
}

test('an answer that comes back after the visitor moved to another project still lands on its own question', () => {
  const s = useConversation.getState()
  s.enter('hall-a')
  const id = s.start('typed', 'why FA-01', 'working')
  s.enter('hall-b') // the panel moved on before the engine answered
  s.hear(id, '!')
  s.addStep(id, { check: 'Explain finding R05 · FA-01', answer: 'late', actions: [] })
  s.setPhase(id, 'answered')
  expect(useConversation.getState().turns).toEqual([])
  s.enter('hall-a')
  expect(useConversation.getState().turns[0]).toMatchObject({ asked: 'why FA-01!', phase: 'answered', steps: [{ answer: 'late' }] })
})

test('a spoken question is open until its turn ends; a typed one never is', () => {
  const s = useConversation.getState()
  const spoken = s.start('live', null, 'hearing')
  const typed = s.start('typed', 'why FA-01', 'working')
  expect(useConversation.getState().turns.map((t) => t.ended)).toEqual([false, true])
  s.setEnded(spoken, true)
  expect(useConversation.getState().turns[0].ended).toBe(true)
  s.setEnded(typed, false)
  expect(useConversation.getState().turns[1].ended).toBe(false)
})

test('what the model said is kept on its card, apart from the engine answer', () => {
  const s = useConversation.getState()
  const id = s.start('live', 'Why FA-01', 'working')
  expect(useConversation.getState().turns[0].said).toBeNull()
  s.setSaid(id, 'It drops 2.16 percent.')
  expect(useConversation.getState().turns[0]).toMatchObject({ said: 'It drops 2.16 percent.', steps: [] })
})

test('a spoken question restored after a reload counts as ended, so it does not claim to be listening', async () => {
  const s = useConversation.getState()
  s.enter('hall-a')
  s.start('live', null, 'hearing')
  const after = await reload()
  after.getState().enter('hall-a')
  expect(after.getState().turns[0].ended).toBe(true)
})

test('a turn keeps what was asked, how, and when, and starts in the phase it was given', () => {
  const id = useConversation.getState().start('typed', 'why FA-01', 'working')
  const [turn] = useConversation.getState().turns
  expect(turn).toMatchObject({ id, via: 'typed', asked: 'why FA-01', phase: 'working', steps: [], note: null })
  expect(typeof turn.at).toBe('number')
})

test('turns keep the order they were asked in, whichever answer arrives first', () => {
  const s = useConversation.getState()
  const slow = s.start('typed', 'why FA-01', 'working')
  const fast = s.start('typed', 'show H-Z2', 'working')
  s.addStep(fast, { check: 'Show H-Z2', answer: 'Showing H-Z2.', actions: [] })
  s.addStep(slow, { check: 'Explain finding R05 · FA-01', answer: 'In r1: …', actions: [] })
  expect(useConversation.getState().turns.map((t) => t.asked)).toEqual(['why FA-01', 'show H-Z2'])
  expect(useConversation.getState().turns[0].steps[0].check).toBe('Explain finding R05 · FA-01')
})

test('a spoken question grows as the transcript arrives in pieces', () => {
  const s = useConversation.getState()
  const id = s.start('live', '', 'hearing')
  for (const piece of ['Why did', ' FA-01', ' fail?']) s.hear(id, piece)
  expect(useConversation.getState().turns[0].asked).toBe('Why did FA-01 fail?')
})

test('a question that was not transcribed has no text', () => {
  useConversation.getState().start('live', null, 'working')
  expect(useConversation.getState().turns[0].asked).toBeNull()
})

test('a turn with no engine check says why, in a note', () => {
  const s = useConversation.getState()
  const id = s.start('live', 'Why did FA-01 fail?', 'hearing')
  s.setPhase(id, 'unchecked', 'The model answered by voice without running an engine check.')
  expect(useConversation.getState().turns[0]).toMatchObject({ phase: 'unchecked', note: 'The model answered by voice without running an engine check.' })
})

test('one turn can run several checks', () => {
  const s = useConversation.getState()
  const id = s.start('live', 'Why FA-01, and what if 200 kW?', 'working')
  s.addStep(id, { check: 'Explain finding R05 · FA-01', answer: 'a', actions: ['Opened R05 · FA-01'] })
  s.addStep(id, { check: 'What-if', answer: 'b', actions: [] })
  expect(useConversation.getState().turns[0].steps.map((x) => x.check)).toEqual(['Explain finding R05 · FA-01', 'What-if'])
})

test('clear forgets every turn', () => {
  const s = useConversation.getState()
  s.start('typed', 'a', 'working')
  s.start('typed', 'b', 'working')
  s.clear()
  expect(useConversation.getState().turns).toEqual([])
})

test('another project starts its own conversation; coming back to a project brings its turns back', () => {
  const s = useConversation.getState()
  s.enter('hall-a')
  s.start('typed', 'why FA-01', 'working')
  s.enter('hall-a')
  expect(useConversation.getState().turns).toHaveLength(1)
  s.enter('hall-b')
  expect(useConversation.getState().turns).toEqual([])
  expect(useConversation.getState().project).toBe('hall-b')
  s.start('typed', 'show H-Z2', 'working')
  s.enter('hall-a')
  expect(useConversation.getState().turns.map((t) => t.asked)).toEqual(['why FA-01'])
  s.enter('hall-b')
  expect(useConversation.getState().turns.map((t) => t.asked)).toEqual(['show H-Z2'])
})

test('clear forgets only the project on screen', () => {
  const s = useConversation.getState()
  s.enter('hall-a')
  s.start('typed', 'why FA-01', 'working')
  s.enter('hall-b')
  s.start('typed', 'show H-Z2', 'working')
  s.clear()
  expect(useConversation.getState().turns).toEqual([])
  s.enter('hall-a')
  expect(useConversation.getState().turns).toHaveLength(1)
})

test('the conversation survives a page reload, for every project', async () => {
  const s = useConversation.getState()
  s.enter('hall-a')
  const id = s.start('typed', 'why FA-01', 'working')
  s.addStep(id, { check: 'Explain finding R05 · FA-01', answer: 'In r1: …', actions: ['Opened R05 · FA-01 in the finding drawer'] })
  s.setPhase(id, 'answered')
  s.enter('hall-b')
  s.start('typed', 'show H-Z2', 'working')
  const after = await reload()
  after.getState().enter('hall-b')
  expect(after.getState().turns.map((t) => t.asked)).toEqual(['show H-Z2'])
  after.getState().enter('hall-a')
  expect(after.getState().turns[0]).toMatchObject({ asked: 'why FA-01', phase: 'answered' })
  expect(after.getState().turns[0].steps[0].check).toBe('Explain finding R05 · FA-01')
})

test('a question still being heard or checked when the page went away is settled, not left spinning', async () => {
  const s = useConversation.getState()
  s.enter('hall-a')
  s.start('live', 'Why did', 'hearing')
  s.start('typed', 'why FA-01', 'working')
  const done = s.start('typed', 'show H-Z2', 'working')
  s.addStep(done, { check: 'Show H-Z2', answer: 'Showing H-Z2.', actions: [] })
  const after = await reload()
  after.getState().enter('hall-a')
  const [hearing, working, partly] = after.getState().turns
  expect(hearing.phase).toBe('unchecked')
  expect(hearing.note).toMatch(/page was closed or reloaded/)
  expect(working.phase).toBe('failed')
  expect(working.note).toMatch(/page was closed or reloaded/)
  expect(partly.phase).toBe('answered')
})

test('new questions after a reload get ids no restored question has', async () => {
  const s = useConversation.getState()
  s.enter('hall-a')
  s.start('typed', 'a', 'working')
  s.start('typed', 'b', 'working')
  s.enter('hall-b')
  const last = s.start('typed', 'c', 'working')
  const after = await reload()
  after.getState().enter('hall-a')
  const id = after.getState().start('typed', 'd', 'working')
  expect(id).toBeGreaterThan(last)
  const ids = after.getState().turns.map((t) => t.id)
  expect(new Set(ids).size).toBe(ids.length)
  // an answer for the new question lands on that question alone
  after.getState().addStep(id, { check: 'c', answer: 'only d', actions: [] })
  expect(after.getState().turns.filter((t) => t.steps.length > 0).map((t) => t.asked)).toEqual(['d'])
})

test('only the latest 100 questions of a project are kept', async () => {
  const s = useConversation.getState()
  s.enter('hall-a')
  for (let i = 1; i <= 105; i++) s.start('typed', `q${i}`, 'answered')
  expect(useConversation.getState().turns).toHaveLength(100)
  expect(useConversation.getState().turns[0].asked).toBe('q6')
  const after = await reload()
  after.getState().enter('hall-a')
  expect(after.getState().turns).toHaveLength(100)
})

test('storage that is full or blocked does not stop the conversation', () => {
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('QuotaExceededError')
  })
  const s = useConversation.getState()
  s.enter('hall-a')
  expect(() => s.start('typed', 'why FA-01', 'working')).not.toThrow()
  expect(useConversation.getState().turns).toHaveLength(1)
})

test('a damaged saved conversation is ignored', async () => {
  localStorage.setItem('kirchhoff.conversation', '{not json')
  const after = await reload()
  after.getState().enter('hall-a')
  expect(after.getState().turns).toEqual([])
  localStorage.setItem('kirchhoff.conversation', JSON.stringify({ project: 'hall-a', turns: 'nope', saved: 7 }))
  const again = await reload()
  again.getState().enter('hall-a')
  expect(again.getState().turns).toEqual([])
})

test('changes to a turn that is not there are ignored', () => {
  const s = useConversation.getState()
  expect(() => {
    s.hear(999, 'x')
    s.setPhase(999, 'answered')
    s.addStep(999, { check: 'c', answer: 'a', actions: [] })
  }).not.toThrow()
  expect(useConversation.getState().turns).toEqual([])
})
