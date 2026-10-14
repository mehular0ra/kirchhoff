// The 7-step guided tour (spec §13.5). Text never states a number that is not counted from data.
import { agentsInvolved } from '@/lib/select'
import type { Bundle } from '@/lib/types'

export interface TourContext {
  /** Hall A's static bundle if it has been loaded this session. */
  hallA: Bundle | null
}

export interface TourStep {
  id: string
  route: (ctx: TourContext) => string
  target: string
  title: (ctx: TourContext) => string
  body: string
}

/** The earliest revision with a failing finding, and that finding (tour step 3 opens it). */
export function firstFailure(b: Bundle | null): { rev: string; id: string } | null {
  for (const r of b?.revisions ?? []) {
    const f = (b!.findings[r.id] ?? []).find((x) => x.status === 'fail')
    if (f) return { rev: r.id, id: f.id }
  }
  return null
}

export const TOUR_STEPS: TourStep[] = [
  {
    id: 'projects',
    route: () => '/app',
    target: '[data-tour="projects"]',
    title: () => "Your firm's live projects",
    body: 'Meridian Power Engineering designs AI data halls, grid connections and solar fields here.',
  },
  {
    id: 'matrix',
    route: () => '/app/p/hall-a?tab=matrix',
    target: '[data-tour="matrix-row"]',
    title: () => 'Every number is checked and cited',
    body: 'Hall A is signed. Each cell is a deterministic rule check on one element; click any cell to see why.',
  },
  {
    id: 'finding',
    route: (ctx) => {
      const f = firstFailure(ctx.hallA)
      return f ? `/app/p/hall-a?tab=matrix&rev=${f.rev}&finding=${encodeURIComponent(f.id)}` : '/app/p/hall-a?tab=matrix'
    },
    target: '[data-tour="tender-chip"]',
    title: () => 'Open a finding and its source',
    body: 'This failure was caught on the first revision. Click the tender chip: the PDF opens at the clause, highlighted.',
  },
  {
    id: 'lanes',
    route: () => '/app/p/hall-a',
    target: '[data-tour="lanes"]',
    title: (ctx) => {
      const n = ctx.hallA ? agentsInvolved(ctx.hallA).length : null
      return n ? `${n} agents designed this; here's what each did` : "The agents that designed this, and what each did"
    },
    body: 'Each lane is one agent: its tool calls, results, findings and the assumptions it logged.',
  },
  {
    id: 'whatif',
    route: () => '/app/p/hall-a',
    target: '[data-tour="whatif-chip"]',
    title: () => 'Try it: racks to 200 kW',
    body: 'The engine re-checks a shadow copy of the signed design. Nothing is saved; every failure lights up across power and cooling.',
  },
  {
    id: 'integrations',
    route: () => '/app/integrations',
    target: '[data-tour="integrations-prs"]',
    title: () => 'Approval pushed these PRs to ERP and moved the CRM deal',
    body: 'Engineering, procurement and sales in one workflow (sandbox systems).',
  },
  {
    id: 'hall-b',
    route: () => '/app',
    target: '[data-tour="hall-b"]',
    title: () => 'Now run it live yourself',
    body: "Hall B is Hall A's twin. Start a live run in your own workspace, or watch a recorded one.",
  },
]
