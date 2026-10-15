import type { WorkspaceView } from './WorkspaceContext'
import { legendKeys } from './legendKeys'

function view(overrides: Partial<WorkspaceView>): WorkspaceView {
  return {
    bundle: null as never,
    source: 'static',
    rev: null,
    parent: null,
    model: null,
    findings: [],
    status: new Map(),
    compare: true,
    diff: null,
    resolved: new Set(),
    whatIf: null,
    highlights: new Map(),
    whatIfStatus: new Map(),
    revRef: null,
    run: null,
    ...overrides,
  }
}

test('the "changed" key shows while comparing against the parent with no what-if active', () => {
  const v = view({ diff: { changes: [{ id: 'FA-01', kind: 'feeder', fields: [] }] } as never, resolved: new Set(['FA-01']) })
  expect(legendKeys(v)).toMatchObject({ diff: true, resolved: true, whatIf: false })
})

test('N7: the "changed" key drops once a what-if is shown, even though the diff against the parent is still there', () => {
  const v = view({
    diff: { changes: [{ id: 'FA-01', kind: 'feeder', fields: [] }] } as never,
    resolved: new Set(['FA-01']),
    whatIf: {} as never,
    highlights: new Map([['FA-01', ['electrical']]]) as never,
  })
  const keys = legendKeys(v)
  expect(keys.whatIf).toBe(true)
  expect(keys.diff).toBe(false)
  expect(keys.resolved).toBe(false)
})
