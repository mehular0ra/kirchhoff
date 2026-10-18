/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

// Read straight from disk (a Vite CSS import is empty under vitest's `css: false`); vitest runs with apps/web as its root.
const css = readFileSync(`${process.cwd()}/src/index.css`, 'utf8')

/**
 * The light theme's glass surfaces must keep WCAG AA: text on a translucent surface is checked against the WORST backdrop it can sit on
 * (the plain canvas and the strongest blue and amber washes), and the decorative circuit traces must still be visible (3:1 graphical contrast).
 * The numbers are read from src/index.css, so a later palette tweak that breaks contrast fails here.
 */
const root = css.slice(css.indexOf(':root'), css.indexOf('}', css.indexOf(':root')))

type RGBA = [number, number, number, number]

function token(name: string): RGBA {
  const m = root.match(new RegExp(`--${name}:\\s*([^;]+);`))
  if (!m) throw new Error(`--${name} is not defined in :root of src/index.css`)
  const v = m[1].trim()
  if (v.startsWith('#')) {
    const h = v.length === 4 ? [...v.slice(1)].map((c) => c + c).join('') : v.slice(1)
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16), 1]
  }
  const r = v.match(/rgb\(\s*(\d+)\s+(\d+)\s+(\d+)(?:\s*\/\s*([\d.]+))?\s*\)/)
  if (!r) throw new Error(`--${name}: cannot read "${v}"`)
  return [+r[1], +r[2], +r[3], r[4] === undefined ? 1 : +r[4]]
}

const over = (top: RGBA, bottom: RGBA): RGBA => {
  const a = top[3]
  return [0, 1, 2].map((i) => Math.round(top[i] * a + bottom[i] * (1 - a))).concat(1) as RGBA
}
const lum = ([r, g, b]: RGBA) => {
  const f = (c: number) => ((c /= 255) <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
}
const ratio = (a: RGBA, b: RGBA) => {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

// What a glass panel can sit on: the canvas, and the two strongest washes of the page backdrop.
const BACKDROPS = ['canvas', 'wash-blue', 'wash-amber'] as const
const GLASS = ['glass', 'glass-strong'] as const

describe('glass tokens exist', () => {
  it.each(['canvas', 'wash-blue', 'wash-amber', 'glass', 'glass-strong', 'glass-edge', 'trace-blue', 'trace-amber'])('--%s is defined', (name) => {
    expect(() => token(name)).not.toThrow()
  })
  it('defines the glass utility with a backdrop blur and a solid fallback', () => {
    expect(css).toMatch(/@utility glass\b/)
    expect(css).toMatch(/backdrop-filter:\s*blur\(/)
    expect(css).toMatch(/@supports not \(\(backdrop-filter: blur\(1px\)\) or \(-webkit-backdrop-filter: blur\(1px\)\)\)/)
  })
})

describe('text on glass stays AA over the worst backdrop', () => {
  for (const g of GLASS) {
    for (const b of BACKDROPS) {
      const surface = over(token(g), token(b))
      it(`body text on ${g} over ${b} is at least 7:1`, () => {
        expect(ratio(token('foreground'), surface)).toBeGreaterThanOrEqual(7)
      })
      it(`muted text on ${g} over ${b} is at least 4.5:1`, () => {
        expect(ratio(token('muted-foreground'), surface)).toBeGreaterThanOrEqual(4.5)
      })
      it(`accent text on ${g} over ${b} is at least 4.5:1`, () => {
        expect(ratio(token('brand-text'), surface)).toBeGreaterThanOrEqual(4.5)
      })
    }
  }
})

describe('lines and bounding boxes are visible', () => {
  const white: RGBA = [255, 255, 255, 1]
  it('--border (cards, panels, tables, tabs) is at least 1.4:1 against white and against the canvas', () => {
    expect(ratio(token('border'), white)).toBeGreaterThanOrEqual(1.4)
    expect(ratio(token('border'), token('canvas'))).toBeGreaterThanOrEqual(1.2)
  })
  it('--input (form controls) is at least 1.9:1 against white', () => {
    expect(ratio(token('input'), white)).toBeGreaterThanOrEqual(1.9)
  })
})

describe('the decorative circuit traces are visible on light', () => {
  it.each(['trace-blue', 'trace-amber'])('--%s is at least 3:1 against the canvas', (name) => {
    expect(ratio(token(name), token('canvas'))).toBeGreaterThanOrEqual(3)
  })
  it('the glass edge is a visible hairline on the canvas (1.25:1 or more)', () => {
    expect(ratio(over(token('glass-edge'), token('canvas')), token('canvas'))).toBeGreaterThanOrEqual(1.25)
  })
})
