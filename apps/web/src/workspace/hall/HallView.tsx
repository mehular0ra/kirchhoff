// 3D hall (spec §12): instanced racks, tube busways/feeders/pipes on their tiers, columns,
// keep-out volume, CDU bays; coloured by finding status with icon+text labels; click → finding.
import { Edges, Grid, Html, Instance, Instances, OrbitControls } from '@react-three/drei'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { useReducedMotion } from 'motion/react'
import { useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { EmptyState } from '@/components/Labels'
import { CHAIN_COLORS } from '@/lib/agents'
import { currentShot } from '@/lib/flags'
import { relatedElementIds } from '@/lib/select'
import { STATUS_META, statusRank } from '@/lib/status'
import type { Finding } from '@/lib/types'
import { useUi } from '@/store/ui'
import { Legend } from '../Legend'
import { useWorkspace, type WorkspaceView } from '../WorkspaceContext'
import { buildHallScene, crossingPoint, midpoint, resample, type HallScene, type SceneTube, type V3 } from './hallScene'

const BASE = {
  rack: '#3f4650',
  column: '#2a3038',
  'busway-feeder': '#d4d4d8',
  'cable-feeder': '#a1a1aa',
  'row-busway': '#e4e4e7',
  pipe: '#38bdf8',
  cdu: '#1e3a5f',
} as const
const DIM = '#262b31'
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
  const from = useRef<V3[] | null>(null)
  const target = useMemo(() => resample(tube.points, 32), [tube.points])
  const t0 = useRef(0)
  const [geom, setGeom] = useState(() => tubeGeometry(tube.points, tube.radius, pos))

  useEffect(() => {
    if (reduce || !from.current) {
      setGeom(tubeGeometry(tube.points, tube.radius, pos))
      from.current = target
      return
    }
    t0.current = performance.now()
  }, [target, tube.points, tube.radius, pos, reduce])

  useFrame(() => {
    if (!from.current || from.current === target || !t0.current) return
    const k = Math.min(1, (performance.now() - t0.current) / 900)
    const e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2
    const pts = target.map((p, i) => {
      const a = from.current![i]
      return [a[0] + (p[0] - a[0]) * e, a[1] + (p[1] - a[1]) * e, a[2] + (p[2] - a[2]) * e] as V3
    })
    if (meshRef.current) {
      meshRef.current.geometry.dispose()
      meshRef.current.geometry = tubeGeometry(pts, tube.radius, pos)
    }
    if (k >= 1) {
      from.current = target
      t0.current = 0
    }
  })

  const c = colourFor(tube.id, BASE[tube.kind], view)
  return (
    <mesh
      ref={meshRef}
      geometry={geom}
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

interface Label {
  id: string
  at: V3
  text: string
  clause: string | null
  tone: string
  findingId: string | null
}

function buildLabels(scene: HallScene, v: WorkspaceView): Label[] {
  const tubes = new Map(scene.tubes.map((t) => [t.id, t]))
  const anchor = (id: string): V3 | null => {
    const t = tubes.get(id)
    if (t) return midpoint(t.points)
    const box = [...scene.racks, ...scene.cdus, ...scene.manifolds].find((b) => b.id === id)
    return box ? [box.center[0], box.center[1], box.center[2] * 2 + 0.3] : null
  }
  const known = new Set([...tubes.keys(), ...scene.racks.map((r) => r.id), ...scene.cdus.map((c) => c.id)])
  const out: Label[] = []
  const seenRows = new Set<string>()
  const add = (f: Finding, text: string, tone: string) => {
    const rack = scene.racks.find((r) => r.id === f.element_id)
    if (rack) {
      if (seenRows.has(rack.row)) return
      seenRows.add(rack.row)
    }
    const related = relatedElementIds(f, known)
    const a = tubes.get(related[0])
    const b = related[1] ? tubes.get(related[1]) : undefined
    const at = (a && b && crossingPoint(a.points, b.points)) || anchor(f.element_id)
    if (at) out.push({ id: `${f.id}:${text}`, at, text, clause: f.tender_refs?.[0]?.clause ?? null, tone, findingId: f.id })
  }
  if (v.highlights.size) {
    for (const f of (v.whatIf?.findings ?? []).filter((x) => x.status === 'fail')) add(f, `what-if: Fail · ${f.rule_id} · ${f.element_id}`, STATUS_META.fail.text)
  } else {
    for (const f of [...v.findings].sort((x, y) => statusRank(y.status) - statusRank(x.status))) {
      if (f.status === 'fail' || f.status === 'warn') add(f, `${STATUS_META[f.status].label} · ${f.rule_id} · ${f.element_id}`, STATUS_META[f.status].text)
      else if (v.diff && v.resolved.has(f.element_id)) add(f, `✓ resolved · ${f.rule_id} · ${f.element_id}`, 'text-emerald-300')
    }
  }
  return out.slice(0, 12)
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

  useEffect(() => {
    if (focusAt) fly(focusAt, 10, 700)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusAt?.join(',')])

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

function HallScene3D({ scene }: { scene: HallScene }) {
  const v = useWorkspace()
  const { pos, size } = useCoords(scene)
  const openFinding = useUi((s) => s.openFinding)
  const focus = useUi((s) => s.focus)
  const focusId = useUi((s) => s.focusId)

  const pick = (ids: string[]) => activateElements(ids, v.findings, { openFinding, focus })

  const labels = useMemo(() => buildLabels(scene, v), [scene, v])
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
      <ambientLight intensity={0.55} />
      <directionalLight position={[20, 40, 15]} intensity={1.1} />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]}>
        <planeGeometry args={[scene.hall.w, scene.hall.d]} />
        <meshStandardMaterial color="#111418" />
      </mesh>
      <Grid position={[0, 0.01, 0]} args={[scene.hall.w, scene.hall.d]} cellSize={1.2} sectionSize={12} cellColor="#1c2127" sectionColor="#2f3640" fadeDistance={160} />
      {scene.rooms.map((r) => (
        <group key={r.id}>
          <mesh position={pos(r.center)}>
            <boxGeometry args={size(r.size)} />
            <meshStandardMaterial color="#161b21" />
          </mesh>
          <Html position={pos([r.center[0], r.center[1], 0.4])} center className="pointer-events-none whitespace-nowrap text-[10px] text-zinc-400">
            {r.label}
          </Html>
        </group>
      ))}
      <Instances limit={Math.max(1, scene.columns.length)}>
        <boxGeometry />
        <meshStandardMaterial color={BASE.column} />
        {scene.columns.map((c) => (
          <Instance key={c.id} position={pos(c.center)} scale={size(c.size)} />
        ))}
      </Instances>
      {scene.keepouts.map((k) => (
        <group key={k.id}>
          <mesh position={pos(k.center)}>
            <boxGeometry args={size(k.size)} />
            <meshStandardMaterial color="#e11d48" transparent opacity={0.1} depthWrite={false} />
            <Edges color="#fb7185" />
          </mesh>
          <Html position={pos([k.center[0], k.center[1], k.size[2] + 0.4])} center className="pointer-events-none whitespace-nowrap text-[10px] text-rose-300">
            Keep-out (fire suppression)
          </Html>
        </group>
      ))}
      {scene.bays.map((b) => (
        <group key={b.id}>
          <mesh position={pos(b.center)}>
            <boxGeometry args={size(b.size)} />
            <meshStandardMaterial color="#0c2a44" transparent opacity={0.7} />
          </mesh>
          <Html position={pos([b.center[0], b.center[1], 2.6])} center className="pointer-events-none text-[10px] text-sky-300">
            CDU bay {b.zone}
          </Html>
        </group>
      ))}
      <Instances limit={Math.max(1, scene.racks.length)}>
        <boxGeometry />
        <meshStandardMaterial />
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
          </mesh>
        )
      })}
      {scene.tubes.map((t) => (
        <AnimatedTube key={t.id} tube={t} view={v} pos={pos} onPick={() => pick([t.id])} />
      ))}
      {labels.map((l) => (
        <Html key={l.id} position={pos([l.at[0], l.at[1], l.at[2] + 0.6])} center zIndexRange={[20, 0]}>
          <button
            type="button"
            onClick={() => l.findingId && openFinding(l.findingId)}
            className={`flex items-center gap-1 whitespace-nowrap rounded border border-zinc-600 bg-zinc-950/90 px-1.5 py-0.5 font-mono text-[10px] ${l.tone}`}
          >
            {l.text}
            {l.clause && <span className="rounded bg-sky-500/15 px-1 text-sky-200">Tender {l.clause}</span>}
          </button>
        </Html>
      ))}
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
        className="rounded border border-zinc-700 bg-zinc-950/90 px-2 py-1 text-zinc-300"
      >
        {issues.length} issue{issues.length === 1 ? '' : 's'}
      </button>
      {open && (
        <div className="flex max-h-48 flex-col gap-0.5 overflow-y-auto rounded border border-zinc-700 bg-zinc-950/95 p-1">
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
  if (!scene) return <EmptyState title="No revision yet">The 3D hall is built from the first checked revision.</EmptyState>
  if (!webgl) return <EmptyState title="3D needs WebGL">Your browser has WebGL disabled; the SLD and Matrix tabs show the same design.</EmptyState>
  return (
    <div className="relative h-full w-full" role="figure" aria-label="3D hall">
      <Canvas camera={{ position: [scene.hall.w * 0.45, scene.hall.w * 0.5, scene.hall.d * 1.15], fov: 40, near: 0.1, far: 500 }} dpr={[1, 2]}>
        <HallScene3D scene={scene} />
      </Canvas>
      <HallIssueOverlay />
      <div className="pointer-events-none absolute bottom-2 left-2">
        <Legend diff={!!v.diff} whatIf={v.highlights.size > 0} />
      </div>
    </div>
  )
}
