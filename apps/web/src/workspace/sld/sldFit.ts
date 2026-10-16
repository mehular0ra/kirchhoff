// SLD readability (UX-1 D8): where the first fit looks, and how an edge reads. Pure, so it is unit-tested;
// colours and text come from the finding's status (icon glyph + word, never colour alone).
import type { ChangeKind } from '@/lib/diff'
import type { Discipline } from '@/lib/model'
import { CHAIN_COLORS } from '@/lib/agents'
import { STATUS_META, statusRank } from '@/lib/status'
import type { Finding, FindingStatus } from '@/lib/types'
import type { SldGraph } from './sldGraph'

/** Below this zoom node labels drop under ~10 px on screen; the first fit never goes lower (the visitor pans). */
export const LEGIBLE_ZOOM = 0.8

export interface FitPlan {
  /** Frame only these nodes; whole diagram when absent. */
  nodes?: string[]
  minZoom?: number
  maxZoom?: number
  padding: number
  /** At the zoom floor, start at the top of the diagram (MV bus, transformers) instead of its middle (N3). */
  anchorTop?: boolean
}

/**
 * The first fit for a revision: a revision with a fail or warn drawn on the SLD frames the worst one (r1's FA-01
 * feeder between CB-A1 and A-01), so the failure is legible on arrival; a clean revision fits the whole diagram
 * but no smaller than LEGIBLE_ZOOM.
 */
export function initialFit(graph: SldGraph, findings: Finding[]): FitPlan {
  const open = findings.filter((f) => f.status === 'fail' || f.status === 'warn').sort((a, b) => statusRank(b.status) - statusRank(a.status))
  for (const f of open) {
    const node = graph.nodes.find((n) => n.id === f.element_id || n.members.includes(f.element_id))
    if (node) return { nodes: [node.id], maxZoom: 1, padding: 0.9 }
    const edge = graph.edges.find((e) => e.id === f.element_id)
    if (edge) return { nodes: [edge.source, edge.target], maxZoom: 1, padding: 0.9 }
  }
  return { minZoom: LEGIBLE_ZOOM, padding: 0.04, anchorTop: true }
}

/**
 * The viewport for a diagram too big to fit at `minZoom` (N3): zoom at the floor with the diagram's top-left corner
 * `pad` px inside the canvas, so the first view reads top-down from the MV bus (ELK puts it at the left of the top
 * row) and the transformers. Centring it horizontally put the MV bus off-screen. null when the whole diagram fits
 * at or above `minZoom` (the caller then fits it whole). Viewport geometry only.
 */
export function topAnchoredViewport(
  bounds: { x: number; y: number; width: number; height: number },
  canvas: { width: number; height: number },
  minZoom: number,
  pad: number,
): { x: number; y: number; zoom: number } | null {
  const fit = Math.min((canvas.width - 2 * pad) / bounds.width, (canvas.height - 2 * pad) / bounds.height)
  if (fit >= minZoom) return null
  return { zoom: minZoom, x: pad - bounds.x * minZoom, y: pad - bounds.y * minZoom }
}

const GLYPH: Partial<Record<FindingStatus, string>> = { fail: '✕', warn: '⚠' }
// On white: -700 text on a -50 pill with the status hex as its border (AA, 6:1 and 4.8:1).
const STATUS_LABEL_TEXT: Partial<Record<FindingStatus, string>> = { fail: '#be123c', warn: '#b45309' }
const STATUS_LABEL_BG: Partial<Record<FindingStatus, string>> = { fail: '#fff1f2', warn: '#fffbeb' }
const EDGE = { quiet: '#8a93a0', changed: '#d97706', label: '#3f4550', labelBg: '#ffffff' } as const

export interface EdgeAppearance {
  color: string
  strokeWidth: number
  label: string | undefined
  labelStyle: { fill: string; fontFamily: string; fontSize: number; fontWeight: number }
  labelBgStyle: { fill: string; stroke?: string; strokeWidth?: number }
  labelBgPadding: [number, number]
}

export function edgeAppearance({
  status,
  change,
  chain,
  label,
}: {
  status: FindingStatus | null
  change: ChangeKind | null
  chain: Discipline | null
  label: string | null
}): EdgeAppearance {
  const open = !!status && statusRank(status) >= statusRank('warn')
  const color = chain ? CHAIN_COLORS[chain] : open ? STATUS_META[status!].hex : change ? EDGE.changed : EDGE.quiet
  const statusText = open ? ` · ${GLYPH[status!]} ${STATUS_META[status!].label}` : ''
  return {
    color,
    strokeWidth: open ? 3.5 : label ? 2.5 : 1.5,
    label: label ? `${label}${statusText}${change ? ' · changed' : ''}` : undefined,
    labelStyle: {
      fill: open ? STATUS_LABEL_TEXT[status!]! : EDGE.label,
      fontFamily: 'JetBrains Mono Variable, monospace',
      fontSize: open ? 13 : 11,
      fontWeight: open ? 600 : 400,
    },
    labelBgStyle: open ? { fill: STATUS_LABEL_BG[status!]!, stroke: STATUS_META[status!].hex, strokeWidth: 1 } : { fill: EDGE.labelBg },
    labelBgPadding: open ? [6, 3] : [3, 2],
  }
}
