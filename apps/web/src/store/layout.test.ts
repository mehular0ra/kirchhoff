import { useTour } from '@/onboarding/tour/tour'
import { COPILOT_W, LANES_W, useLayout } from './layout'

beforeEach(() => {
  localStorage.clear()
  useLayout.getState().reset()
})

/** A page reload: the store module is evaluated again and reads what the last page left in storage. */
async function reload() {
  vi.resetModules()
  return (await import('./layout')).useLayout
}

test('both side panels start open at their usual widths', () => {
  expect(useLayout.getState()).toMatchObject({ lanesOpen: true, copilotOpen: true, lanesW: LANES_W.def, copilotW: COPILOT_W.def })
})

test('a width is kept between its smallest and largest, whatever is asked for', () => {
  const s = useLayout.getState()
  s.setLanesW(10)
  expect(useLayout.getState().lanesW).toBe(LANES_W.min)
  s.setLanesW(5000)
  expect(useLayout.getState().lanesW).toBe(LANES_W.max)
  s.setCopilotW(10)
  expect(useLayout.getState().copilotW).toBe(COPILOT_W.min)
  s.setCopilotW(5000)
  expect(useLayout.getState().copilotW).toBe(COPILOT_W.max)
  s.setCopilotW(401.6)
  expect(useLayout.getState().copilotW).toBe(402)
})

test('each side panel can be hidden and shown again without losing its width', () => {
  const s = useLayout.getState()
  s.setLanesW(300)
  s.toggleLanes()
  expect(useLayout.getState()).toMatchObject({ lanesOpen: false, lanesW: 300, copilotOpen: true })
  s.toggleLanes()
  expect(useLayout.getState()).toMatchObject({ lanesOpen: true, lanesW: 300 })
  s.toggleCopilot()
  expect(useLayout.getState().copilotOpen).toBe(false)
})

test('Gemini\'s spoken words are hidden until the visitor switches them on, and the choice survives a reload and a layout reset', async () => {
  expect(useLayout.getState().showSaid).toBe(false)
  useLayout.getState().toggleSaid()
  useLayout.getState().reset()
  expect(useLayout.getState().showSaid).toBe(true)
  expect((await reload()).getState().showSaid).toBe(true)
  useLayout.getState().toggleSaid()
  expect(useLayout.getState().showSaid).toBe(false)
})

test('openAll shows both panels again and keeps the widths the visitor chose', () => {
  const s = useLayout.getState()
  s.setLanesW(300)
  s.setCopilotW(420)
  s.toggleLanes()
  s.toggleCopilot()
  s.openAll()
  expect(useLayout.getState()).toMatchObject({ lanesOpen: true, copilotOpen: true, lanesW: 300, copilotW: 420 })
})

test('starting the guided tour opens a panel the visitor had hidden, because its steps point into them', () => {
  useLayout.getState().toggleCopilot()
  useLayout.getState().toggleLanes()
  useTour.getState().start()
  expect(useLayout.getState()).toMatchObject({ lanesOpen: true, copilotOpen: true })
  useTour.getState().stop(false)
})

test('a tour resumed after a reload opens the panels too', async () => {
  useLayout.getState().toggleCopilot()
  localStorage.setItem('kirchhoff.tour', JSON.stringify({ active: true, step: 3, done: false }))
  vi.resetModules()
  const layout = (await import('./layout')).useLayout
  expect(layout.getState().copilotOpen).toBe(false)
  await import('@/onboarding/tour/tour')
  expect(layout.getState().copilotOpen).toBe(true)
  localStorage.removeItem('kirchhoff.tour')
})

test('reset puts both panels back, open, at their usual widths', () => {
  const s = useLayout.getState()
  s.setLanesW(400)
  s.setCopilotW(500)
  s.toggleLanes()
  s.toggleCopilot()
  s.reset()
  expect(useLayout.getState()).toMatchObject({ lanesOpen: true, copilotOpen: true, lanesW: LANES_W.def, copilotW: COPILOT_W.def })
})

test('the layout survives a page reload', async () => {
  const s = useLayout.getState()
  s.setLanesW(320)
  s.setCopilotW(444)
  s.toggleCopilot()
  const after = await reload()
  expect(after.getState()).toMatchObject({ lanesOpen: true, lanesW: 320, copilotOpen: false, copilotW: 444 })
})

test('saved values that are out of range or not numbers are pulled back, and damaged storage is ignored', async () => {
  localStorage.setItem('kirchhoff.layout', JSON.stringify({ lanesW: 9999, copilotW: 'wide', lanesOpen: 'yes', copilotOpen: false }))
  const clamped = await reload()
  expect(clamped.getState()).toMatchObject({ lanesW: LANES_W.max, copilotW: COPILOT_W.def, lanesOpen: true, copilotOpen: false })
  localStorage.setItem('kirchhoff.layout', '{not json')
  const damaged = await reload()
  expect(damaged.getState()).toMatchObject({ lanesOpen: true, copilotOpen: true, lanesW: LANES_W.def, copilotW: COPILOT_W.def })
})

test('storage that is full or blocked does not stop the layout from changing', () => {
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('QuotaExceededError')
  })
  expect(() => useLayout.getState().setLanesW(300)).not.toThrow()
  expect(useLayout.getState().lanesW).toBe(300)
})
