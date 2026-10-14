// DesignModel → 3D scene description in model coordinates (metres; x east, y north, z up).
// Positions only; no engineering value is derived here.
import type { Discipline } from '@/lib/model'
import type { DesignModel, Point3 } from '@/lib/types'

export type V3 = [number, number, number]
export interface SceneBox {
  id: string
  center: V3
  size: V3
}
export interface SceneTube {
  id: string
  kind: 'busway-feeder' | 'cable-feeder' | 'row-busway' | 'pipe'
  discipline: Discipline
  points: V3[]
  radius: number
}
export interface HallScene {
  hall: { w: number; d: number }
  columns: SceneBox[]
  keepouts: SceneBox[]
  rooms: (SceneBox & { label: string })[]
  racks: (SceneBox & { row: string })[]
  cdus: SceneBox[]
  manifolds: SceneBox[]
  bays: (SceneBox & { zone: string })[]
  tubes: SceneTube[]
}

export const RACK_HEIGHT = 2.2
const ROW_BUSWAY_OFFSET = 0.3 // spec §9.1: A busway at x − 0.3 m, B busway at x + 0.3 m

const p3 = (p: Point3): V3 => [p.x, p.y, p.z]

export function buildHallScene(m: DesignModel): HallScene {
  const g = m.geometry
  const [w, d] = g.hall
  const buswayZ = g.tiers.busway ?? 3.2
  const racks = m.racks.map((r) => ({
    id: r.id,
    row: r.row,
    // rows run north–south: rack width spans y, depth spans x
    center: [r.x, r.y, RACK_HEIGHT / 2] as V3,
    size: [r.d ?? 1.2, r.w ?? 0.6, RACK_HEIGHT] as V3,
  }))

  const tubes: SceneTube[] = []
  for (const c of m.connections) {
    if (c.kind === 'internal' || (c.route?.length ?? 0) < 2) continue
    tubes.push({
      id: c.id,
      kind: c.kind === 'busway' ? 'busway-feeder' : 'cable-feeder',
      discipline: 'electrical',
      points: c.route!.map(p3),
      radius: c.kind === 'busway' ? 0.11 : 0.07,
    })
  }
  // Row busways run along their row at the busway tier (synthesised from rack positions and feeds).
  for (const e of m.equipment.filter((x) => x.kind === 'busway')) {
    const fed = m.racks.map((r) => ({ r, side: r.feeds.indexOf(e.id) })).filter((x) => x.side >= 0)
    if (!fed.length) continue
    const x = fed.reduce((s, f) => s + f.r.x, 0) / fed.length + (fed[0].side === 0 ? -ROW_BUSWAY_OFFSET : ROW_BUSWAY_OFFSET)
    const ys = fed.map((f) => f.r.y)
    const half = (fed[0].r.w ?? 0.6) / 2
    tubes.push({
      id: e.id,
      kind: 'row-busway',
      discipline: 'electrical',
      points: [
        [x, Math.min(...ys) - half, buswayZ],
        [x, Math.max(...ys) + half, buswayZ],
      ],
      radius: 0.1,
    })
  }
  for (const p of m.pipes) {
    if (p.route.length < 2) continue
    tubes.push({ id: p.id, kind: 'pipe', discipline: 'cooling', points: p.route.map(p3), radius: Math.max(0.06, (p.dn / 1000) * 0.75) })
  }

  const cdus = m.cooling_nodes
    .filter((n) => n.kind === 'cdu')
    .map((n) => ({ id: n.id, center: [n.x, n.y, 1.0] as V3, size: [1.2, 0.8, 2.0] as V3 }))
  const manifolds = m.cooling_nodes
    .filter((n) => n.kind === 'manifold')
    .map((n) => ({ id: n.id, center: [n.x, n.y, 2.35] as V3, size: [0.3, 0.3, 0.3] as V3 }))
  const zones = new Map<string, typeof cdus>()
  for (const n of m.cooling_nodes.filter((c) => c.kind === 'cdu')) {
    zones.set(n.zone, [...(zones.get(n.zone) ?? []), cdus.find((c) => c.id === n.id)!])
  }
  const bays = [...zones].map(([zone, list]) => {
    const xs = list.flatMap((c) => [c.center[0] - 1.4, c.center[0] + 1.4])
    const ys = list.flatMap((c) => [c.center[1] - 1.2, c.center[1] + 1.2])
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)]
    return { id: `bay-${zone}`, zone, center: [(x0 + x1) / 2, (y0 + y1) / 2, 0.01] as V3, size: [x1 - x0, y1 - y0, 0.02] as V3 }
  })

  return {
    hall: { w, d },
    columns: g.columns.map(([x, y], i) => ({ id: `col-${i}`, center: [x, y, 2.2], size: [0.5, 0.5, 4.4] })),
    keepouts: g.keepouts.map(([x0, y0, x1, y1], i) => ({
      id: `keepout-${i}`,
      center: [(x0 + x1) / 2, (y0 + y1) / 2, 1.5],
      size: [x1 - x0, y1 - y0, 3.0],
    })),
    rooms: Object.entries(g.rooms).map(([k, [x0, y0, x1, y1]]) => ({
      id: `room-${k}`,
      label: `LV room ${k}`,
      center: [(x0 + x1) / 2, (y0 + y1) / 2, 0.02],
      size: [x1 - x0, y1 - y0, 0.04],
    })),
    racks,
    cdus,
    manifolds,
    bays,
    tubes,
  }
}

/** Plan-view crossing of two polylines (first hit), at polyline `a`'s height. Used to anchor R11 labels. */
export function crossingPoint(a: V3[], b: V3[]): V3 | null {
  for (let i = 0; i < a.length - 1; i++) {
    for (let j = 0; j < b.length - 1; j++) {
      const [p, p2, q, q2] = [a[i], a[i + 1], b[j], b[j + 1]]
      const r = [p2[0] - p[0], p2[1] - p[1]]
      const s = [q2[0] - q[0], q2[1] - q[1]]
      const den = r[0] * s[1] - r[1] * s[0]
      if (Math.abs(den) < 1e-9) continue
      const t = ((q[0] - p[0]) * s[1] - (q[1] - p[1]) * s[0]) / den
      const u = ((q[0] - p[0]) * r[1] - (q[1] - p[1]) * r[0]) / den
      if (t >= 0 && t <= 1 && u >= 0 && u <= 1) return [p[0] + t * r[0], p[1] + t * r[1], p[2] + t * (p2[2] - p[2])]
    }
  }
  return null
}

/** Resamples a polyline to n points evenly spaced by length (lets a re-routed tube animate between revisions). */
export function resample(points: V3[], n: number): V3[] {
  const seg = points.slice(1).map((p, i) => Math.hypot(p[0] - points[i][0], p[1] - points[i][1], p[2] - points[i][2]))
  const total = seg.reduce((a, b) => a + b, 0)
  if (total === 0) return Array.from({ length: n }, () => points[0])
  const out: V3[] = []
  for (let k = 0; k < n; k++) {
    let dist = (total * k) / (n - 1)
    let i = 0
    while (i < seg.length - 1 && dist > seg[i]) dist -= seg[i++]
    const t = seg[i] === 0 ? 0 : Math.min(1, dist / seg[i])
    const [a, b] = [points[i], points[i + 1]]
    out.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t])
  }
  return out
}

export function midpoint(points: V3[]): V3 {
  return resample(points, 3)[1]
}
