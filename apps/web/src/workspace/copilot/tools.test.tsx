import { renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { fmtNum, fmtQty } from '@/lib/format'
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
  expect(out.check).toBe('Details of FA-01')
  expect(out.actions).toHaveLength(1)
  expect(out.actions[0]).toMatch(/^Showing FA-01 on the (3D hall|SLD|3D hall and the SLD)$/)
})

// ---- "what is the power of rack R1-01?": the answer is the engine's record of the element, not just "Showing R1-01".

const modelOf = (view: ReturnType<typeof viewOf>) => view.model!

test('a rack comes back with its row, power, liquid fraction and feeds, from the model', async () => {
  const view = viewOf()
  const rack = modelOf(view).racks.find((r) => r.id === 'R1-01')!
  const out = await executeTool('focus_element', { element_id: 'R1-01' }, ctxFor(view))
  expect(out.check).toBe('Details of R1-01')
  expect(out.summary).toBe(`Rack R1-01 (row ${rack.row}): ${fmtQty(rack.kw, 'kW')}, liquid fraction ${fmtNum(rack.liquid_fraction)}, fed by ${rack.feeds.join(' and ')}.`)
  expect(out.data).toMatchObject({ element_id: 'R1-01', kind: 'rack', row: rack.row, kw: rack.kw, liquid_fraction: rack.liquid_fraction, feeds: rack.feeds })
  // the text Gemini may speak is the same engine text the card shows
  expect(out.data.text).toBe(out.summary)
  expect(out.actions).toEqual(['Showing R1-01 on the 3D hall and the SLD'])
})

test('a spoken id is read the way it was meant: spaces around the dash and lower case', async () => {
  const ctx = ctxFor(viewOf())
  const out = await executeTool('focus_element', { element_id: 'r1 - 01' }, ctx)
  expect(out.summary).toMatch(/^Rack R1-01 /)
  expect(ctx.focus).toHaveBeenCalledWith('R1-01')
})

test('equipment comes back with its kind, rating, system and room', async () => {
  const view = viewOf()
  const tx = modelOf(view).equipment.find((e) => e.id === 'T-A1')!
  const out = await executeTool('focus_element', { element_id: 'T-A1' }, ctxFor(view))
  expect(out.summary).toBe(`Transformer T-A1: ${fmtQty(tx.rating, tx.unit)}, system ${tx.system}, room ${tx.room}. Checks on it: 1 pass.`)
  expect(out.data).toMatchObject({ kind: 'transformer', rating: tx.rating, unit: tx.unit, system: tx.system, room: tx.room })
})

test('a cooling unit comes back with its zone and capacity', async () => {
  const view = viewOf()
  const cdu = modelOf(view).cooling_nodes.find((n) => n.id === 'CDU-1')!
  const out = await executeTool('focus_element', { element_id: 'CDU-1' }, ctxFor(view))
  expect(out.summary).toBe(`CDU CDU-1 in zone ${cdu.zone}: capacity ${fmtQty(cdu.capacity_kw, 'kW')}. Checks on it: 1 pass.`)
  expect(out.data).toMatchObject({ kind: 'cdu', zone: cdu.zone, capacity_kw: cdu.capacity_kw })
})

test('a feeder comes back with its ends and length, and the checks on it where it failed', async () => {
  const view = viewOf('r1')
  const feeder = modelOf(view).connections.find((c) => c.id === 'FA-01')!
  const out = await executeTool('focus_element', { element_id: 'FA-01' }, ctxFor(view))
  const kind = { cable: 'Cable', busway: 'Busway', internal: 'Internal link' }[feeder.kind]
  expect(out.summary).toContain(`${kind} FA-01: ${feeder.src} to ${feeder.dst}, ${fmtQty(feeder.length_m, 'm')}.`)
  expect(out.summary).toContain('Checks on it: 1 fail, 3 pass.')
  expect(out.summary).toContain('Failing: R05 2.16% vs 2%.')
  expect(out.data).toMatchObject({ kind: feeder.kind, from: feeder.src, to: feeder.dst, length_m: feeder.length_m })
  expect(out.data.checks).toMatchObject({ pass: 3, fail: 1, failing: [{ rule: 'R05', value: 2.1604, limit: 2, unit: '%' }] })
})

test('a pipe comes back with its kind, size and zone, and the check that failed on it', async () => {
  const out = await executeTool('focus_element', { element_id: 'H-Z2' }, ctxFor(viewOf('r1')))
  expect(out.summary).toMatch(/^Pipe H-Z2 \(header, DN\d+\) in zone Z2/)
  expect(out.summary).toContain('Checks on it: 1 fail, 2 pass.')
  expect(out.summary).toContain('Failing: R11 1 crossing vs 0 crossings.')
})

test('a name only the checks use (the bill of quantities) still answers with the checks on it', async () => {
  const out = await executeTool('focus_element', { element_id: 'BOQ' }, ctxFor(viewOf('r1'), { focus: vi.fn(() => false) }))
  expect(out.summary).toBe('BOQ is not drawn on the 3D hall or the SLD. Checks on it: 1 pass.')
  expect(out.actions).toEqual(['Nothing moved: BOQ is not drawn on a canvas'])
})

test('an id that is not in the design says what the design does have, so the answer is not a dead end', async () => {
  const view = viewOf()
  const racks = modelOf(view).racks
  const out = await executeTool('focus_element', { element_id: 'ZZ-99' }, ctxFor(view, { focus: vi.fn(() => false) }))
  expect(out.summary).toBe(`ZZ-99 is not in this design. It has ${racks.length} racks (${racks[0].id} to ${racks[racks.length - 1].id}); ask about a rack, a feeder, a board or a CDU by its id.`)
  expect(out.data).toMatchObject({ element_id: 'ZZ-99', error: 'not_found', racks: racks.length })
  expect(out.actions).toEqual(['Nothing moved: ZZ-99 is not drawn on a canvas'])
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
