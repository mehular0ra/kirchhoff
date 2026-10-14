// Live adapter: Firestore onSnapshot over the visitor workspace, assembled into a ProjectBundle
// (spec §11, §14). Firestore documents are `model_dump()`s of the contracts (snake_case).
import { artifactPayload } from '@/lib/events'
import { visibleEvents } from '@/lib/events'
import type {
  Approval,
  Bundle,
  CrmOverlay,
  DesignBrief,
  DesignModel,
  Finding,
  Project,
  ProjectState,
  PurchaseRequisition,
  Revision,
  RunEvent,
  RunRecord,
  StepRecord,
} from '@/lib/types'
import type { DocSnap, LiveSource, Unsubscribe } from './liveSource'

export interface LiveParts {
  project: Project
  run: RunRecord | null
  steps: StepRecord[]
  events: RunEvent[]
  revisions: Revision[]
  findings: Record<string, Finding[]>
  approvals: Approval[]
  prs: PurchaseRequisition[]
  crm: CrmOverlay[]
  brief: DesignBrief | null
  models: Record<string, DesignModel>
}

export function deriveState(run: RunRecord | null, approvals: Approval[], fallback: ProjectState): ProjectState {
  if (!run) return fallback
  if (approvals.some((a) => a.decision === 'approved')) return 'signed'
  if (run.status === 'at_gate' && run.gate === 'review') return 'in_review'
  if (run.status === 'running' || run.status === 'at_gate') return 'running'
  if (run.status === 'done') return 'checked'
  return fallback
}

export function assembleLive(p: LiveParts): Bundle {
  const revisions = p.revisions
    .filter((r) => r.project_id === p.project.id)
    .map((r) => ({ ...r, model: r.model ?? p.models[r.id] ?? null }))
    .sort((a, b) => a.created_at - b.created_at)
  const revIds = new Set(revisions.map((r) => r.id))
  const approvals = p.approvals.filter((a) => revIds.has(a.revision))
  const findings: Record<string, Finding[]> = {}
  for (const id of revIds) findings[id] = p.findings[id] ?? []
  return {
    project: { ...p.project, state: deriveState(p.run, approvals, p.project.state) },
    brief: p.brief,
    runs: p.run ? [p.run] : [],
    steps: p.steps,
    events: visibleEvents(p.events, p.steps),
    revisions,
    findings,
    approvals,
    prs: p.prs.filter((x) => x.project_id === p.project.id),
    crm: [...p.crm].sort((a, b) => b.updated_at - a.updated_at)[0] ?? null,
    what_ifs: [],
  }
}

const withId = <T,>(d: DocSnap): T => ({ ...d.data, id: (d.data.id as string | undefined) ?? d.id }) as unknown as T

export interface LiveOptions {
  uid: string
  runId: string
  project: Project
  /** Resolves a brief/model reference that is a URL or storage path (not a Firestore path). */
  loadJson: (ref: string) => Promise<unknown>
}

export function subscribeLiveBundle(
  src: LiveSource,
  opts: LiveOptions,
  onChange: (b: Bundle) => void,
  onError: (e: Error) => void = () => {},
): Unsubscribe {
  const base = `workspaces/${opts.uid}`
  const runPath = `${base}/runs/${opts.runId}`
  const parts: LiveParts = {
    project: opts.project,
    run: null,
    steps: [],
    events: [],
    revisions: [],
    findings: {},
    approvals: [],
    prs: [],
    crm: [],
    brief: null,
    models: {},
  }
  const unsubs: Unsubscribe[] = []
  const findingSubs = new Map<string, Unsubscribe>()
  const pending = new Set<string>()
  let closed = false
  const emit = () => {
    if (!closed) onChange(assembleLive(parts))
  }

  const resolveRef = async (ref: string): Promise<unknown> => {
    if (ref.startsWith('workspaces/')) return (await src.getDoc(ref))?.data ?? null
    return opts.loadJson(ref)
  }
  /** WS2's brief ref is its step-outputs doc `{step, json}`; `json` holds `{brief: DesignBrief, ...}` (ruling R7). */
  const unwrapBrief = (d: unknown): DesignBrief | null => {
    const o = d && typeof d === 'object' ? (d as Record<string, unknown>) : null
    if (!o) return null
    const inner = typeof o.json === 'string' ? (JSON.parse(o.json) as Record<string, unknown>) : o
    return (inner.brief ?? inner) as unknown as DesignBrief
  }
  const loadBrief = () => {
    const ev = parts.events.find((e) => artifactPayload(e)?.type === 'brief')
    const ref = ev && artifactPayload(ev)!.ref
    if (!ref || parts.brief || pending.has(ref)) return
    pending.add(ref)
    resolveRef(ref)
      .then((d) => {
        const brief = unwrapBrief(d)
        if (brief) parts.brief = brief
        else pending.delete(ref) // the event can precede the step commit: retry on the next snapshot
        emit()
      })
      .catch((e: Error) => {
        pending.delete(ref)
        onError(e)
      })
  }
  const loadModels = () => {
    for (const r of parts.revisions) {
      if (r.model || !r.model_url || parts.models[r.id] || pending.has(r.model_url)) continue
      pending.add(r.model_url)
      const url = r.model_url
      resolveRef(url)
        .then((m) => {
          if (m) parts.models[r.id] = m as DesignModel
          else pending.delete(url)
          emit()
        })
        .catch((e: Error) => {
          pending.delete(url)
          onError(e)
        })
    }
  }
  const syncFindings = () => {
    for (const r of parts.revisions) {
      if (findingSubs.has(r.id)) continue
      findingSubs.set(
        r.id,
        src.watchCollection(
          `${base}/revisions/${r.id}/findings`,
          (docs) => {
            parts.findings[r.id] = docs.map((d) => withId<Finding>(d))
            emit()
          },
          undefined,
          onError,
        ),
      )
    }
  }

  unsubs.push(
    src.watchDoc(runPath, (d) => {
      parts.run = d ? withId<RunRecord>(d) : null
      emit()
    }, onError),
    src.watchCollection(`${runPath}/steps`, (docs) => {
      parts.steps = docs.map((d) => withId<StepRecord>(d))
      loadBrief() // a step commit may have just written the brief's outputs doc
      emit()
    }, undefined, onError),
    src.watchCollection(`${runPath}/events`, (docs) => {
      parts.events = docs.map((d) => d.data as unknown as RunEvent)
      loadBrief()
      emit()
    }, { orderBy: 'seq' }, onError),
    src.watchCollection(`${base}/revisions`, (docs) => {
      parts.revisions = docs.map((d) => withId<Revision>(d))
      syncFindings()
      loadModels()
      emit()
    }, { where: ['project_id', '==', opts.project.id] }, onError),
    src.watchCollection(`${base}/approvals`, (docs) => {
      parts.approvals = docs.map((d) => withId<Approval>(d))
      emit()
    }, undefined, onError),
    src.watchCollection(`${base}/prs`, (docs) => {
      parts.prs = docs.map((d) => withId<PurchaseRequisition>(d))
      emit()
    }, { where: ['project_id', '==', opts.project.id] }, onError),
    src.watchCollection(`${base}/crm`, (docs) => {
      parts.crm = docs.map((d) => ({ opportunity_id: d.id, ...d.data }) as unknown as CrmOverlay)
      emit()
    }, undefined, onError),
  )

  return () => {
    closed = true
    unsubs.forEach((u) => u())
    findingSubs.forEach((u) => u())
  }
}
