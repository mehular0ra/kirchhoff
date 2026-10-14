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

afterEach(() => {
  cleanup()
  localStorage.clear()
  sessionStorage.clear()
  vi.useRealTimers()
})
