// 3D hall (spec §12): instanced racks, tube busways/feeders/pipes on their tiers, columns,
// keep-out volume, CDU bays; coloured by finding status with icon+text labels; click → finding.
import { Edges, Grid, Instance, Instances, OrbitControls } from '@react-three/drei'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { useReducedMotion } from 'motion/react'
import { useEffect, useMemo, useRef, useState, type RefObject } from 'react'
import * as THREE from 'three'
import { EmptyState } from '@/components/Labels'
import { CHAIN_COLORS } from '@/lib/agents'
import { currentShot } from '@/lib/flags'
import { STATUS_META, statusRank } from '@/lib/status'
import type { Finding } from '@/lib/types'
import { useUi } from '@/store/ui'
import { Legend } from '../Legend'
import { legendKeys } from '../legendKeys'
import { useWorkspace, type WorkspaceView } from '../WorkspaceContext'
import { buildLabels, layoutLabels, type LayoutItem, type SceneLabel } from './hallLabels'
import { buildHallScene, midpoint, resample, type HallScene, type SceneBox, type SceneTube, type V3 } from './hallScene'
import { useTubeGeometry } from './useTubeGeometry'

// Readability (final review I1): mid-grey racks with light outlines on a slightly lifted floor, lit
// by a sky/ground hemisphere plus key and fill lights, rendered without tone mapping (`flat`) so
// status colours keep their hue.
const BASE = {
  rack: '#94a3b8',
  column: '#3a4350',
  'busway-feeder': '#d4d4d8',
  'cable-feeder': '#a1a1aa',
  'row-busway': '#e4e4e7',
  pipe: '#38bdf8',
  cdu: '#3b82c4',
} as const
const DIM = '#2a3038'
const RESOLVED = '#34d399'
const CHANGED = '#fbbf24'

function hasWebGL(): boolean {
  try {
    const c = document.createElement('canvas')
    return !!(c.getContext('webgl2') || c.getContext('webgl'))
  } catch {
    return false
  }
}

function colourFor(id: string, base: string, v: WorkspaceView): { color: string; emissive: string; dim: boolean } {
  if (v.highlights.size) {
    const chain = v.highlights.get(id)
    return chain ? { color: CHAIN_COLORS[chain[0]], emissive: CHAIN_COLORS[chain[0]], dim: false } : { color: DIM, emissive: '#000000', dim: true }
  }
  if (v.diff && v.resolved.has(id)) return { color: RESOLVED, emissive: RESOLVED, dim: false }
  const s = v.status.get(id)
  if (s === 'fail' || s === 'warn') return { color: STATUS_META[s].hex, emissive: STATUS_META[s].hex, dim: false }
  if (v.diff?.byId.get(id) === 'changed') return { color: CHANGED, emissive: '#000000', dim: false }
  return { color: base, emissive: '#000000', dim: false }
}

function useCoords(scene: HallScene) {
  const cx = scene.hall.w / 2
  const cy = scene.hall.d / 2
  return useMemo(
    () => ({
      pos: ([x, y, z]: V3): V3 => [x - cx, z, -(y - cy)],
      size: ([sx, sy, sz]: V3): V3 => [sx, sz, sy],
    }),
    [cx, cy],
  )
}

function tubeGeometry(points: V3[], radius: number, pos: (p: V3) => V3): THREE.TubeGeometry {
  const path = new THREE.CurvePath<THREE.Vector3>()
  const v = points.map((p) => new THREE.Vector3(...pos(p)))
  for (let i = 0; i < v.length - 1; i++) path.add(new THREE.LineCurve3(v[i], v[i + 1]))
  return new THREE.TubeGeometry(path, Math.max(8, points.length * 12), radius, 10, false)
}

/** A tube that eases from its previous route to a new one (e.g. H-Z2 dropping to the low tier). */
function AnimatedTube({ tube, view, pos, onPick }: { tube: SceneTube; view: WorkspaceView; pos: (p: V3) => V3; onPick: () => void }) {
  const reduce = useReducedMotion()
  const meshRef = useRef<THREE.Mesh>(null)
  const target = useMemo(() => resample(tube.points, 32), [tube.points])
  // Geometry is owned imperatively (never held in React state, never built during render — spec
  // ruling P3-R4) and the snap-vs-animate decision is a small state machine of its own (spec
  // ruling P3-R5, fix round 3): see useTubeGeometry's doc comment for why.
  const { tick } = useTubeGeometry<THREE.TubeGeometry>({
    meshRef,
    target,
    reduce: !!reduce,
    build: (points) => tubeGeometry(points, tube.radius, pos),
  })

  useFrame(tick)

  const c = colourFor(tube.id, BASE[tube.kind], view)
  return (
    <mesh
      ref={meshRef}
      onClick={(e) => {
        e.stopPropagation()
        onPick()
      }}
    >
      <meshStandardMaterial
        color={c.color}
        emissive={c.emissive}
        emissiveIntensity={c.emissive === '#000000' ? 0 : 0.6}
        transparent={c.dim}
        opacity={c.dim ? 0.25 : 1}
        metalness={0.2}
        roughness={0.5}
      />
    </mesh>
  )
}

type Coords = { pos: (p: V3) => V3; size: (s: V3) => V3 }

/** One merged line-segment geometry outlining every rack (one draw call), so racks read as cabinets. */
function RackOutlines({ racks, coords, dim }: { racks: SceneBox[]; coords: Coords; dim: boolean }) {
  const geometry = useMemo(() => {
    const corners = [[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1], [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]]
    const edges = [[0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7]]
    const pts: number[] = []
    for (const r of racks) {
      const [cx, cy, cz] = coords.pos(r.center)
      const [sx, sy, sz] = coords.size(r.size)
      const c = corners.map(([a, b, d]) => [cx + (a * sx) / 2, cy + (b * sy) / 2, cz + (d * sz) / 2])
      for (const [i, j] of edges) pts.push(...c[i], ...c[j])
    }
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3))
    return g
  }, [racks, coords])
  useEffect(() => () => geometry.dispose(), [geometry])
  return (
    <lineSegments geometry={geometry}>
      <lineBasicMaterial color="#e2e8f0" transparent opacity={dim ? 0.12 : 0.55} />
    </lineSegments>
  )
}

/**
 * Projects every label anchor each frame and places the DOM labels (rendered outside the canvas by
 * HallLabelOverlay) with layoutLabels(): finding callouts never stack on each other, and room/bay
 * names give way to them. Writes styles directly — no React render per frame.
 */
function LabelLayout({ labels, els, leaders, pos }: { labels: SceneLabel[]; els: RefObject<Map<string, HTMLElement>>; leaders: RefObject<Map<string, SVGGElement>>; pos: (p: V3) => V3 }) {
  const { camera, size } = useThree()
  const v = useMemo(() => new THREE.Vector3(), [])
  const sizes = useRef(new Map<string, { w: number; h: number }>())
  useEffect(() => sizes.current.clear(), [labels])
  useFrame(() => {
    const items: LayoutItem[] = []
    const anchors = new Map<string, [number, number]>()
    for (const l of labels) {
      const el = els.current.get(l.id)
      if (!el) continue
      let sz = sizes.current.get(l.id)
      if (!sz || !sz.w) {
        sz = { w: el.offsetWidth, h: el.offsetHeight }
        sizes.current.set(l.id, sz)
      }
      v.set(...pos(l.at)).project(camera)
      const x = ((v.x + 1) / 2) * size.width
      const y = ((1 - v.y) / 2) * size.height
      anchors.set(l.id, [x, y])
      items.push({ id: l.id, x, y, w: sz.w, h: sz.h, kind: l.kind, behind: v.z > 1 })
    }
    const placed = layoutLabels(items, { w: size.width, h: size.height })
    for (const [id, p] of placed) {
      const el = els.current.get(id)
      if (!el) continue
      const t = `translate3d(${Math.round(p.x)}px, ${Math.round(p.y)}px, 0)`
      if (el.style.transform !== t) el.style.transform = t
      const vis = p.visible ? 'visible' : 'hidden'
      if (el.style.visibility !== vis) el.style.visibility = vis
      const g = leaders.current.get(id)
      const a = anchors.get(id)
      if (!g || !a) continue
      if (g.style.visibility !== vis) g.style.visibility = vis
      const sz = sizes.current.get(id)!
      const ly = p.y + sz.h / 2 < a[1] ? p.y + sz.h : p.y // label bottom when above the anchor, else its top
      const line = g.firstElementChild as SVGLineElement
      const dot = g.lastElementChild as SVGCircleElement
      line.setAttribute('x1', String(Math.round(a[0])))
      line.setAttribute('y1', String(Math.round(a[1])))
      line.setAttribute('x2', String(Math.round(Math.min(Math.max(a[0], p.x + 6), p.x + sz.w - 6))))
      line.setAttribute('y2', String(Math.round(ly)))
      dot.setAttribute('cx', String(Math.round(a[0])))
      dot.setAttribute('cy', String(Math.round(a[1])))
    }
  })
  return null
}

/** DOM labels over the canvas (positioned by LabelLayout). Finding callouts are buttons that open the finding. */
function HallLabelOverlay({ labels, els, leaders }: { labels: SceneLabel[]; els: RefObject<Map<string, HTMLElement>>; leaders: RefObject<Map<string, SVGGElement>> }) {
  const openFinding = useUi((s) => s.openFinding)
  const register = (id: string) => (el: HTMLElement | null) => {
    if (el) els.current.set(id, el)
    else els.current.delete(id)
  }
  const registerLeader = (id: string) => (el: SVGGElement | null) => {
    if (el) leaders.current.set(id, el)
    else leaders.current.delete(id)
  }
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      <svg aria-hidden className="absolute inset-0 h-full w-full">
        {labels
          .filter((l) => l.kind === 'finding')
          .map((l) => (
            <g key={l.id} ref={registerLeader(l.id)} style={{ visibility: 'hidden' }} className={l.tone}>
              <line stroke="currentColor" strokeWidth={1} strokeOpacity={0.8} />
              <circle r={2.5} fill="currentColor" />
            </g>
          ))}
      </svg>
      {labels.map((l) => {
        const Icon = l.icon
        return l.kind === 'finding' ? (
          <button
            key={l.id}
            ref={register(l.id)}
            type="button"
            onClick={() => l.findingId && openFinding(l.findingId)}
            style={{ visibility: 'hidden' }}
            className={`pointer-events-auto absolute left-0 top-0 flex items-center gap-1 whitespace-nowrap rounded border bg-background/95 px-1.5 py-0.5 font-mono text-[11px] shadow-md ${l.tone}`}
          >
            {Icon && <Icon aria-hidden className="size-3 shrink-0" />}
            {l.text}
            {l.clause && <span className="rounded bg-blue-500/15 px-1 text-blue-700">Tender {l.clause}</span>}
          </button>
        ) : (
          <span
            key={l.id}
            ref={register(l.id)}
            style={{ visibility: 'hidden' }}
            className={`absolute left-0 top-0 whitespace-nowrap rounded bg-background/80 px-1 text-[11px] ${l.tone}`}
          >
            {l.text}
          </span>
        )
      })}
    </div>
  )
}

function CameraRig({ scene, focusAt, coldOpenAt }: { scene: HallScene; focusAt: V3 | null; coldOpenAt: V3 | null }) {
  const { camera, controls } = useThree()
  const reduce = useReducedMotion()
  const goal = useRef<{ pos: THREE.Vector3; target: THREE.Vector3; start: number; dur: number; fromPos: THREE.Vector3; fromTarget: THREE.Vector3 } | null>(null)
  const ctrl = controls as unknown as { target: THREE.Vector3; update(): void } | null

  const fly = (to: V3, distance: number, dur: number) => {
    if (!ctrl) return
    const target = new THREE.Vector3(...to)
    const pos = target.clone().add(new THREE.Vector3(distance * 0.8, distance * 0.7, distance))
    if (reduce) {
      camera.position.copy(pos)
      ctrl.target.copy(target)
      ctrl.update()
      return
    }
    goal.current = { pos, target, start: performance.now(), dur, fromPos: camera.position.clone(), fromTarget: ctrl.target.clone() }
  }

  useEffect(() => {
    if (coldOpenAt) {
      camera.position.set(scene.hall.w * 0.9, scene.hall.w * 0.8, scene.hall.d * 1.6)
      fly(coldOpenAt, 7, 4000)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [coldOpenAt?.join(','), ctrl])

  // `ctrl` is a dependency: when the tab mounts with a focus already set (Show on canvas from the
  // Matrix), OrbitControls registers a frame later and the fly must run then (final review I5).
  useEffect(() => {
    if (focusAt) fly(focusAt, 10, 700)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusAt?.join(','), ctrl])

  useFrame(() => {
    const g = goal.current
    if (!g || !ctrl) return
    const k = Math.min(1, (performance.now() - g.start) / g.dur)
    const e = 1 - Math.pow(1 - k, 3)
    camera.position.lerpVectors(g.fromPos, g.pos, e)
    ctrl.target.lerpVectors(g.fromTarget, g.target, e)
    ctrl.update()
    if (k >= 1) goal.current = null
  })
  return null
}

/**
 * Opens the worst non-pass finding touching any of `ids`, falling back to focus (spec §12 click
 * semantics). Shared by mesh onClick handlers and the keyboard overlay buttons so the two paths
 * for "activating" an element can't drift apart (mirrors SldView's activateNode).
 */
export function activateElements(ids: string[], findings: Finding[], ui: { openFinding(id: string): void; focus(id: string | null): void }): void {
  const worst = findings.filter((f) => ids.includes(f.element_id) && f.status !== 'pass').sort((a, b) => statusRank(b.status) - statusRank(a.status))[0]
  if (worst) ui.openFinding(worst.id)
  else ui.focus(ids[0] ?? null)
}

function HallScene3D({
  scene,
  labels,
  labelEls,
  leaders,
}: {
  scene: HallScene
  labels: SceneLabel[]
  labelEls: RefObject<Map<string, HTMLElement>>
  leaders: RefObject<Map<string, SVGGElement>>
}) {
  const v = useWorkspace()
  const coords = useCoords(scene)
  const { pos, size } = coords
  const openFinding = useUi((s) => s.openFinding)
  const focus = useUi((s) => s.focus)
  const focusId = useUi((s) => s.focusId)

  const pick = (ids: string[]) => activateElements(ids, v.findings, { openFinding, focus })

  const focusAt = useMemo(() => {
    if (!focusId) return null
    const t = scene.tubes.find((x) => x.id === focusId)
    const b = [...scene.racks, ...scene.cdus].find((x) => x.id === focusId)
    const p = t ? midpoint(t.points) : b ? b.center : null
    return p ? pos(p) : null
  }, [focusId, scene, pos])
  const coldOpenAt = useMemo(() => {
    if (currentShot() !== 'cold-open') return null
    const r11 = v.findings.find((f) => f.rule_id === 'R11' && f.status === 'fail')
    const l = r11 && labels.find((x) => x.findingId === r11.id)
    return l ? pos(l.at) : null
  }, [v.findings, labels, pos])

  return (
    <>
      <color attach="background" args={['#0b0d10']} />
      <hemisphereLight args={['#f1f5f9', '#1e293b', 0.85]} />
      <ambientLight intensity={0.2} />
      <directionalLight position={[20, 40, 15]} intensity={1.25} />
      <directionalLight position={[-25, 18, -20]} intensity={0.35} />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]}>
        <planeGeometry args={[scene.hall.w, scene.hall.d]} />
        <meshStandardMaterial color="#161b22" />
      </mesh>
      <Grid position={[0, 0.01, 0]} args={[scene.hall.w, scene.hall.d]} cellSize={1.2} sectionSize={12} cellColor="#202730" sectionColor="#3a4452" fadeDistance={160} />
      {scene.rooms.map((r) => (
        <mesh key={r.id} position={pos(r.center)}>
          <boxGeometry args={size(r.size)} />
          <meshStandardMaterial color="#1b2129" />
          <Edges color="#4b5563" />
        </mesh>
      ))}
      <Instances limit={Math.max(1, scene.columns.length)}>
        <boxGeometry />
        <meshStandardMaterial color={BASE.column} />
        {scene.columns.map((c) => (
          <Instance key={c.id} position={pos(c.center)} scale={size(c.size)} />
        ))}
      </Instances>
      {scene.keepouts.map((k) => (
        <mesh key={k.id} position={pos(k.center)}>
          <boxGeometry args={size(k.size)} />
          <meshStandardMaterial color="#e11d48" transparent opacity={0.1} depthWrite={false} />
          <Edges color="#fb7185" />
        </mesh>
      ))}
      {scene.bays.map((b) => (
        <mesh key={b.id} position={pos(b.center)}>
          <boxGeometry args={size(b.size)} />
          <meshStandardMaterial color="#0c2a44" transparent opacity={0.75} />
          <Edges color="#38bdf8" />
        </mesh>
      ))}
      <Instances limit={Math.max(1, scene.racks.length)}>
        <boxGeometry />
        <meshStandardMaterial roughness={0.75} metalness={0.05} />
        {scene.racks.map((r) => {
          const c = colourFor(r.id, BASE.rack, v)
          return (
            <Instance
              key={r.id}
              position={pos(r.center)}
              scale={size(r.size)}
              color={c.color}
              onClick={(e) => {
                e.stopPropagation()
                pick([r.id])
              }}
            />
          )
        })}
      </Instances>
      <RackOutlines racks={scene.racks} coords={coords} dim={v.highlights.size > 0} />
      {scene.cdus.map((c) => {
        const col = colourFor(c.id, BASE.cdu, v)
        return (
          <mesh
            key={c.id}
            position={pos(c.center)}
            onClick={(e) => {
              e.stopPropagation()
              pick([c.id])
            }}
          >
            <boxGeometry args={size(c.size)} />
            <meshStandardMaterial color={col.color} emissive={col.emissive} emissiveIntensity={col.emissive === '#000000' ? 0 : 0.4} />
            <Edges color="#bfdbfe" />
          </mesh>
        )
      })}
      {scene.tubes.map((t) => (
        <AnimatedTube key={t.id} tube={t} view={v} pos={pos} onPick={() => pick([t.id])} />
      ))}
      <LabelLayout labels={labels} els={labelEls} leaders={leaders} pos={pos} />
      <OrbitControls makeDefault target={[0, 1.5, 0]} maxPolarAngle={Math.PI / 2.1} />
      <CameraRig scene={scene} focusAt={focusAt} coldOpenAt={coldOpenAt} />
    </>
  )
}

/**
 * Keyboard-reachable path onto the canvas (spec "every control keyboard-reachable" — canvas
 * meshes are never focusable). One native <button> per element with a non-pass status; each
 * runs the same activateElements() the meshes use on click. Collapsed behind an "N issues"
 * toggle so it stays visually quiet and never obstructs the camera shot.
 */
export function HallIssueOverlay() {
  const v = useWorkspace()
  const openFinding = useUi((s) => s.openFinding)
  const focus = useUi((s) => s.focus)
  const [open, setOpen] = useState(false)
  const issues = [...v.status].filter(([, s]) => s === 'fail' || s === 'warn')
  if (!issues.length) return null
  return (
    <div className="pointer-events-auto absolute left-2 top-2 z-10 flex flex-col items-start gap-1 text-[11px]">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="rounded border border-zinc-300 bg-background/90 px-2 py-1 text-zinc-700 shadow-sm"
      >
        {issues.length} issue{issues.length === 1 ? '' : 's'}
      </button>
      {open && (
        <div className="flex max-h-48 flex-col gap-0.5 overflow-y-auto rounded border border-zinc-300 bg-background/95 p-1 shadow-md">
          {issues.map(([id, status]) => {
            const Icon = STATUS_META[status].icon
            return (
              <button
                key={id}
                type="button"
                onClick={() => activateElements([id], v.findings, { openFinding, focus })}
                className={`flex items-center gap-1 whitespace-nowrap rounded px-1 py-0.5 text-left ${STATUS_META[status].text}`}
              >
                <Icon aria-hidden className="size-3 shrink-0" />
                {STATUS_META[status].label} · {id}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

/** Cold-open shot (`?shot=cold-open`): show the revision where R11 fails, then its fix with the diff on. */
function useColdOpen() {
  const { bundle } = useWorkspace()
  useEffect(() => {
    if (currentShot() !== 'cold-open') return
    const failing = bundle.revisions.find((r) => (bundle.findings[r.id] ?? []).some((f) => f.rule_id === 'R11' && f.status === 'fail'))
    const fixed = failing && bundle.revisions.find((r) => r.parent === failing.id)
    if (!failing) return
    const ui = useUi.getState()
    ui.setViewRev(failing.id)
    ui.setCompare(false)
    const t = setTimeout(() => {
      if (fixed) {
        useUi.getState().setViewRev(fixed.id)
        useUi.getState().setCompare(true)
      }
    }, 5500)
    return () => clearTimeout(t)
  }, [bundle])
}

export default function HallView() {
  const v = useWorkspace()
  useColdOpen()
  const scene = useMemo(() => (v.model ? buildHallScene(v.model) : null), [v.model])
  const [webgl] = useState(hasWebGL)
  const labels = useMemo(() => (scene ? buildLabels(scene, v) : []), [scene, v])
  const labelEls = useRef(new Map<string, HTMLElement>())
  const leaders = useRef(new Map<string, SVGGElement>())
  if (!scene) return <EmptyState title="No revision yet">The 3D hall is built from the first checked revision.</EmptyState>
  if (!webgl) return <EmptyState tone="error" title="3D needs WebGL">Your browser has WebGL disabled; the SLD and Matrix tabs show the same design.</EmptyState>
  return (
    <div className="relative h-full w-full" role="figure" aria-label="3D hall">
      <Canvas flat camera={{ position: [scene.hall.w * 0.45, scene.hall.w * 0.5, scene.hall.d * 1.15], fov: 40, near: 0.1, far: 500 }} dpr={[1, 2]}>
        <HallScene3D scene={scene} labels={labels} labelEls={labelEls} leaders={leaders} />
      </Canvas>
      <HallLabelOverlay labels={labels} els={labelEls} leaders={leaders} />
      <HallIssueOverlay />
      <div className="pointer-events-none absolute bottom-2 left-2">
        <Legend {...legendKeys(v)} />
      </div>
    </div>
  )
}
