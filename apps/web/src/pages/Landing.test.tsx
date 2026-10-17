import { screen, within } from '@testing-library/react'
import { renderWithProviders } from '@/test/render'
import { Landing } from './Landing'

// The landing page's structure (YC-style: nav, hero, product, features, how it works, trust, closing call to action). Copy is checked where it is
// a contract: the e2e tour starts from "Enter the demo workspace (no login)" and "Run it live", so each must exist exactly once.

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
  expect(within(legend).getAllByRole('listitem')).toHaveLength(3)
  expect(screen.getByRole('img', { name: /Hall A \(sample\)/ })).toBeInTheDocument()
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
