import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TooltipProvider } from '@/components/ui/tooltip'
import type { Bundle, RunEvent } from '@/lib/types'
import { fixtureBundle } from '@/test/fixtures'
import { resetStores } from '@/test/render'
import { AgentLanes } from './AgentLanes'
import { WorkspaceProvider } from './WorkspaceContext'

function renderLanes(bundle: Bundle) {
  resetStores()
  return render(
    <TooltipProvider>
      <WorkspaceProvider bundle={bundle} source="static">
        <AgentLanes />
      </WorkspaceProvider>
    </TooltipProvider>,
  )
}

const ev = (seq: number, agent: RunEvent['agent'], tool: string, summary: Record<string, unknown>): RunEvent => ({
  seq,
  phase: 'p3',
  step: `p3.${tool}`,
  attempt: 1,
  agent,
  kind: 'tool_result',
  title: `${tool} done`,
  detail: '',
  payload: { tool, summary },
  ts: 1760000600 + seq,
})

test('I2: tool results with WS2 list/dict summaries read as counts, never [object Object]', async () => {
  const user = userEvent.setup()
  const b = fixtureBundle()
  // Shapes from services/api/kirchhoff/runs/phase{2,3}.py.
  b.events = [
    ...b.events,
    ev(901, 'cooling', 'route_pipes', { pipes: { 'H-Z1': 'pipe_high', 'H-Z2': 'pipe_low', 'BR-R1': 'pipe_low' } }),
    ev(902, 'layout', 'detect_clashes', { count: 1, clashes: [{ a: 'H-Z2', b: 'FB-03' }] }),
    ev(903, 'power', 'fix_candidates', { finding_id: 'R05:FA-01', candidates: [{ id: 'a' }, { id: 'b' }] }),
    ev(904, 'power', 'enumerate_topologies', { options: [{ id: '2N' }, { id: 'DR' }, { id: 'N+1' }] }),
  ]
  renderLanes(b)
  for (const name of ['Cooling', 'Layout', 'Power']) await user.click(screen.getByRole('button', { name: new RegExp(`^${name}`) }))
  const lanes = screen.getByRole('navigation', { name: 'Agent lanes' })
  expect(lanes).not.toHaveTextContent('[object Object]')
  expect(within(lanes).getByText('route_pipes → 3 pipes')).toBeInTheDocument()
  expect(within(lanes).getByText('detect_clashes → Count 1 · 1 clash')).toBeInTheDocument()
  expect(within(lanes).getByText('fix_candidates → Finding R05:FA-01 · 2 candidates')).toBeInTheDocument()
  expect(within(lanes).getByText('enumerate_topologies → 3 options')).toBeInTheDocument()
})

test('M3: a recorded design with no agent events explains itself instead of showing every lane "Waiting"', () => {
  const b = { ...fixtureBundle(), events: [], steps: [], runs: [] }
  renderLanes(b)
  const lanes = screen.getByRole('navigation', { name: 'Agent lanes' })
  expect(within(lanes).queryByText('Waiting')).not.toBeInTheDocument()
  expect(within(lanes).getByText(/shows the recorded result/)).toBeInTheDocument()
  // Counters counted from the recorded design still show.
  expect(within(lanes).getByText('4 racks placed')).toBeInTheDocument()
})

test('D10: a lane with no events is not expandable (no chevron, no toggle)', () => {
  resetStores()
  const b = fixtureBundle()
  b.events = []
  render(
    <TooltipProvider>
      <WorkspaceProvider bundle={b} source="static">
        <AgentLanes />
      </WorkspaceProvider>
    </TooltipProvider>,
  )
  const lanes = screen.getByRole('navigation', { name: 'Agent lanes' })
  expect(within(lanes).queryAllByRole('button', { expanded: false })).toHaveLength(0)
  expect(within(lanes).getByText('Intake')).toBeInTheDocument()
})
