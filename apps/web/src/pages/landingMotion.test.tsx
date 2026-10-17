import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import { renderWithProviders } from '@/test/render'
import { Landing } from './Landing'
import { AREAS } from './shotAreas'

// The landing's motion (all of it in landingMotion.tsx, so it can be taken out as one piece): one entrance sequence for the hero, the check grid sweeping in, the
// step cards and their connector traces drawing in order, a highlight on the screenshot when a legend card is hovered, and a hover lift on small glass cards.
// Under "reduce motion" every part is in its final state from the first frame (nothing starts hidden or shrunk).

const pref = vi.hoisted(() => ({ reduce: false }))
vi.mock('motion/react', async (orig) => ({ ...(await orig<typeof import('motion/react')>()), useReducedMotion: () => pref.reduce }))

// jsdom has no IntersectionObserver; a stub that never reports an element in view keeps the scroll-triggered parts in their starting state, as before a scroll.
class NeverInView {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return []
  }
}
beforeAll(() => {
  vi.stubGlobal('IntersectionObserver', NeverInView)
})
afterAll(() => {
  vi.unstubAllGlobals()
})

const cells = () => Array.from(document.querySelectorAll<HTMLElement>('[data-check-grid] > span'))
const links = () => Array.from(document.querySelectorAll<HTMLElement>('[data-step-link]'))

describe('motion allowed', () => {
  beforeEach(() => {
    pref.reduce = false
  })

  test('the hero text starts hidden and enters as one sequence; the product window only rises, so its image is painted from the first frame', () => {
    renderWithProviders(<Landing />)
    expect(screen.getByRole('heading', { level: 1 }).style.opacity).toBe('0')
    const figure = screen.getByRole('figure')
    expect(figure.style.transform).toContain('translateY(28px)')
    expect(figure.style.opacity).toBe('')
  })

  test('the check grid starts empty and fills cell by cell: 60 cells, two of them the flagged ones', () => {
    renderWithProviders(<Landing />)
    expect(cells()).toHaveLength(60)
    expect(cells().every((c) => c.style.opacity === '0')).toBe(true)
    expect(cells().filter((c) => c.className.includes('bg-rose-500'))).toHaveLength(2)
  })

  test('each step card and the trace to the next one start undrawn', () => {
    renderWithProviders(<Landing />)
    expect(links()).toHaveLength(2) // between 1-2 and 2-3, none after the last card
    for (const l of links()) expect(l.style.transform).toContain('scaleX(0)')
    for (const li of within(screen.getByRole('list', { name: 'How it works' })).getAllByRole('listitem')) expect(li.style.opacity).toBe('0')
  })
})

describe('a browser that cannot observe the viewport', () => {
  test('the scroll-triggered parts are plain and visible instead of waiting for a signal that never comes', () => {
    pref.reduce = false
    vi.stubGlobal('IntersectionObserver', undefined)
    renderWithProviders(<Landing />)
    expect(cells().some((c) => c.style.opacity === '0')).toBe(false)
    for (const l of links()) expect(l.style.transform).toBe('')
    for (const li of within(screen.getByRole('list', { name: 'How it works' })).getAllByRole('listitem')) expect(li.style.opacity).toBe('')
    vi.stubGlobal('IntersectionObserver', NeverInView)
  })
})

describe('reduce motion', () => {
  beforeEach(() => {
    pref.reduce = true
  })

  test('nothing starts hidden, shrunk or undrawn', () => {
    renderWithProviders(<Landing />)
    expect(screen.getByRole('heading', { level: 1 }).style.opacity).toBe('')
    expect(screen.getByRole('figure').style.transform).toBe('')
    expect(cells()).toHaveLength(60)
    expect(cells().some((c) => c.style.opacity === '0' || c.style.transform !== '')).toBe(false)
    expect(cells().filter((c) => c.className.includes('bg-rose-500'))).toHaveLength(2)
    expect(links()).toHaveLength(2)
    for (const l of links()) expect(l.style.transform).toBe('')
    for (const li of within(screen.getByRole('list', { name: 'How it works' })).getAllByRole('listitem')) expect(li.style.opacity).toBe('')
  })
})

describe('hover', () => {
  test('hovering a legend card lights up the area of the screenshot it describes, and only that one', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Landing />)
    const legend = within(screen.getByRole('list', { name: 'What the screenshot shows' })).getAllByRole('listitem')
    const active = () => Array.from(document.querySelectorAll('[data-highlight]')).map((el) => `${el.getAttribute('data-highlight')}:${el.getAttribute('data-active')}`)
    expect(active()).toEqual(['left:false', 'centre:false', 'right:false'])
    await user.hover(legend[1])
    expect(active()).toEqual(['left:false', 'centre:true', 'right:false'])
    await user.hover(legend[2])
    expect(active()).toEqual(['left:false', 'centre:false', 'right:true'])
    await user.unhover(legend[2])
    expect(active()).toEqual(['left:false', 'centre:false', 'right:false'])
    // each highlight is the measured area of the screenshot (see shotAreas.ts), not a hand-typed copy
    for (const at of ['left', 'centre', 'right'] as const) {
      const box = document.querySelector<HTMLElement>(`[data-highlight="${at}"]`)!
      expect([box.style.left, box.style.top, box.style.width, box.style.height]).toEqual([AREAS[at].left, AREAS[at].top, AREAS[at].width, AREAS[at].height])
    }
    // decorative: the highlight layer is hidden from assistive technology and never takes the pointer
    const layer = document.querySelector('[data-highlight]')!.parentElement!
    expect(layer).toHaveAttribute('aria-hidden', 'true')
    expect(layer.className).toContain('pointer-events-none')
  })

  test('the small glass cards lift on hover, and only when motion is allowed', () => {
    renderWithProviders(<Landing />)
    const small = [
      ...within(screen.getByRole('list', { name: 'What the screenshot shows' })).getAllByRole('listitem'),
      ...within(screen.getByRole('list', { name: 'Built on' })).getAllByRole('listitem'),
    ]
    expect(small).toHaveLength(8)
    for (const li of small) {
      expect(li.className).toMatch(/hover:-translate-y-/)
      expect(li.className).toMatch(/motion-reduce:hover:translate-y-0/)
      expect(li.className).toMatch(/motion-reduce:transition-none/)
    }
  })
})
