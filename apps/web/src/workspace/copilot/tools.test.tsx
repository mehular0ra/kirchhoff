import { renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { revisionLabel } from '@/lib/select'
import { normalizeBundle, type ProjectBundle } from '@/lib/types'
import { ServicesProvider } from '@/services/services'
import { useUi } from '@/store/ui'
import hallASigned from '@/test/fixtures/hall-a-signed.json'
import { fakeApi, fakeServices, resetStores } from '@/test/render'
import { useWorkspace, WorkspaceProvider } from '../WorkspaceContext'
import { executeTool, type ToolContext } from './tools'

const realHallA = () => normalizeBundle(structuredClone(hallASigned) as unknown as ProjectBundle)

/** The workspace view of Hall A, as the tools see it. `rev` picks the revision on screen (default: the latest, r2). */
function viewOf(rev?: string) {
  resetStores()
  if (rev) useUi.getState().setViewRev(rev)
  const wrapper = ({ children }: { children: ReactNode }) => (
    <ServicesProvider services={fakeServices()}>
      <WorkspaceProvider bundle={realHallA()} source="static">
        {children}
      </WorkspaceProvider>
    </ServicesProvider>
  )
  return renderHook(() => useWorkspace(), { wrapper }).result.current
}

const ctxFor = (view: ReturnType<typeof viewOf>, over: Partial<ToolContext> = {}): ToolContext => ({
  view,
  api: fakeApi(),
  runWhatIf: vi.fn(),
  focus: vi.fn(() => true),
  openFinding: vi.fn(),
  setViewRev: vi.fn(),
  ...over,
})

afterEach(() => vi.useRealTimers())

test('explain on the signed r2 walks back to r1 and says so, and says it opened the finding', async () => {
  const view = viewOf()
  const ctx = ctxFor(view)
  const out = await executeTool('explain_finding', { finding_id: 'R05:FA-01' }, ctx)
  const r1 = view.bundle.revisions.find((r) => r.id === 'r1')!
  expect(out.check).toBe('Explain finding R05 · FA-01')
  expect(out.actions).toEqual([`Switched to ${revisionLabel(r1)}, where this check failed`, 'Opened R05 · FA-01 in the finding drawer'])
  expect(ctx.setViewRev).toHaveBeenCalledWith('r1', { source: 'auto' })
  expect(ctx.openFinding).toHaveBeenCalledWith('R05:FA-01')
})

test('explain on the revision where the check failed switches nothing and says only what it opened', async () => {
  const ctx = ctxFor(viewOf('r1'))
  const out = await executeTool('explain_finding', { finding_id: 'R11:H-Z2' }, ctx)
  expect(out.check).toBe('Explain finding R11 · H-Z2')
  expect(out.actions).toEqual(['Opened R11 · H-Z2 in the finding drawer'])
  expect(ctx.setViewRev).not.toHaveBeenCalled()
})

test('explain for something that is not there changes nothing and says so', async () => {
  const ctx = ctxFor(viewOf())
  const out = await executeTool('explain_finding', { element_id: 'ZZ-99' }, ctx)
  expect(out.summary).toBe('No finding for ZZ-99 in this revision.')
  expect(out.check).toBe('Explain finding ZZ-99')
  expect(out.actions).toEqual([])
  expect(ctx.openFinding).not.toHaveBeenCalled()
})

test('explain uses the language model\'s rewrite when it comes back in time, with the finding\'s own numbers', async () => {
  const explain = vi.fn(async () => ({ text: 'Rewritten: FA-01 drops {value} against {limit}.' }))
  const out = await executeTool('explain_finding', { finding_id: 'R05:FA-01' }, ctxFor(viewOf('r1'), { api: fakeApi({ explain }) }))
  expect(out.summary).toBe('Rewritten: FA-01 drops 2.16% against 2%.')
})

test('a slow rewrite never holds the answer: after a few seconds the engine\'s own explanation stands', async () => {
  vi.useFakeTimers()
  const explain = vi.fn(() => new Promise<{ text: string }>(() => undefined)) // never answers
  const pending = executeTool('explain_finding', { finding_id: 'R05:FA-01' }, ctxFor(viewOf('r1'), { api: fakeApi({ explain }) }))
  await vi.advanceTimersByTimeAsync(4_000)
  const out = await pending
  expect(explain).toHaveBeenCalled()
  expect(out.summary).toMatch(/^Voltage drop .* via FA-01 is 2\.16% against a limit of 2%\./)
  expect(out.actions).toContain('Opened R05 · FA-01 in the finding drawer')
})

test('focus says which canvases it is showing the element on', async () => {
  const ctx = ctxFor(viewOf())
  const out = await executeTool('focus_element', { element_id: 'fa-01' }, ctx)
  expect(out.check).toBe('Show FA-01')
  expect(out.summary).toBe('Showing FA-01.')
  expect(out.actions).toHaveLength(1)
  expect(out.actions[0]).toMatch(/^Showing FA-01 on the (3D hall|SLD|3D hall and the SLD)$/)
})

test('focus on something no canvas draws says nothing moved', async () => {
  const ctx = ctxFor(viewOf(), { focus: vi.fn(() => false) })
  const out = await executeTool('focus_element', { element_id: 'BOQ' }, ctx)
  expect(out.actions).toEqual(['Nothing moved: BOQ is not drawn on a canvas'])
})

test('a what-if says which revision it ran on, that nothing was saved, and where the result is', async () => {
  const view = viewOf()
  const rev = view.bundle.revisions[view.bundle.revisions.length - 1]
  const runWhatIf = vi.fn(async () => ({ rev, result: { findings: [], impact_chain: [] } }))
  const out = await executeTool('what_if', { param: 'rack_kw', value: 200 }, ctxFor(view, { runWhatIf: runWhatIf as unknown as ToolContext['runWhatIf'] }))
  expect(out.check).toBe('What-if: Racks → 200 kW')
  expect(out.summary).toBe(`On ${revisionLabel(rev)}: no check fails.`)
  expect(out.actions).toEqual([`Ran on ${revisionLabel(rev)}; engine only, nothing saved`, 'The result is in the What-if panel and lit on the canvases'])
})

test.each([
  ['liquid_fraction', 0.9, 'What-if: Liquid fraction → 0.9'],
  ['dv_limit_pct', 1.5, 'What-if: ΔV limit → 1.5%'],
  ['tx_loading_cap_pct', 35, 'What-if: Transformer loading cap → 35%'],
])('the what-if check names its parameter the way the chips do: %s', async (param, value, label) => {
  const view = viewOf()
  const rev = view.bundle.revisions[view.bundle.revisions.length - 1]
  const runWhatIf = vi.fn(async () => ({ rev, result: { findings: [], impact_chain: [] } }))
  const out = await executeTool('what_if', { param, value }, ctxFor(view, { runWhatIf: runWhatIf as unknown as ToolContext['runWhatIf'] }))
  expect(out.check).toBe(label)
})

test('a what-if the tools do not support, or an unreachable engine, changes nothing', async () => {
  const view = viewOf()
  const unsupported = await executeTool('what_if', { param: 'nonsense', value: 1 }, ctxFor(view))
  expect(unsupported).toMatchObject({ summary: 'That what-if is not supported.', actions: [] })
  const unreachable = await executeTool('what_if', { param: 'rack_kw', value: 200 }, ctxFor(view, { runWhatIf: vi.fn(async () => null) }))
  expect(unreachable).toMatchObject({ summary: 'The engine is unreachable for that what-if.', actions: [] })
})

test('an unknown tool changes nothing', async () => {
  const out = await executeTool('delete_everything', {}, ctxFor(viewOf()))
  expect(out).toMatchObject({ summary: 'Unknown tool delete_everything.', actions: [] })
})
