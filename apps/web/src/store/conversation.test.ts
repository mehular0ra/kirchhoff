import { useConversation } from './conversation'

beforeEach(() => useConversation.getState().clear())

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

test('another project starts an empty conversation; coming back to the same project keeps its turns', () => {
  const s = useConversation.getState()
  s.enter('hall-a')
  s.start('typed', 'why FA-01', 'working')
  s.enter('hall-a')
  expect(useConversation.getState().turns).toHaveLength(1)
  s.enter('grid-132kv')
  expect(useConversation.getState().turns).toEqual([])
  expect(useConversation.getState().project).toBe('grid-132kv')
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
