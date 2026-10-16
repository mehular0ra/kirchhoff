// The co-pilot's three tools (spec §6.5), executed in the browser against /api and the bundle.
// Typed input, Gemini Live function calls and push-to-talk results all go through here.
// Summaries are built from engine records only (spec §6.3): the one piece of LLM-sourced text
// (the engine's own explanation, or /api/explain's answer) is passed through fillPlaceholders,
// the same digit-insertion mechanism FindingDrawer.tsx already uses for displaying finding text.
import { fillPlaceholders, fmtKeyValue, fmtQty } from '@/lib/format'
import { findingsFor, parentRevision, revisionLabel, revisionRef } from '@/lib/select'
import { statusRank } from '@/lib/status'
import type { Finding, Revision, WhatIfParam } from '@/lib/types'
import type { ApiClient } from '@/services/apiClient'
import type { ViewRevSource } from '@/store/ui'
import { readFix } from '../finding/fixView'
import type { WorkspaceView } from '../WorkspaceContext'
import type { WhatIfRun } from './useWhatIf'

export interface ToolContext {
  view: WorkspaceView
  api: ApiClient
  /** Runs on the head revision unless one was picked in the revision bar (#37); says which it ran on. */
  runWhatIf: (param: WhatIfParam, value: number) => Promise<WhatIfRun | null>
  /** Focuses the element; false when no canvas draws it (R12 "BOQ"), so the answer says so. */
  focus: (id: string) => boolean
  openFinding: (id: string) => void
  /**
   * Switches the workspace to another revision (the "why" answer opens the revision where the check failed, D1).
   * Always an automatic switch: it is not a revision-bar pick, so later what-ifs stay on the head (#37).
   */
  setViewRev: (rev: string, opts: { source: ViewRevSource }) => void
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

const isProblem = (f: Finding | null): f is Finding => !!f && (f.status === 'fail' || f.status === 'warn')

/** The finding asked about in one revision: by id first, else the worst one for the element (and rule). */
function findingIn(findings: Finding[], id: string, element: string, rule?: string): Finding | null {
  return findings.find((f) => f.id === id) ?? worstFindingFor(findings, element, rule)
}

interface Located {
  finding: Finding
  rev: Revision | null
  /** The next revision on the path back from the one on screen (where the check was fixed), when it is not `rev`. */
  child: Revision | null
}

/**
 * "Why did FA-01 fail?" on a signed revision where FA-01 now passes must explain the check that failed,
 * not the passing one (UX-1 D1). When the finding on screen is pass or n/a, walk back through the
 * parent revisions to the nearest fail or warn on the same finding id, or the same element and rule.
 */
function locate(view: WorkspaceView, id: string, element: string, rule?: string): Located | null {
  const here = findingIn(view.findings, id, element, rule)
  if (isProblem(here)) return { finding: here, rev: view.rev, child: null }
  let child = view.rev
  for (let rev = parentRevision(view.bundle, view.rev); rev; child = rev, rev = parentRevision(view.bundle, rev)) {
    const back = findingIn(findingsFor(view.bundle, rev.id), id, element, rule)
    if (isProblem(back)) return { finding: back, rev, child }
  }
  return here ? { finding: here, rev: view.rev, child: null } : null
}

/** One line from the chosen-fix record: "Fixed in r2: <label> · Cost Δ +$15,580 · ΔV 0.84%". Values from the record only. */
function fixLine(located: Located, view: WorkspaceView): string {
  const fix = readFix(located.finding.fix ?? null, located.finding.rule_id)
  if (!fix) return ''
  const after = located.child ? findingsFor(view.bundle, located.child.id).find((f) => f.id === located.finding.id) : null
  const lead = after && !isProblem(after) && located.child ? `Fixed in ${located.child.id}` : 'Chosen fix'
  // The cost and the rule's resulting metric, chosen by key (readFix), never "the first two" (the limit, in a recorded bundle).
  const deltas = fix.headline.map(([k, v]) => fmtKeyValue(k, v))
  return ` ${lead}: ${[fix.label, ...deltas].join(' · ')}.`
}

export async function executeTool(name: string, args: Record<string, unknown>, ctx: ToolContext): Promise<ToolOutcome> {
  if (name === 'what_if') {
    const param = String(args.param) as WhatIfParam
    const value = Number(args.value)
    if (!WHAT_IF_PARAMS.includes(param) || !Number.isFinite(value)) return { summary: 'That what-if is not supported.', data: { error: 'unsupported' } }
    const ran = await ctx.runWhatIf(param, value)
    if (!ran) return { summary: 'The engine is unreachable for that what-if.', data: { error: 'unavailable' } }
    const { result: r, rev } = ran
    const fails = r.findings.filter((f) => f.status === 'fail')
    // Names the revision it ran on (#37): "On r2 (signed): 60 checks fail: …", id and status from the bundle.
    const summary = `On ${revisionLabel(rev)}: ${
      fails.length
        ? `${fails.length} checks fail: ${fails
            .slice(0, 4)
            .map((f) => `${f.rule_id} ${f.element_id} ${fmtQty(f.value ?? null, f.unit)} vs ${fmtQty(f.limit ?? null, f.unit)}`)
            .join('; ')}`
        : 'no check fails.'
    }`
    return {
      summary,
      data: {
        revision: rev.id,
        revision_status: rev.status,
        failing: fails.map((f) => ({ rule: f.rule_id, element: f.element_id, value: f.value, limit: f.limit, unit: f.unit })),
        impact_chain: r.impact_chain,
      },
    }
  }
  if (name === 'explain_finding') {
    const id = String(args.finding_id ?? '')
    const element = String(args.element_id ?? id.split(':')[1] ?? '')
    const rule = (args.rule_id as string | undefined) ?? (id.includes(':') ? id.split(':')[0] : undefined)
    const located = locate(ctx.view, id, element, rule)
    if (!located) return { summary: `No finding for ${id || element} in this revision.`, data: { error: 'not_found' } }
    const { finding, rev } = located
    const elsewhere = !!rev && rev.id !== ctx.view.rev?.id
    if (elsewhere) ctx.setViewRev(rev.id, { source: 'auto' })
    ctx.openFinding(finding.id)
    let text = fillPlaceholders(finding.explanation || finding.title, finding)
    const ref = rev ? revisionRef(ctx.view.bundle, rev.id, ctx.view.source) : ctx.view.revRef
    if (ref) {
      try {
        text = fillPlaceholders((await ctx.api.explain(ref, finding.id)).text, finding)
      } catch {
        // engine explanation stands
      }
    }
    const summary = `${elsewhere ? `In ${rev.id}: ` : ''}${text}${elsewhere ? fixLine(located, ctx.view) : ''}`
    return {
      summary,
      data: { finding_id: finding.id, revision: rev?.id ?? null, status: finding.status, value: finding.value, limit: finding.limit, unit: finding.unit, text: summary },
    }
  }
  if (name === 'focus_element') {
    const id = String(args.element_id ?? '').toUpperCase()
    if (!ctx.focus(id))
      return { summary: `${id} is not drawn on the 3D hall or the SLD; its checks are in the Matrix.`, data: { element_id: id, drawn: false } }
    return { summary: `Showing ${id}.`, data: { element_id: id } }
  }
  return { summary: `Unknown tool ${name}.`, data: { error: 'unknown_tool' } }
}
