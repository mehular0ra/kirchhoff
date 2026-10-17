import { makeLiveObserver, teeReceive, type LiveMessage, type LiveVoiceEvent } from './liveEvents'

const seen = () => {
  const events: LiveVoiceEvent[] = []
  return { events, observe: makeLiveObserver((e) => events.push(e)) }
}

test('the visitor\'s transcript comes through in the pieces the service sends it in, spaces kept', () => {
  const { events, observe } = seen()
  for (const text of ['Why did', ' FA-01', ' fail?']) observe({ type: 'serverContent', inputTranscription: { text } })
  expect(events).toEqual([
    { type: 'heard', text: 'Why did' },
    { type: 'heard', text: ' FA-01' },
    { type: 'heard', text: ' fail?' },
  ])
})

test('empty transcript pieces and messages with no news say nothing', () => {
  const { events, observe } = seen()
  observe({ type: 'serverContent', inputTranscription: { text: '' } })
  observe({ type: 'serverContent', inputTranscription: {} })
  observe({ type: 'serverContent' })
  observe({ type: 'goingAwayNotice' })
  expect(events).toEqual([])
})

test('the spoken reply is announced once per reply, from its audio or its transcript', () => {
  const { events, observe } = seen()
  observe({ type: 'serverContent', modelTurn: { parts: [{ type: 'inlineData', inlineData: { mimeType: 'audio/pcm;rate=24000' } }] } })
  observe({ type: 'serverContent', modelTurn: { parts: [{ type: 'inlineData', inlineData: { mimeType: 'audio/pcm;rate=24000' } }] } })
  observe({ type: 'serverContent', outputTranscription: { text: 'In r1' } })
  expect(events).toEqual([{ type: 'speaking' }])
})

test('the model\'s own words are never passed on as text: only that it is speaking', () => {
  const { events, observe } = seen()
  observe({ type: 'serverContent', outputTranscription: { text: 'FA-01 drops 2.16 percent' } })
  expect(JSON.stringify(events)).not.toMatch(/2\.16|FA-01/)
})

test('the end of a reply, or an interruption, ends the turn, and the next reply is announced again', () => {
  const { events, observe } = seen()
  observe({ type: 'serverContent', outputTranscription: { text: 'a' } })
  observe({ type: 'serverContent', turnComplete: true })
  observe({ type: 'serverContent', outputTranscription: { text: 'b' } })
  observe({ type: 'serverContent', interrupted: true })
  expect(events.map((e) => e.type)).toEqual(['speaking', 'turn_complete', 'speaking', 'turn_complete'])
})

test('a tool call is not an event of its own: the handler path owns it', () => {
  const { events, observe } = seen()
  observe({ type: 'toolCall', functionCalls: [{ name: 'focus_element', args: {} }] } as LiveMessage)
  expect(events).toEqual([])
})

async function* fakeMessages(items: Array<Record<string, unknown>>) {
  for (const m of items) yield m as { type: string }
}

test('teeReceive passes every message on untouched and lets the panel watch them go by', async () => {
  const items = [{ type: 'serverContent', inputTranscription: { text: 'hi' } }, { type: 'toolCall' }, { type: 'serverContent', turnComplete: true }]
  const session = { receive: () => fakeMessages(items) }
  const watched: unknown[] = []
  teeReceive(session, (m) => watched.push(m))
  const out: unknown[] = []
  for await (const m of session.receive()) out.push(m)
  expect(out).toEqual(items)
  expect(watched).toEqual(items)
})

test('a watcher that throws never breaks the audio conversation', async () => {
  const items = [{ type: 'serverContent' }, { type: 'serverContent', turnComplete: true }]
  const session = { receive: () => fakeMessages(items) }
  teeReceive(session, () => {
    throw new Error('panel bug')
  })
  const out: unknown[] = []
  for await (const m of session.receive()) out.push(m)
  expect(out).toEqual(items)
})

test('stopping the conversation closes the underlying stream', async () => {
  let closed = false
  async function* source() {
    try {
      yield { type: 'serverContent' }
      yield { type: 'serverContent' }
    } finally {
      closed = true
    }
  }
  const session = { receive: () => source() as AsyncGenerator<{ type: string }, void, unknown> }
  teeReceive(session, () => undefined)
  const gen = session.receive()
  await gen.next()
  await gen.return(undefined)
  expect(closed).toBe(true)
})
