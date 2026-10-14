// The co-pilot's three tools (spec §6.5), executed in the browser against /api and the bundle.
// Typed input, Gemini Live function calls and push-to-talk results all go through here.
// Summaries are built from engine records only (spec §6.3): the one piece of LLM-sourced text
// (the engine's own explanation, or /api/explain's answer) is passed through fillPlaceholders,
// the same digit-insertion mechanism FindingDrawer.tsx already uses for displaying finding text.
import { fillPlaceholders, fmtQty } from '@/lib/format'
import { statusRank } from '@/lib/status'
import type { Finding, WhatIfParam, WhatIfResult } from '@/lib/types'
import type { ApiClient } from '@/services/apiClient'
import type { WorkspaceView } from '../WorkspaceContext'

export interface ToolContext {
  view: WorkspaceView
  api: ApiClient
  runWhatIf: (param: WhatIfParam, value: number) => Promise<WhatIfResult | null>
  focus: (id: string) => void
  openFinding: (id: string) => void
}

export interface ToolOutcome {
  summary: string
  /** Sent back to Gemini Live as the FunctionResponse.response. */
  data: Record<string, unknown>
}

const WHAT_IF_PARAMS: WhatIfParam[] = ['rack_kw', 'liquid_fraction', 'dv_limit_pct', 'tx_loading_cap_pct']

function worstFindingFor(findings: Finding[], element: string, rule?: string): Finding | null {
  return (
    findings
      .filter((f) => f.element_id.toUpperCase() === element.toUpperCase() && (!rule || f.rule_id === rule))
      .sort((a, b) => statusRank(b.status) - statusRank(a.status))[0] ?? null
  )
}

export async function executeTool(name: string, args: Record<string, unknown>, ctx: ToolContext): Promise<ToolOutcome> {
  if (name === 'what_if') {
    const param = String(args.param) as WhatIfParam
    const value = Number(args.value)
    if (!WHAT_IF_PARAMS.includes(param) || !Number.isFinite(value)) return { summary: 'That what-if is not supported.', data: { error: 'unsupported' } }
    const r = await ctx.runWhatIf(param, value)
    if (!r) return { summary: 'The engine is unreachable for that what-if.', data: { error: 'unavailable' } }
    const fails = r.findings.filter((f) => f.status === 'fail')
    const summary = fails.length
      ? `${fails.length} checks fail: ${fails
          .slice(0, 4)
          .map((f) => `${f.rule_id} ${f.element_id} ${fmtQty(f.value ?? null, f.unit)} vs ${fmtQty(f.limit ?? null, f.unit)}`)
          .join('; ')}`
      : 'No check fails.'
    return {
      summary,
      data: {
        failing: fails.map((f) => ({ rule: f.rule_id, element: f.element_id, value: f.value, limit: f.limit, unit: f.unit })),
        impact_chain: r.impact_chain,
      },
    }
  }
  if (name === 'explain_finding') {
    const id = String(args.finding_id ?? '')
    const finding =
      ctx.view.findings.find((f) => f.id === id) ??
      worstFindingFor(ctx.view.findings, String(args.element_id ?? id.split(':')[1] ?? ''), (args.rule_id as string | undefined) ?? id.split(':')[0])
    if (!finding) return { summary: `No finding for ${id || String(args.element_id)} in this revision.`, data: { error: 'not_found' } }
    ctx.openFinding(finding.id)
    let text = fillPlaceholders(finding.explanation || finding.title, finding)
    if (ctx.view.revRef) {
      try {
        text = fillPlaceholders((await ctx.api.explain(ctx.view.revRef, finding.id)).text, finding)
      } catch {
        // engine explanation stands
      }
    }
    return { summary: text, data: { finding_id: finding.id, status: finding.status, value: finding.value, limit: finding.limit, unit: finding.unit, text } }
  }
  if (name === 'focus_element') {
    const id = String(args.element_id ?? '').toUpperCase()
    ctx.focus(id)
    return { summary: `Showing ${id}.`, data: { element_id: id } }
  }
  return { summary: `Unknown tool ${name}.`, data: { error: 'unknown_tool' } }
}
