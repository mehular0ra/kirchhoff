import { canvasesFor } from '@/lib/model'
import { fixtureBundle } from '@/test/fixtures'
import { useUi } from './ui'

const model = fixtureBundle().revisions[1].model!

beforeEach(() => useUi.getState().resetWorkspaceUi())

test('I5: focusing from Matrix/Options/Docs switches to a canvas that draws the element', () => {
  const ui = useUi.getState()
  ui.setTab('matrix')
  ui.focus('FA-01', canvasesFor(model, 'FA-01'))
  expect(useUi.getState()).toMatchObject({ tab: 'hall', focusId: 'FA-01' })
  ui.setTab('docs')
  ui.focus('T-A1', canvasesFor(model, 'T-A1')) // transformers are drawn on the SLD only
  expect(useUi.getState().tab).toBe('sld')
  ui.setTab('options')
  ui.focus('A1') // no hint: the 3D hall
  expect(useUi.getState().tab).toBe('hall')
})

test('I5: a canvas that already draws the element stays; one that cannot switches; clearing focus never switches', () => {
  const ui = useUi.getState()
  ui.setTab('sld')
  ui.focus('FA-01', canvasesFor(model, 'FA-01'))
  expect(useUi.getState().tab).toBe('sld')
  ui.focus('H-Z2', canvasesFor(model, 'H-Z2')) // pipes are 3D only
  expect(useUi.getState().tab).toBe('hall')
  ui.setTab('matrix')
  ui.focus(null)
  expect(useUi.getState().tab).toBe('matrix')
})

test('canvasesFor knows which canvas draws which element', () => {
  expect(canvasesFor(model, 'R1-01')).toEqual(['hall', 'sld'])
  expect(canvasesFor(model, 'A-01')).toEqual(['hall', 'sld'])
  expect(canvasesFor(model, 'CB-A1')).toEqual(['sld'])
  expect(canvasesFor(model, 'CDU-1')).toEqual(['hall'])
  expect(canvasesFor(model, 'L-MV-TA1')).toEqual(['sld'])
  expect(canvasesFor(model, 'nope')).toEqual([]) // not in the model: no canvas draws it
})

test('residual: focus() with no canvas that draws the element leaves the tab alone', () => {
  useUi.getState().resetWorkspaceUi()
  useUi.getState().setTab('matrix')
  useUi.getState().focus('BOQ', [])
  expect(useUi.getState().tab).toBe('matrix')
})

test('#37: only a revision-bar pick ("user") is explicit; automatic switches stay "auto" and keep a same-revision pick', () => {
  const ui = useUi.getState()
  expect(useUi.getState().viewRevSource).toBe('auto')
  ui.setViewRev('r1') // D1, a deep link, a lane event, the cold-open shot
  expect(useUi.getState()).toMatchObject({ viewRev: 'r1', viewRevSource: 'auto' })
  ui.setViewRev('r1', { source: 'user' }) // the visitor then clicks r1 in the revision bar: now it is a pick
  expect(useUi.getState()).toMatchObject({ viewRev: 'r1', viewRevSource: 'user' })
  ui.setViewRev('r1', { source: 'auto' }) // an automatic move to the revision already picked keeps the pick
  expect(useUi.getState().viewRevSource).toBe('user')
  ui.setViewRev('r2', { source: 'auto' }) // an automatic move elsewhere is not a pick
  expect(useUi.getState()).toMatchObject({ viewRev: 'r2', viewRevSource: 'auto' })
  ui.setViewRev('r1', { source: 'user' })
  ui.resetWorkspaceUi()
  expect(useUi.getState()).toMatchObject({ viewRev: null, viewRevSource: 'auto' })
})
