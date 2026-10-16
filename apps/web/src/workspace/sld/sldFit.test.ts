import { normalizeBundle, type ProjectBundle } from '@/lib/types'
import hallASigned from '@/test/fixtures/hall-a-signed.json'
import { buildSldGraph, NODE_SIZE } from './sldGraph'
import { edgeAppearance, initialFit, LEGIBLE_ZOOM, topAnchoredViewport } from './sldFit'

const hallA = () => normalizeBundle(structuredClone(hallASigned) as unknown as ProjectBundle)

test('D8: on a revision with a failure on the SLD, the first fit frames that failure (r1: FA-01 between CB-A1 and A-01)', () => {
  const b = hallA()
  const r1 = b.revisions[0]
  const plan = initialFit(buildSldGraph(r1.model!), b.findings.r1)
  expect(plan.nodes).toEqual(['CB-A1', 'A-01'])
  expect(plan.maxZoom).toBeGreaterThanOrEqual(0.9)
})

test('D8: a clean revision fits the whole diagram but never below a legible zoom; the visitor pans for the rest', () => {
  const b = hallA()
  const plan = initialFit(buildSldGraph(b.revisions[1].model!), b.findings.r2)
  expect(plan.nodes).toBeUndefined()
  expect(plan.minZoom).toBeGreaterThanOrEqual(0.8)
  expect(plan.anchorTop).toBe(true) // N3: at the zoom floor, start from the MV bus, not mid-diagram
})

test('N3: when the whole diagram would fit only below the legible zoom, the view starts at the top of the diagram', () => {
  // A diagram much larger than the canvas (Hall A r2: six trains, seven levels)
  const bounds = { x: 0, y: 0, width: 2400, height: 900 }
  const canvas = { width: 880, height: 720 }
  const v = topAnchoredViewport(bounds, canvas, LEGIBLE_ZOOM, 24)!
  expect(v.zoom).toBe(LEGIBLE_ZOOM)
  expect(v.y).toBe(24) // the diagram's top edge sits 24 px below the canvas top
  expect(v.x).toBe(24) // and its left edge 24 px in: the MV bus starts the top row at the left, so it is on screen
  // offset bounds are honoured
  const shifted = topAnchoredViewport({ x: 100, y: 50, width: 2400, height: 900 }, canvas, LEGIBLE_ZOOM, 24)!
  expect(shifted.y).toBeCloseTo(24 - 50 * LEGIBLE_ZOOM)
  expect(shifted.x).toBeCloseTo(24 - 100 * LEGIBLE_ZOOM)
})

test('N3: a diagram that fits at a legible zoom keeps the usual whole-diagram fit', () => {
  expect(topAnchoredViewport({ x: 0, y: 0, width: 600, height: 400 }, { width: 880, height: 720 }, LEGIBLE_ZOOM, 24)).toBeNull()
})

test('D8: a failing feeder is a thick rose line with a large "✕ Fail" label on a tinted pill; a passing one stays quiet', () => {
  const fail = edgeAppearance({ status: 'fail', change: null, chain: null, label: 'FA-01' })
  expect(fail.strokeWidth).toBeGreaterThanOrEqual(3)
  expect(fail.label).toBe('FA-01 · ✕ Fail')
  expect(fail.labelStyle.fontSize).toBeGreaterThanOrEqual(12)
  expect(fail.labelBgStyle.stroke).toBe('#e11d48')
  const pass = edgeAppearance({ status: 'pass', change: null, chain: null, label: 'FA-02' })
  expect(pass.label).toBe('FA-02')
  expect(pass.strokeWidth).toBeLessThan(fail.strokeWidth)
  expect(pass.labelStyle.fontSize).toBeGreaterThanOrEqual(11)
  expect(edgeAppearance({ status: 'pass', change: 'changed', chain: null, label: 'FA-01' }).label).toBe('FA-01 · changed')
})

test('D8: nodes are wide enough for 12 px sub-labels like "3,150 kVA · TX-3150"', () => {
  const chars = '3,150 kVA · TX-3150'.length
  expect(NODE_SIZE.transformer.w).toBeGreaterThanOrEqual(chars * 7.2 + 16)
  expect(NODE_SIZE.ups.w).toBeGreaterThanOrEqual('2,500 kW · UPS-500'.length * 7.2 + 16)
})
