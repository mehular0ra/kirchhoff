import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// jsdom lacks these browser APIs; Radix (Popover/Tooltip/Sheet) and React Flow call them.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver

class DOMMatrixReadOnlyStub {
  m22 = 1
}
;(globalThis as Record<string, unknown>).DOMMatrixReadOnly ??= DOMMatrixReadOnlyStub

if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList
}
Element.prototype.scrollIntoView ??= function scrollIntoView() {}
Element.prototype.hasPointerCapture ??= () => false
Element.prototype.releasePointerCapture ??= () => {}
window.scrollTo = (() => {}) as typeof window.scrollTo

// jsdom has no media/speech APIs. These are inert stubs so canRecord() reports true (as it would
// in a real browser) and the co-pilot's push-to-talk/speech-synthesis code paths can be exercised
// in tests without ever touching a real microphone or Live session (none of these record audio).
class MediaRecorderStub {
  static isTypeSupported() {
    return true
  }
  ondataavailable: ((e: { data: Blob }) => void) | null = null
  onstop: (() => void) | null = null
  start() {}
  stop() {
    this.ondataavailable?.({ data: new Blob() })
    this.onstop?.()
  }
}
;(globalThis as Record<string, unknown>).MediaRecorder ??= MediaRecorderStub
if (!navigator.mediaDevices) {
  Object.defineProperty(navigator, 'mediaDevices', {
    value: { getUserMedia: async () => ({ getTracks: () => [] }) },
    configurable: true,
  })
}
if (!window.speechSynthesis) {
  Object.defineProperty(window, 'speechSynthesis', {
    value: { cancel: () => {}, speak: () => {} },
    configurable: true,
  })
}
;(globalThis as Record<string, unknown>).SpeechSynthesisUtterance ??= class {
  text: string
  constructor(text: string) {
    this.text = text
  }
}

afterEach(() => {
  cleanup()
  localStorage.clear()
  sessionStorage.clear()
  vi.useRealTimers()
})
