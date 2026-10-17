// The co-pilot's three tools (spec §6.5), executed in the browser against /api and the bundle.
// Typed input, Gemini Live function calls and push-to-talk results all go through here.
// Summaries are built from engine records only (spec §6.3): the one piece of LLM-sourced text
// (the engine's own explanation, or /api/explain's answer) is passed through fillPlaceholders,
// the same digit-insertion mechanism FindingDrawer.tsx already uses for displaying finding text.
import { fillPlaceholders, fmtKeyValue, fmtNum, fmtQty } from '@/lib/format'
import { canvasesFor, type Canvas } from '@/lib/model'
import { findingsFor, parentRevision, revisionLabel, revisionRef } from '@/lib/select'
import { statusRank } from '@/lib/status'
import type { DesignModel, Finding, Revision, WhatIfParam } from '@/lib/types'
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
  /** What the engine was asked, in words ("Explain finding R05 · FA-01"): the source label of the answer. */
  check: string
  /** What changed on screen because of it, one plain sentence each; empty when nothing did. */
  actions: string[]
}

const WHAT_IF_PARAMS: WhatIfParam[] = ['rack_kw', 'liquid_fraction', 'dv_limit_pct', 'tx_loading_cap_pct']

/** The what-if chips' wording ("Racks → 200 kW"), so the history reads like the controls. */
export function whatIfCheck(param: WhatIfParam, value: number): string {
  const label = {
    rack_kw: `Racks → ${fmtNum(value)} kW`,
    liquid_fraction: `Liquid fraction → ${fmtNum(value)}`,
    dv_limit_pct: `ΔV limit → ${fmtNum(value)}%`,
    tx_loading_cap_pct: `Transformer loading cap → ${fmtNum(value)}%`,
  }[param]
  return label ? `What-if: ${label}` : 'What-if'
}

const CANVAS_NAME: Record<Canvas, string> = { hall: '3D hall', sld: 'SLD' }

/** "R05:FA-01" as the history writes it: "R05 · FA-01". */
export const findingLabel = (findingId: string): string => findingId.replace(':', ' · ')

/** What a "show" changed on screen (typed, Live and push-to-talk say it the same way). */
export function focusActions(model: DesignModel | null, id: string, drawn: boolean): string[] {
  if (!drawn) return [`Nothing moved: ${id} is not drawn on a canvas`]
  const on = canvasesFor(model, id).map((c) => CANVAS_NAME[c])
  return [`Showing ${id} on the ${on.length ? on.join(' and the ') : 'canvas'}`]
}

/**
 * How long a spoken or typed "why" waits for the language model's rewrite of the explanation. The engine's own
 * explanation of the finding is always there; a Live conversation must not sit silent for a whole model call (6 to
 * 11 s measured), so after this the engine's text stands.
 */
const EXPLAIN_WAIT_MS = 4_000

/** The promise's value, or 'late' if it has not come back in `ms`. A late rejection is still handled (race subscribes to both). */
async function withinWait<T>(p: Promise<T>, ms: number): Promise<T | 'late'> {
  let timer: ReturnType<typeof setTimeout> | undefined
  try {
    return await Promise.race([
      p,
      new Promise<'late'>((resolve) => {
        timer = setTimeout(() => resolve('late'), ms)
      }),
    ])
  } finally {
    clearTimeout(timer)
  }
}

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
    if (!WHAT_IF_PARAMS.includes(param) || !Number.isFinite(value))
      return { summary: 'That what-if is not supported.', data: { error: 'unsupported' }, check: 'What-if', actions: [] }
    const check = whatIfCheck(param, value)
    const ran = await ctx.runWhatIf(param, value)
    if (!ran) return { summary: 'The engine is unreachable for that what-if.', data: { error: 'unavailable' }, check, actions: [] }
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
      check,
      actions: [`Ran on ${revisionLabel(rev)}; engine only, nothing saved`, 'The result is in the What-if panel and lit on the canvases'],
    }
  }
  if (name === 'explain_finding') {
    const id = String(args.finding_id ?? '')
    const element = String(args.element_id ?? id.split(':')[1] ?? '')
    const rule = (args.rule_id as string | undefined) ?? (id.includes(':') ? id.split(':')[0] : undefined)
    const located = locate(ctx.view, id, element, rule)
    if (!located)
      return { summary: `No finding for ${id || element} in this revision.`, data: { error: 'not_found' }, check: `Explain finding ${id.replace(':', ' · ') || element}`, actions: [] }
    const { finding, rev } = located
    const elsewhere = !!rev && rev.id !== ctx.view.rev?.id
    if (elsewhere) ctx.setViewRev(rev.id, { source: 'auto' })
    ctx.openFinding(finding.id)
    let text = fillPlaceholders(finding.explanation || finding.title, finding)
    const ref = rev ? revisionRef(ctx.view.bundle, rev.id, ctx.view.source) : ctx.view.revRef
    if (ref) {
      try {
        const rewrite = await withinWait(ctx.api.explain(ref, finding.id), EXPLAIN_WAIT_MS)
        if (rewrite !== 'late') text = fillPlaceholders(rewrite.text, finding)
      } catch {
        // engine explanation stands
      }
    }
    const summary = `${elsewhere ? `In ${rev.id}: ` : ''}${text}${elsewhere ? fixLine(located, ctx.view) : ''}`
    const label = `${finding.rule_id} · ${finding.element_id}`
    return {
      summary,
      data: { finding_id: finding.id, revision: rev?.id ?? null, status: finding.status, value: finding.value, limit: finding.limit, unit: finding.unit, text: summary },
      check: `Explain finding ${label}`,
      actions: [...(elsewhere ? [`Switched to ${revisionLabel(rev)}, where this check failed`] : []), `Opened ${label} in the finding drawer`],
    }
  }
  if (name === 'focus_element') {
    const id = String(args.element_id ?? '').toUpperCase()
    if (!ctx.focus(id))
      return {
        summary: `${id} is not drawn on the 3D hall or the SLD; its checks are in the Matrix.`,
        data: { element_id: id, drawn: false },
        check: `Show ${id}`,
        actions: focusActions(ctx.view.model, id, false),
      }
    return { summary: `Showing ${id}.`, data: { element_id: id }, check: `Show ${id}`, actions: focusActions(ctx.view.model, id, true) }
  }
  return { summary: `Unknown tool ${name}.`, data: { error: 'unknown_tool' }, check: name, actions: [] }
}
