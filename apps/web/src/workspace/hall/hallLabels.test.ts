import { fixtureBundle } from '@/test/fixtures'
import type { Finding, WhatIfResult } from '@/lib/types'
import { buildView } from '../WorkspaceContext'
import { buildHallScene } from './hallScene'
import { buildLabels, layoutLabels } from './hallLabels'

const bundle = fixtureBundle()
const scene = buildHallScene(bundle.revisions[1].model!)

function whatIfWith(findings: Pick<Finding, 'rule_id' | 'element_id'>[]): WhatIfResult {
  const base = bundle.what_ifs[0]
  return {
    ...base,
    findings: findings.map((f, i) => ({ ...base.findings[0], id: `${f.rule_id}:${f.element_id}:${i}`, rule_id: f.rule_id, element_id: f.element_id, status: 'fail' })),
  }
}

test('what-if fails collapse to one label per rule, counted from the findings; elements not drawn in 3D get none', () => {
  const result = whatIfWith([
    { rule_id: 'R02', element_id: 'A-01' },
    { rule_id: 'R02', element_id: 'B-01' },
    { rule_id: 'R08', element_id: 'CDU-1' },
    { rule_id: 'R01', element_id: 'T-A1' }, // transformers are SLD-only
  ])
  const v = buildView(bundle, 'static', { viewRev: null, compare: false, whatIf: { result, origin: 'precomputed' } })
  const labels = buildLabels(scene, v).filter((l) => l.kind === 'finding')
  expect(labels.map((l) => l.text)).toEqual(['what-if: Fail · R02 · 2 elements', 'what-if: Fail · R08 · CDU-1'])
})

test('finding labels come first; rooms, bays and the keep-out are lower-priority context labels', () => {
  const v = buildView(bundle, 'static', { viewRev: 'r1', compare: false, whatIf: null })
  const labels = buildLabels(scene, v)
  const kinds = labels.map((l) => l.kind)
  expect(kinds.indexOf('context')).toBeGreaterThan(kinds.lastIndexOf('finding'))
  expect(labels.filter((l) => l.kind === 'finding').map((l) => l.text)).toEqual(['Fail · R05 · FA-01', 'Fail · R11 · H-Z2', 'Warn · R10 · BR-R1'])
  expect(labels.filter((l) => l.kind === 'context').map((l) => l.text)).toEqual(
    expect.arrayContaining(['Keep-out (fire suppression)', 'CDU bay Z2', 'LV room A', 'LV room B']),
  )
})

const box = (id: string, x: number, y: number, kind: 'finding' | 'context', w = 100, h = 20) => ({ id, x, y, w, h, kind })
const overlaps = (a: { x: number; y: number; w: number; h: number }, b: { x: number; y: number; w: number; h: number }) =>
  a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h

test('layout: finding labels anchored at the same spot are stacked without overlap', () => {
  const items = [box('a', 300, 200, 'finding'), box('b', 300, 200, 'finding'), box('c', 305, 203, 'finding')]
  const out = layoutLabels(items, { w: 800, h: 600 })
  const placed = items.map((i) => ({ ...out.get(i.id)!, w: i.w, h: i.h }))
  expect(placed.every((p) => p.visible)).toBe(true)
  for (let i = 0; i < placed.length; i++) for (let j = i + 1; j < placed.length; j++) expect(overlaps(placed[i], placed[j])).toBe(false)
})

test('layout: a context label that would cover a finding label is hidden; clear ones stay', () => {
  const out = layoutLabels([box('f', 300, 200, 'finding'), box('room', 310, 200, 'context'), box('far', 600, 500, 'context')], { w: 800, h: 600 })
  expect(out.get('f')!.visible).toBe(true)
  expect(out.get('room')!.visible).toBe(false)
  expect(out.get('far')!.visible).toBe(true)
})

test('layout: labels stay inside the canvas and anchors behind the camera are hidden', () => {
  const out = layoutLabels([box('edge', 790, 5, 'finding'), { ...box('behind', 100, 100, 'finding'), behind: true }], { w: 800, h: 600 })
  const e = out.get('edge')!
  expect(e.x + 100).toBeLessThanOrEqual(800)
  expect(e.y).toBeGreaterThanOrEqual(0)
  expect(out.get('behind')!.visible).toBe(false)
})

test('with compare on, only the checks that failed in the parent are called out as resolved', () => {
  const v = buildView(bundle, 'static', { viewRev: 'r2', compare: true, whatIf: null })
  const resolved = buildLabels(scene, v).filter((l) => l.text.startsWith('resolved'))
  expect(resolved.map((l) => l.text).sort()).toEqual(['resolved · R05 · FA-01', 'resolved · R11 · H-Z2'])
})
