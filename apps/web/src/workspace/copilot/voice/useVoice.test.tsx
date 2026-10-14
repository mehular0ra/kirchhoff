import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { ServicesProvider, type Services } from '@/services/services'
import { fakeApi, fakeServices } from '@/test/render'
import { useVoice } from './useVoice'

function hook(services: Services, opts: Partial<Parameters<typeof useVoice>[0]> = {}) {
  const wrapper = ({ children }: { children: ReactNode }) => <ServicesProvider services={services}>{children}</ServicesProvider>
  return renderHook(
    () =>
      useVoice({
        revisionRef: 'seed:hall-a@r1',
        onToolCall: async () => ({}),
        onPushToTalk: () => undefined,
        ...opts,
      }),
    { wrapper },
  )
}

test('unmounting mid-recording stops the mic stream and discards the clip', async () => {
  const stopTrack = vi.fn()
  vi.spyOn(navigator.mediaDevices, 'getUserMedia').mockResolvedValue({ getTracks: () => [{ stop: stopTrack }] } as unknown as MediaStream)
  const api = fakeApi()
  const { result, unmount } = hook(fakeServices({ api, startLiveVoice: null }))

  await act(async () => {
    await result.current.pttDown()
  })
  expect(result.current.mode).toBe('recording')

  unmount()
  await act(async () => {}) // flush the Recording.stop() promise

  expect(stopTrack).toHaveBeenCalled()
  expect(api.voice).not.toHaveBeenCalled()
})

test('unmounting cancels any in-progress speech synthesis', () => {
  const cancel = vi.fn()
  vi.spyOn(window.speechSynthesis, 'cancel').mockImplementation(cancel)
  const { unmount } = hook(fakeServices())
  unmount()
  expect(cancel).toHaveBeenCalled()
})

test('unmounting is safe when the browser has no speechSynthesis at all', () => {
  const original = window.speechSynthesis
  // @ts-expect-error -- simulating a browser without the Web Speech API
  delete window.speechSynthesis
  const { unmount } = hook(fakeServices())
  expect(() => unmount()).not.toThrow()
  Object.defineProperty(window, 'speechSynthesis', { value: original, configurable: true })
})
