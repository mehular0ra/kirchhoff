// 3D hall labels: what to label (finding/what-if callouts first, then rooms, bays and the keep-out),
// and a screen-space layout that keeps them from piling up (final review I1). Positions only.
import type { LucideIcon } from 'lucide-react'
import { findingsFor, relatedElementIds } from '@/lib/select'
import { STATUS_META, statusRank } from '@/lib/status'
import type { Finding } from '@/lib/types'
import type { WorkspaceView } from '../WorkspaceContext'
import { crossingPoint, midpoint, type HallScene, type V3 } from './hallScene'

export interface SceneLabel {
  id: string
  /** Anchor in model coordinates (metres; z up). */
  at: V3
  kind: 'finding' | 'context'
  text: string
  clause: string | null
  tone: string
  icon: LucideIcon | null
  findingId: string | null
}

const MAX_FINDING_LABELS = 10

export function buildLabels(scene: HallScene, v: WorkspaceView): SceneLabel[] {
  const tubes = new Map(scene.tubes.map((t) => [t.id, t]))
  const boxes = [...scene.racks, ...scene.cdus, ...scene.manifolds]
  const anchorOf = (id: string): V3 | null => {
    const t = tubes.get(id)
    if (t) return midpoint(t.points)
    const b = boxes.find((x) => x.id === id)
    return b ? [b.center[0], b.center[1], b.center[2] * 2 + 0.3] : null
  }
  const known = new Set([...tubes.keys(), ...scene.racks.map((r) => r.id), ...scene.cdus.map((c) => c.id)])
  /** R11-style findings name a second element (`over`/`above`): pin the label at their crossing. */
  const findingAnchor = (f: Finding): V3 | null => {
    const related = relatedElementIds(f, known)
    const a = tubes.get(related[0])
    const b = related[1] ? tubes.get(related[1]) : undefined
    return (a && b && crossingPoint(a.points, b.points)) || anchorOf(f.element_id)
  }

  const out: SceneLabel[] = []
  if (v.highlights.size) {
    // What-if: one callout per failing rule (the chain colours already mark every element).
    const byRule = new Map<string, Finding[]>()
    for (const f of (v.whatIf?.findings ?? []).filter((x) => x.status === 'fail')) byRule.set(f.rule_id, [...(byRule.get(f.rule_id) ?? []), f])
    for (const [rule, fs] of byRule) {
      const drawn = fs.map((f) => ({ f, at: findingAnchor(f) })).filter((x): x is { f: Finding; at: V3 } => !!x.at)
      if (!drawn.length) continue
      const what = fs.length === 1 ? fs[0].element_id : `${fs.length} elements`
      out.push({
        id: `wi:${rule}`,
        at: drawn[0].at,
        kind: 'finding',
        text: `what-if: Fail · ${rule} · ${what}`,
        clause: null,
        tone: STATUS_META.fail.text,
        icon: STATUS_META.fail.icon,
        findingId: drawn[0].f.id,
      })
    }
  } else {
    const seenRows = new Set<string>()
    // With "compare" on, a check that failed in the parent and passes now is called out as resolved.
    const parentFails = new Set(v.diff ? findingsFor(v.bundle, v.parent?.id).filter((f) => f.status === 'fail').map((f) => f.id) : [])
    for (const f of [...v.findings].sort((x, y) => statusRank(y.status) - statusRank(x.status))) {
      const open = f.status === 'fail' || f.status === 'warn'
      const resolved = !open && parentFails.has(f.id) && v.resolved.has(f.element_id)
      if (!open && !resolved) continue
      const rack = scene.racks.find((r) => r.id === f.element_id)
      if (rack) {
        if (seenRows.has(rack.row)) continue // one callout per rack row
        seenRows.add(rack.row)
      }
      const at = findingAnchor(f)
      if (!at) continue
      const meta = open ? STATUS_META[f.status] : null
      out.push({
        id: `f:${f.id}`,
        at,
        kind: 'finding',
        text: meta ? `${meta.label} · ${f.rule_id} · ${f.element_id}` : `resolved · ${f.rule_id} · ${f.element_id}`,
        clause: f.tender_refs?.[0]?.clause ?? null,
        tone: meta ? meta.text : 'text-emerald-300',
        icon: meta ? meta.icon : STATUS_META.pass.icon,
        findingId: f.id,
      })
    }
  }
  const findings = out.slice(0, MAX_FINDING_LABELS)

  const context: SceneLabel[] = [
    ...scene.keepouts.map((k) => ({ id: k.id, at: [k.center[0], k.center[1], k.size[2] + 0.2] as V3, text: 'Keep-out (fire suppression)', tone: 'text-rose-300' })),
    ...scene.bays.map((b) => ({ id: b.id, at: [b.center[0], b.center[1], 0.05] as V3, text: `CDU bay ${b.zone}`, tone: 'text-sky-300' })),
    ...scene.rooms.map((r) => ({ id: r.id, at: r.labelAt, text: r.label, tone: 'text-zinc-300' })),
  ].map((c) => ({ ...c, kind: 'context' as const, clause: null, icon: null, findingId: null }))
  return [...findings, ...context]
}

export interface LayoutItem {
  id: string
  /** Projected anchor in canvas pixels. */
  x: number
  y: number
  /** Label size in pixels. */
  w: number
  h: number
  kind: 'finding' | 'context'
  /** Anchor is behind the camera or outside the clip volume. */
  behind?: boolean
}
export interface Placement {
  x: number
  y: number
  visible: boolean
}

const GAP = 3
const LIFT = 8 // labels sit just above their anchor
const EDGE = 4

/**
 * Greedy screen-space placement, in order (callers pass findings first). A finding label tries its
 * natural spot above the anchor, then steps up or down until it no longer overlaps an earlier
 * label; a context label (room, bay, keep-out) is simply hidden when its spot is taken.
 */
export function layoutLabels(items: LayoutItem[], bounds: { w: number; h: number }): Map<string, Placement> {
  const out = new Map<string, Placement>()
  const placed: { x: number; y: number; w: number; h: number }[] = []
  const hits = (r: { x: number; y: number; w: number; h: number }) =>
    placed.some((p) => r.x < p.x + p.w + GAP && p.x < r.x + r.w + GAP && r.y < p.y + p.h + GAP && p.y < r.y + r.h + GAP)
  for (const it of items) {
    const outside = it.x < -it.w || it.x > bounds.w + it.w || it.y < -it.h || it.y > bounds.h + it.h
    if (it.behind || outside) {
      out.set(it.id, { x: 0, y: 0, visible: false })
      continue
    }
    const x = Math.min(Math.max(it.x - it.w / 2, EDGE), Math.max(EDGE, bounds.w - it.w - EDGE))
    const clampY = (y: number) => Math.min(Math.max(y, EDGE), Math.max(EDGE, bounds.h - it.h - EDGE))
    const y0 = clampY(it.y - it.h - LIFT)
    const tries = it.kind === 'finding' ? [0, -1, 1, -2, 2, -3, 3, -4, 4, -5, 5, -6, 6] : [0]
    let spot: { x: number; y: number; w: number; h: number } | null = null
    for (const k of tries) {
      const r = { x, y: clampY(y0 + k * (it.h + GAP)), w: it.w, h: it.h }
      if (!hits(r)) {
        spot = r
        break
      }
    }
    if (!spot && it.kind === 'finding') spot = { x, y: y0, w: it.w, h: it.h } // never drop a finding
    if (!spot) {
      out.set(it.id, { x, y: y0, visible: false })
      continue
    }
    placed.push(spot)
    out.set(it.id, { x: spot.x, y: spot.y, visible: true })
  }
  return out
}
