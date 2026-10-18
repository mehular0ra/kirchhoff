import { clearDebugLog, debugEntries, exportDebugLog, logDebug } from './debugLog'

beforeEach(() => {
  localStorage.clear()
  clearDebugLog()
})

/** A page reload: the module is evaluated again and reads what the last page left in storage. */
async function reload() {
  vi.resetModules()
  return import('./debugLog')
}

test('an entry keeps when it happened, what kind it is, and its details', () => {
  logDebug('typed', { text: 'why FA-01' })
  const [e] = debugEntries()
  expect(e).toMatchObject({ kind: 'typed', text: 'why FA-01' })
  expect(new Date(e.t).toISOString()).toBe(e.t)
})

test('entries stay in the order they happened', () => {
  logDebug('a', {})
  logDebug('b', {})
  logDebug('c', {})
  expect(debugEntries().map((e) => e.kind)).toEqual(['a', 'b', 'c'])
})

test('only the latest 400 entries are kept', () => {
  for (let i = 1; i <= 405; i++) logDebug('n', { i })
  expect(debugEntries()).toHaveLength(400)
  expect(debugEntries()[0].i).toBe(6)
})

test('the log survives a page reload', async () => {
  logDebug('heard', { text: 'Why did FA-01 fail?' })
  const after = await reload()
  expect(after.debugEntries()).toHaveLength(1)
  expect(after.debugEntries()[0]).toMatchObject({ kind: 'heard', text: 'Why did FA-01 fail?' })
})

test('clearing empties it, for good', async () => {
  logDebug('x', {})
  clearDebugLog()
  expect(debugEntries()).toEqual([])
  expect((await reload()).debugEntries()).toEqual([])
})

test('damaged or foreign saved data is ignored', async () => {
  localStorage.setItem('kirchhoff.debuglog', '{not json')
  expect((await reload()).debugEntries()).toEqual([])
  localStorage.setItem('kirchhoff.debuglog', JSON.stringify([{ t: 'x' }, 7, null, { t: '2026-10-18T03:00:00.000Z', kind: 'ok' }]))
  expect((await reload()).debugEntries().map((e) => e.kind)).toEqual(['ok'])
})

test('storage that is full or blocked does not stop logging', () => {
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('QuotaExceededError')
  })
  expect(() => logDebug('x', {})).not.toThrow()
  expect(debugEntries()).toHaveLength(1)
})

test('the export is one JSON document: when, where, the conversation as shown, and every entry', () => {
  logDebug('tool_call', { name: 'focus_element' })
  const doc = JSON.parse(exportDebugLog({ project: 'hall-a', conversation: [{ asked: 'why FA-01' }] }))
  expect(doc).toMatchObject({ app: 'kirchhoff', project: 'hall-a', conversation: [{ asked: 'why FA-01' }] })
  expect(new Date(doc.exported_at).toString()).not.toBe('Invalid Date')
  expect(doc.entries).toHaveLength(1)
  expect(doc.entries[0]).toMatchObject({ kind: 'tool_call', name: 'focus_element' })
})
