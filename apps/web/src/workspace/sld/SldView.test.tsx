import { fireEvent, render, screen } from '@testing-library/react'
import { fixtureBundle } from '@/test/fixtures'
import { useUi } from '@/store/ui'
import { WorkspaceProvider } from '../WorkspaceContext'
import { SldView } from './SldView'

// The staged top-down reveal is time-based (spec §12); force it to show every level at once so
// keyboard/click tests don't need to wait out the stagger, same as a reduced-motion visitor sees.
vi.mock('motion/react', async (importOriginal) => {
  const actual = await importOriginal<typeof import('motion/react')>()
  return { ...actual, useReducedMotion: () => true }
})

test('SLD explains itself when there is no revision yet', () => {
  const b = { ...fixtureBundle(), revisions: [], findings: {} }
  render(
    <WorkspaceProvider bundle={b} source="live">
      <SldView />
    </WorkspaceProvider>,
  )
  expect(screen.getByText('No revision yet')).toBeInTheDocument()
})

test('SLD mounts a figure for a revision with a model', () => {
  render(
    <WorkspaceProvider bundle={fixtureBundle()} source="static">
      <SldView />
    </WorkspaceProvider>,
  )
  expect(screen.getByRole('figure', { name: 'Single-line diagram' })).toBeInTheDocument()
})

test('Enter on a focused SLD node opens its worst finding, same as a click', async () => {
  useUi.getState().resetWorkspaceUi()
  render(
    <WorkspaceProvider bundle={fixtureBundle()} source="static">
      <SldView />
    </WorkspaceProvider>,
  )
  const node = await screen.findByRole('button', { name: 'MV' })
  fireEvent.keyDown(node, { key: 'Enter' })
  expect(useUi.getState().focusId).toBe('MV')
})

test('Space on a focused SLD node runs the same activation and prevents the page from scrolling', async () => {
  useUi.getState().resetWorkspaceUi()
  render(
    <WorkspaceProvider bundle={fixtureBundle()} source="static">
      <SldView />
    </WorkspaceProvider>,
  )
  const node = await screen.findByRole('button', { name: 'T-B1' })
  const event = new KeyboardEvent('keydown', { key: ' ', bubbles: true, cancelable: true })
  fireEvent(node, event)
  expect(useUi.getState().focusId).toBe('T-B1')
  expect(event.defaultPrevented).toBe(true)
})
