import { fireEvent, render, screen } from '@testing-library/react'
import { fixtureBundle } from '@/test/fixtures'
import { useUi } from '@/store/ui'
import { WorkspaceProvider } from '../WorkspaceContext'
import { SldView } from './SldView'

// The staged top-down reveal is time-based (spec §12); force it to show every level at once so
// keyboard/click tests don't need to wait out the stagger, same as a reduced-motion visitor sees.
// ELK itself is covered by sldGraph.test.ts; here a deterministic grid layout keeps these UI tests
// fast and independent of loading a 1.4 MB layout engine under full-suite load (it timed out cold).
const layoutCtl = vi.hoisted(() => ({ hold: false }))
vi.mock('./sldGraph', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./sldGraph')>()
  return {
    ...actual,
    layoutSld: (g: ReturnType<typeof actual.buildSldGraph>) =>
      layoutCtl.hold
        ? new Promise(() => {}) // a layout still computing
        : Promise.resolve(new Map(g.nodes.map((n, i) => [n.id, { x: (i % 6) * 160, y: n.level * 100 }]))),
  }
})

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

test('backlog [1] / M11: Enter on the node a failing feeder ends at opens that feeder finding; the label carries status', async () => {
  useUi.getState().resetWorkspaceUi()
  useUi.getState().setViewRev('r1')
  render(
    <WorkspaceProvider bundle={fixtureBundle()} source="static">
      <SldView />
    </WorkspaceProvider>,
  )
  const node = await screen.findByRole('button', { name: /^A-01/ })
  expect(node).toHaveAccessibleName('A-01: Pass, feeder FA-01: Fail')
  fireEvent.keyDown(node, { key: 'Enter' })
  expect(useUi.getState().findingId).toBe('R05:FA-01')
})

test('backlog [2]: while a new revision is being laid out, a node without a position is not drawn at a stale/origin spot', async () => {
  useUi.getState().resetWorkspaceUi()
  const b = fixtureBundle()
  const { rerender } = render(
    <WorkspaceProvider bundle={b} source="static">
      <SldView />
    </WorkspaceProvider>,
  )
  await screen.findByRole('button', { name: /^MV/ })
  layoutCtl.hold = true
  const r2 = b.revisions[1]
  const added = { ...r2, model: { ...r2.model!, equipment: [...r2.model!.equipment, { ...r2.model!.equipment[1], id: 'T-NEW' }] } }
  rerender(
    <WorkspaceProvider bundle={{ ...b, revisions: [b.revisions[0], added] }} source="static">
      <SldView />
    </WorkspaceProvider>,
  )
  await new Promise((r) => setTimeout(r, 50))
  expect(screen.queryByRole('button', { name: /^T-NEW/ })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: /^MV/ })).toBeInTheDocument() // known nodes keep their place
  layoutCtl.hold = false
})
