// Asset-pack results (spec §10). Static bundles carry the engine's result dict in the last
// tool_result event whose tool is evaluate_grid / evaluate_solar (ruling R5).
import { toolPayload } from '@/lib/events'
import { fmtNum } from '@/lib/format'
import type { AssetResult, Bundle } from '@/lib/types'

export const ASSET_TOOLS = ['evaluate_grid', 'evaluate_solar']

/** The option the Asset agent picked (WS2 `choice`), else the engine's `recommended`. */
export function chosenOption(r: AssetResult): string {
  return r.choice?.option ?? r.recommended
}

/** Mini SLD: the result's `sld`, else WS1's grid `geometry.nodes/edges` (evaluate_grid returns no `sld` key). */
export function miniSld(r: AssetResult): NonNullable<AssetResult['sld']> | null {
  if (r.sld) return r.sld
  const g = r.geometry as { nodes?: unknown; edges?: unknown }
  if (!Array.isArray(g.nodes) || !Array.isArray(g.edges)) return null
  const nodes = (g.nodes as Record<string, unknown>[]).map((n) => ({
    id: String(n.id),
    kind: 'bus',
    label: typeof n.kv === 'number' ? `${fmtNum(n.kv)} kV` : String(n.id),
  }))
  const edges = (g.edges as Record<string, unknown>[]).map((e) => ({ src: String(e.src), dst: String(e.dst), label: String(e.id ?? '') }))
  return { nodes, edges }
}

export function assetResultFrom(b: Bundle): AssetResult | null {
  for (const e of [...b.events].reverse()) {
    const t = toolPayload(e)
    if (e.kind === 'tool_result' && t && ASSET_TOOLS.includes(t.tool) && Array.isArray(t.summary.options)) {
      return t.summary as unknown as AssetResult
    }
  }
  return null
}

const NAME_KEYS = ['id', 'name', 'label']

export function optionName(o: Record<string, unknown>): string {
  return String(o.name ?? o.label ?? o.id ?? '')
}

export function optionId(o: Record<string, unknown>): string {
  return String(o.id ?? o.name ?? '')
}

/** Union of the option dicts' keys (engine order), excluding identity keys. */
export function optionColumns(options: Record<string, unknown>[]): string[] {
  const cols: string[] = []
  for (const o of options) for (const k of Object.keys(o)) if (!NAME_KEYS.includes(k) && !cols.includes(k)) cols.push(k)
  return cols
}

type XY = [number, number]
export interface Shapes {
  lines: { id: string; points: XY[] }[]
  polygons: { id: string; points: XY[] }[]
  rects: { id: string; r: [number, number, number, number] }[]
  points: { id: string; p: XY }[]
}

const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
const isXY = (v: unknown): v is XY => Array.isArray(v) && v.length === 2 && v.every(isNum)
const isRect = (v: unknown): v is [number, number, number, number] => Array.isArray(v) && v.length === 4 && v.every(isNum)
const CLOSED = /polygon|field|boundary|site|area|parcel/i

/** Generic geometry reader: [x,y] → point; [[x,y],…] → line (closed if the key names an area); [[x0,y0,x1,y1],…] → rects. */
export function geometryShapes(geometry: Record<string, unknown>): Shapes {
  const s: Shapes = { lines: [], polygons: [], rects: [], points: [] }
  for (const [k, v] of Object.entries(geometry)) {
    if (isXY(v)) s.points.push({ id: k, p: v })
    else if (Array.isArray(v) && v.length && v.every(isXY)) (CLOSED.test(k) ? s.polygons : s.lines).push({ id: k, points: v as XY[] })
    else if (Array.isArray(v) && v.length && v.every(isRect)) v.forEach((r, i) => s.rects.push({ id: `${k}-${i}`, r: r as [number, number, number, number] }))
  }
  return s
}

export function shapeBounds(s: Shapes): [number, number, number, number] | null {
  const xs: number[] = []
  const ys: number[] = []
  const add = ([x, y]: XY) => {
    xs.push(x)
    ys.push(y)
  }
  s.lines.forEach((l) => l.points.forEach(add))
  s.polygons.forEach((l) => l.points.forEach(add))
  s.points.forEach((p) => add(p.p))
  s.rects.forEach(({ r }) => {
    add([r[0], r[1]])
    add([r[2], r[3]])
  })
  if (!xs.length) return null
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)]
}
