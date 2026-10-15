import { normalizeBundle, type ProjectBundle } from '@/lib/types'
import hallASigned from '@/test/fixtures/hall-a-signed.json'
import { buildSldGraph, NODE_SIZE } from './sldGraph'
import { edgeAppearance, initialFit } from './sldFit'

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
})

test('D8: a failing feeder is a thick rose line with a large "✕ Fail" label on a tinted pill; a passing one stays quiet', () => {
  const fail = edgeAppearance({ status: 'fail', change: null, chain: null, label: 'FA-01' })
  expect(fail.strokeWidth).toBeGreaterThanOrEqual(3)
  expect(fail.label).toBe('FA-01 · ✕ Fail')
  expect(fail.labelStyle.fontSize).toBeGreaterThanOrEqual(12)
  expect(fail.labelBgStyle.stroke).toBe('#fb7185')
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
