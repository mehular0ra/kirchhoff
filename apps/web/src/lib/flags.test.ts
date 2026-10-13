import { currentShot, initPresentationMode, isPresentationMode } from './flags'

test('?present=1 turns presentation mode on for the session; ?present=0 turns it off', () => {
  expect(initPresentationMode('')).toBe(false)
  expect(initPresentationMode('?present=1')).toBe(true)
  expect(document.documentElement.dataset.present).toBe('1')
  expect(initPresentationMode('')).toBe(true) // persisted in sessionStorage
  expect(isPresentationMode()).toBe(true)
  expect(initPresentationMode('?present=0')).toBe(false)
  expect(currentShot('?shot=cold-open')).toBe('cold-open')
})
