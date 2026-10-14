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
  expect(canvasesFor(model, 'nope')).toEqual(['hall', 'sld'])
})
