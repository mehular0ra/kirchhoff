/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { screen, within } from '@testing-library/react'
import { renderWithProviders } from '@/test/render'
import { Landing } from './Landing'

/** Width and height of a PNG, read from its IHDR chunk (and the 8-byte signature checked), so a lossy or tiny replacement is caught. */
function pngSize(file: string): { w: number; h: number } {
  const b = readFileSync(`${process.cwd()}/public/landing/${file}`)
  expect(b.subarray(0, 8).toString('hex')).toBe('89504e470d0a1a0a')
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) }
}

// The landing page's structure (YC-style: nav, hero, product, features, how it works, trust, closing call to action). Copy is checked where it is
// a contract: the e2e tour starts from "Enter the demo workspace (no login)" and "Run it live", so each must exist exactly once.

/** Width and height of a lossless WebP (VP8L: 14 bits each, minus one). A lossy file has another chunk type and fails the first check. */
function webpLosslessSize(file: string): { w: number; h: number } {
  const b = readFileSync(`${process.cwd()}/public/landing/${file}`)
  expect(b.subarray(0, 4).toString()).toBe('RIFF')
  expect(b.subarray(8, 12).toString()).toBe('WEBP')
  expect(b.subarray(12, 16).toString()).toBe('VP8L')
  const bits = b.readUInt32LE(21)
  return { w: (bits & 0x3fff) + 1, h: ((bits >> 14) & 0x3fff) + 1 }
}

test('the nav is a landmark with anchors to three sections and a way into the demo', () => {
  renderWithProviders(<Landing />)
  const nav = screen.getByRole('navigation', { name: 'Landing' })
  const links = within(nav).getAllByRole('link')
  // the logo's own "#top" link is not one of the section anchors
  const anchors = links.filter((a) => a.getAttribute('href')?.startsWith('#') && a.getAttribute('href') !== '#top')
  expect(anchors.map((a) => a.textContent)).toEqual(['How it works', 'What it does', 'Why trust the numbers'])
  // every anchor lands on a section that exists
  for (const a of anchors) expect(document.getElementById(a.getAttribute('href')!.slice(1))).not.toBeNull()
  expect(within(nav).getByRole('link', { name: 'Open the demo' })).toHaveAttribute('href', '/app')
})

test('the headline is one plain run of text, not one phrase picked out in another style', () => {
  renderWithProviders(<Landing />)
  const h1 = screen.getByRole('heading', { level: 1 })
  expect(h1).toHaveTextContent('Weeks of senior-engineer design work, in one reviewed, signed session.')
  expect(h1.children).toHaveLength(0)
})

test('the contract links the e2e tour depends on exist exactly once, and the demo labels are in the footer', () => {
  renderWithProviders(<Landing />)
  expect(screen.getAllByRole('link', { name: /Enter the demo workspace/ })).toHaveLength(1)
  expect(screen.getAllByRole('link', { name: 'Run it live' })).toHaveLength(1)
  expect(screen.getByText(/all companies, people and data are fictional/i)).toBeInTheDocument()
  expect(screen.getByText(/illustrative values, not for construction/i)).toBeInTheDocument()
})

test('the product window has a legend that says what the three areas of the screenshot are', () => {
  renderWithProviders(<Landing />)
  const legend = screen.getByRole('list', { name: 'What the screenshot shows' })
  const items = within(legend).getAllByRole('listitem')
  expect(items).toHaveLength(3)
  // each item is its own glass card with a small map of the screenshot's three columns, the item's column filled: left, centre, right
  for (const li of items) expect(li.className).toMatch(/(^|\s)glass(\s|$)/)
  expect(items.map((li) => li.querySelector('svg[aria-hidden="true"]')?.getAttribute('data-at'))).toEqual(['left', 'centre', 'right'])
  expect(items.map((li) => li.querySelector('p')?.textContent)).toEqual(['Agent lanes', '3D hall', 'Co-pilot'])
  expect(screen.getByRole('img', { name: /Hall A \(sample\)/ })).toBeInTheDocument()
})

test('the product screenshot is lossless (a WebP first, the same pixels as a PNG fallback), with at least two pixels per shown pixel, and narrow screens get a sharper crop of the 3D column', () => {
  const { container } = renderWithProviders(<Landing />)
  const img = screen.getByRole('img', { name: /Hall A \(sample\)/ })
  expect(img).toHaveAttribute('src', '/landing/hall-a-r2.png')
  const sources = Array.from(container.querySelectorAll('picture > source')).map((s) => [s.getAttribute('media'), s.getAttribute('type'), s.getAttribute('srcset')])
  expect(sources).toEqual([
    ['(max-width: 639px)', 'image/webp', '/landing/hall-a-r2-phone.webp'],
    ['(max-width: 639px)', null, '/landing/hall-a-r2-phone.png'],
    [null, 'image/webp', '/landing/hall-a-r2.webp'],
  ])

  // shown up to 1176 px wide on desktop, and about 360 px wide on a phone
  const desktop = pngSize('hall-a-r2.png')
  expect(desktop.w).toBeGreaterThanOrEqual(2 * 1152)
  expect(desktop.w / desktop.h).toBeCloseTo(16 / 10, 2)
  const phone = pngSize('hall-a-r2-phone.png')
  expect(phone.w).toBeGreaterThanOrEqual(2 * 360)
  // the WebP files are lossless and exactly the PNGs' size (a lossy re-encode is what blurred the text before)
  expect(webpLosslessSize('hall-a-r2.webp')).toEqual(desktop)
  expect(webpLosslessSize('hall-a-r2-phone.webp')).toEqual(phone)
  // the img reserves the phone crop's shape on a phone (no stretching), and the desktop shape from `sm` up
  expect(img.className).toContain(`max-sm:aspect-[${phone.w / 12}/${phone.h / 12}]`)
})

test('the Google Cloud stack is five equal glass tiles, each an icon over a name, under a strong label, with no hairline separators', () => {
  renderWithProviders(<Landing />)
  const stack = screen.getByRole('list', { name: 'Built on' })
  const tiles = within(stack).getAllByRole('listitem')
  expect(tiles.map((li) => li.textContent)).toEqual(['Gemini on Vertex AI', 'Agent Development Kit', 'Cloud Run', 'Firestore', 'Firebase'])
  // an icon over every name (decorative), and one class string for all five, so no tile looks different from its neighbours
  for (const li of tiles) expect(li.querySelector('svg[aria-hidden="true"]')).not.toBeNull()
  expect(new Set(tiles.map((li) => li.className)).size).toBe(1)
  // each tile is its own frosted glass (not one panel cut by lines), so there are no dividers between them
  for (const li of tiles) expect(li.className).toMatch(/(^|\s)glass(\s|$)/)
  expect(stack.className).not.toMatch(/divide-/)
  expect(stack.closest('.glass-strong')).toBeNull()
  // the label is the heading line of the group: full foreground colour and semibold, not a plain grey caption, and no rule under it
  const label = screen.getByText('Built on Google Cloud')
  expect(label.parentElement).toContainElement(stack)
  expect(label.className).toMatch(/\btext-foreground\b/)
  expect(label.className).toMatch(/\bfont-semibold\b/)
  expect(label.className).not.toMatch(/\bborder-/)
})

test('"What Kirchhoff does" lists the features: a lead feature and five more', () => {
  renderWithProviders(<Landing />)
  const section = screen.getByRole('region', { name: 'What Kirchhoff does' })
  expect(within(section).getByRole('heading', { level: 3, name: /checked by code/i })).toBeInTheDocument()
  const list = within(section).getByRole('list', { name: 'More of what it does' })
  expect(within(list).getAllByRole('listitem')).toHaveLength(5)
})

test('"How it works" is an ordered list of the three real steps', () => {
  renderWithProviders(<Landing />)
  const steps = screen.getByRole('list', { name: 'How it works' })
  expect(steps.tagName).toBe('OL')
  expect(within(steps).getAllByRole('listitem').map((li) => li.querySelector('p')?.textContent)).toEqual(['Agents design', 'Physics checks', 'An engineer signs'])
})

test('"Why trust the numbers" gives three principles, and the closing call to action opens the demo', () => {
  renderWithProviders(<Landing />)
  const trust = screen.getByRole('region', { name: 'Why you can trust the numbers' })
  expect(within(trust).getAllByRole('heading', { level: 3 })).toHaveLength(3)
  const cta = screen.getByRole('region', { name: 'See a signed design, or run one yourself' })
  expect(within(cta).getByRole('link', { name: 'Open the demo workspace' })).toHaveAttribute('href', '/app')
  expect(within(cta).getByRole('link', { name: 'Run Hall B live' })).toHaveAttribute('href', '/app/p/hall-b')
})

test('a keyboard user can skip the nav', () => {
  renderWithProviders(<Landing />)
  expect(screen.getByRole('link', { name: 'Skip to content' })).toHaveAttribute('href', '#main')
})
