import { normalizeBundle, type ProjectBundle } from '@/lib/types'
import hallASigned from '@/test/fixtures/hall-a-signed.json'
import { buildView } from './WorkspaceContext'

const hallA = () => normalizeBundle(structuredClone(hallASigned) as unknown as ProjectBundle)

test('I1: a signed revision with a parent opens with "Compare with parent" on, so the fix story shows on arrival', () => {
  const v = buildView(hallA(), 'static', { viewRev: null, compare: null, whatIf: null })
  expect(v.rev?.id).toBe('r2')
  expect(v.compare).toBe(true)
  expect(v.diff?.changes.length).toBeGreaterThan(0)
  expect([...v.resolved].sort()).toEqual(['FA-01', 'H-Z2'])
})

test('I1: the default never applies without a parent, and an explicit choice wins', () => {
  expect(buildView(hallA(), 'static', { viewRev: 'r1', compare: null, whatIf: null }).compare).toBe(false)
  const off = buildView(hallA(), 'static', { viewRev: null, compare: false, whatIf: null })
  expect(off.compare).toBe(false)
  expect(off.diff).toBeNull()
  const b = hallA()
  b.approvals = []
  expect(buildView(b, 'static', { viewRev: null, compare: null, whatIf: null }).compare).toBe(false) // unsigned: off by default
})
