import '@xyflow/react/dist/style.css'
import {
  Background,
  Controls,
  MarkerType,
  Panel,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Edge,
} from '@xyflow/react'
import { useReducedMotion } from 'motion/react'
import { useEffect, useMemo, useState } from 'react'
import { EmptyState } from '@/components/Labels'
import { CHAIN_COLORS } from '@/lib/agents'
import type { ChangeKind } from '@/lib/diff'
import type { Discipline } from '@/lib/model'
import { STATUS_META, statusRank, worstStatus } from '@/lib/status'
import type { FindingStatus } from '@/lib/types'
import { useUi } from '@/store/ui'
import { Legend } from '../Legend'
import { useWorkspace } from '../WorkspaceContext'
import { nodeTypes, type SldFlowNode } from './SldNodes'
import { buildSldGraph, layoutSld, MAX_LEVEL, NODE_SIZE } from './sldGraph'

function SldCanvas() {
  const view = useWorkspace()
  const focusId = useUi((s) => s.focusId)
  const openFinding = useUi((s) => s.openFinding)
  const focus = useUi((s) => s.focus)
  const reduce = useReducedMotion()
  const { fitView } = useReactFlow()
  const graph = useMemo(() => (view.model ? buildSldGraph(view.model) : null), [view.model])
  const [pos, setPos] = useState<Map<string, { x: number; y: number }> | null>(null)
  const [reveal, setReveal] = useState(MAX_LEVEL)

  useEffect(() => {
    if (!graph) return
    let alive = true
    layoutSld(graph).then((p) => alive && setPos(p))
    return () => {
      alive = false
    }
  }, [graph])

  // Staged reveal by level whenever a new revision is shown; instant under reduced motion.
  useEffect(() => {
    if (reduce) {
      setReveal(MAX_LEVEL)
      return
    }
    let level = -1
    setReveal(level)
    const id = setInterval(() => {
      level += 1
      setReveal(level)
      if (level >= MAX_LEVEL) clearInterval(id)
    }, 220)
    return () => clearInterval(id)
  }, [view.rev?.id, reduce])

  useEffect(() => {
    if (pos) requestAnimationFrame(() => fitView({ includeHiddenNodes: true, padding: 0.12 }))
  }, [pos, fitView])

  const whatIfActive = view.highlights.size > 0
  const levelOf = useMemo(() => new Map(graph?.nodes.map((n) => [n.id, n.level]) ?? []), [graph])

  // Opens a node's (or clicked flow-node's) worst non-pass finding, falling back to focus.
  // Shared by onNodeClick (mouse) and each node's onKeyDown (Enter/Space) so the two paths can't drift apart.
  const activateNode = (id: string, members: string[]) => {
    const worst = view.findings
      .filter((f) => members.includes(f.element_id) && f.status !== 'pass')
      .sort((a, b) => statusRank(b.status) - statusRank(a.status))[0]
    if (worst) openFinding(worst.id)
    else focus(id)
  }

  const nodes: SldFlowNode[] = useMemo(() => {
    if (!graph || !pos) return []
    return graph.nodes.map((n) => {
      const statuses = n.members.map((m) => view.status.get(m)).filter((s): s is FindingStatus => !!s)
      const changes = n.members.map((m) => view.diff?.byId.get(m)).filter((c): c is ChangeKind => !!c)
      const chain = [...new Set(n.members.flatMap((m) => view.highlights.get(m) ?? []))] as Discipline[]
      const wis = n.members.map((m) => view.whatIfStatus.get(m)).filter((s): s is FindingStatus => !!s)
      const size = NODE_SIZE[n.kind]
      return {
        id: n.id,
        type: 'sld' as const,
        position: pos.get(n.id) ?? { x: 0, y: 0 },
        width: size.w,
        height: size.h,
        hidden: n.level > reveal,
        draggable: false,
        data: {
          kind: n.kind,
          label: n.label,
          sub: n.sub,
          status: worstStatus(statuses),
          change: changes[0] ?? null,
          resolved: n.members.some((m) => view.resolved.has(m)) && !!view.diff,
          chain,
          whatIfStatus: worstStatus(wis),
          dim: whatIfActive && chain.length === 0,
          focused: focusId === n.id || n.members.includes(focusId ?? ''),
          activate: () => activateNode(n.id, n.members),
        },
      }
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- activateNode closes over view, already a dep
  }, [graph, pos, view, reveal, whatIfActive, focusId])

  const edges: Edge[] = useMemo(() => {
    if (!graph || !pos) return []
    return graph.edges.map((e) => {
      const status = view.status.get(e.id) ?? null
      const change = view.diff?.byId.get(e.id) ?? null
      const chain: Discipline | null =
        view.highlights.get(e.id)?.[0] ??
        (view.highlights.has(e.source) && view.highlights.has(e.target) ? view.highlights.get(e.target)![0] : null)
      const color = chain
        ? CHAIN_COLORS[chain]
        : status && statusRank(status) >= statusRank('warn')
          ? STATUS_META[status].hex
          : change
            ? '#fbbf24'
            : '#52525b'
      const statusText = status && status !== 'pass' ? ` · ${STATUS_META[status].label}` : ''
      return {
        id: e.id,
        source: e.source,
        target: e.target,
        type: 'smoothstep',
        hidden: (levelOf.get(e.target) ?? 0) > reveal,
        label: e.label ? `${e.label}${statusText}${change ? ' · changed' : ''}` : undefined,
        labelStyle: { fill: '#e4e4e7', fontFamily: 'JetBrains Mono Variable, monospace', fontSize: 10 },
        labelBgStyle: { fill: '#0b0d10' },
        style: { stroke: color, strokeWidth: e.label ? 2.5 : 1.5, strokeDasharray: change ? '6 4' : undefined },
        markerEnd: { type: MarkerType.Arrow, color, width: 12, height: 12 },
        opacity: whatIfActive && !chain ? 0.35 : 1,
      }
    })
  }, [graph, pos, view, reveal, levelOf, whatIfActive])

  // Waits for the layout (`pos`): when the tab mounts with a focus already set (Show on canvas from
  // the Matrix), the first run has no positions yet (final review I5). A focused feeder frames both ends.
  useEffect(() => {
    if (!focusId || !graph || !pos) return
    const target = graph.nodes.find((n) => n.id === focusId || n.members.includes(focusId))
    const edge = target ? null : graph.edges.find((e) => e.id === focusId)
    const ids = target ? [target.id] : edge ? [edge.source, edge.target] : []
    if (!ids.length) return
    const raf = requestAnimationFrame(() => fitView({ nodes: ids.map((id) => ({ id })), duration: reduce ? 0 : 500, maxZoom: 1.3, padding: 0.6 }))
    return () => cancelAnimationFrame(raf)
  }, [focusId, graph, pos, fitView, reduce])

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      nodesDraggable={false}
      nodesConnectable={false}
      nodesFocusable={false}
      minZoom={0.15}
      proOptions={{ hideAttribution: true }}
      onNodeClick={(_, node) => {
        const spec = graph?.nodes.find((n) => n.id === node.id)
        activateNode(node.id, spec?.members ?? [node.id])
      }}
      onEdgeClick={(_, edge) => {
        const f = view.findings.find((x) => x.element_id === edge.id && x.status !== 'pass')
        if (f) openFinding(f.id)
        else focus(edge.id)
      }}
    >
      <Background gap={24} color="#1f242b" />
      <Controls showInteractive={false} position="top-right" />
      <Panel position="bottom-left">
        <Legend diff={!!view.diff} whatIf={whatIfActive} />
      </Panel>
    </ReactFlow>
  )
}

export function SldView() {
  const { model } = useWorkspace()
  if (!model) {
    return (
      <EmptyState title="No revision yet">
        The single-line diagram is drawn from the first checked revision, after Power and Layout have run.
      </EmptyState>
    )
  }
  return (
    <div className="h-full w-full" aria-label="Single-line diagram" role="figure">
      <ReactFlowProvider>
        <SldCanvas />
      </ReactFlowProvider>
    </div>
  )
}
