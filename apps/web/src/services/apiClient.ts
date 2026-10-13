// Typed client for the HTTP API table in plans/2026-10-13-interfaces.md. Every mutation goes
// through /api (clients never write Firestore). Every call is aborted after 12 s (API budget < 10 s).
import type {
  AssetResult,
  Autonomy,
  Material,
  Opportunity,
  PurchaseRequisition,
  TopologyId,
  WhatIfParam,
  WhatIfResult,
} from '@/lib/types'

export type Fetcher = (path: string, init?: RequestInit) => Promise<Response>

export class ApiError extends Error {
  readonly status: number
  readonly detail: string
  constructor(status: number, detail: string) {
    super(`API ${status}: ${detail}`)
    this.status = status
    this.detail = detail
  }
}

export interface VoiceToolResult {
  name: 'what_if' | 'explain_finding' | 'focus_element'
  args: Record<string, unknown>
  result: Record<string, unknown>
}
export interface VoiceResponse {
  transcript: string
  answer: string
  tool_results: VoiceToolResult[]
}

export interface ApiClient {
  health(): Promise<{ ok: boolean; version: string }>
  ensureWorkspace(): Promise<{ uid: string; created: boolean }>
  resetWorkspace(): Promise<void>
  startRun(projectId: string, autonomy: Autonomy): Promise<{ run_id: string }>
  planGate(runId: string, answers: Record<string, string>, planNotes: Record<string, string>): Promise<void>
  optionGate(runId: string, optionId: TopologyId): Promise<void>
  reviewGate(runId: string, decision: 'approved' | 'rejected', comment: string): Promise<void>
  resume(runId: string): Promise<{ resumed: boolean }>
  whatIf(revisionRef: string, param: WhatIfParam, value: number): Promise<WhatIfResult>
  explain(revisionRef: string, findingId: string): Promise<{ text: string }>
  voice(audio: Blob, revisionRef: string): Promise<VoiceResponse>
  asset(pack: 'grid' | 'solar'): Promise<AssetResult>
  erpMaterials(): Promise<Material[]>
  erpPrs(): Promise<PurchaseRequisition[]>
  crmOpportunities(): Promise<Opportunity[]>
  fileBlob(path: string): Promise<Blob>
}

const TIMEOUT_MS = 12_000

/** WS2 error codes (`detail`) → sentences for the UI (ruling R23). No digits: limits are WS2's to state. */
const DETAIL_TEXT: Record<string, string> = {
  global_cap: 'Live runs are at capacity right now. Watch the recorded run instead.',
  visitor_rate_limit: 'You have reached the hourly limit for live runs. Watch the recorded run, or try again later.',
  run_in_progress: 'A live run is still working in your workspace. Try again when it waits at a gate or finishes.',
  wrong_state: 'The run is no longer waiting at this gate; the view catches up in a moment.',
  gate_expired: 'This run waited at its gate for more than a day and expired. Start a new run.',
  open_findings: 'Approve is disabled while findings still fail.',
  invalid_answer: 'That answer is not one of the offered options.',
  option_not_offered: 'That option was not offered for this run.',
  timeout: 'The engine took too long to answer; try again.',
}

export function describeApiError(e: unknown): string {
  if (e instanceof ApiError) return DETAIL_TEXT[e.detail] ?? `The live backend answered ${e.status}: ${e.detail}.`
  return 'The live backend is unreachable. Seed projects and replays still work.'
}

export function httpApiClient(
  fetcher: Fetcher,
  plainFetch: (url: string) => Promise<Response> = (u) => fetch(u),
): ApiClient {
  async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS)
    try {
      const r = await fetcher(path, { ...init, signal: ctrl.signal })
      if (!r.ok) {
        let detail = r.statusText
        try {
          const body = (await r.json()) as { detail?: unknown }
          if (body.detail !== undefined) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
        } catch {
          // non-JSON error body
        }
        throw new ApiError(r.status, detail)
      }
      if (r.status === 204) return undefined as T
      const text = await r.text()
      return (text ? JSON.parse(text) : undefined) as T
    } finally {
      clearTimeout(timer)
    }
  }
  const post = <T>(path: string, body?: unknown) =>
    call<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

  return {
    health: () => call('/api/health'),
    ensureWorkspace: () => post('/api/workspace'),
    resetWorkspace: async () => {
      await post('/api/workspace/reset')
    },
    startRun: (projectId, autonomy) => post('/api/runs', { project_id: projectId, autonomy }),
    planGate: async (runId, answers, planNotes) => {
      await post(`/api/runs/${runId}/gates/plan`, { answers, plan_notes: planNotes })
    },
    optionGate: async (runId, optionId) => {
      await post(`/api/runs/${runId}/gates/option`, { option_id: optionId })
    },
    reviewGate: async (runId, decision, comment) => {
      await post(`/api/runs/${runId}/gates/review`, { decision, comment })
    },
    resume: (runId) => post(`/api/runs/${runId}/resume`),
    whatIf: (revisionRef, param, value) => post('/api/what-if', { revision_ref: revisionRef, param, value }),
    explain: (revisionRef, findingId) => post('/api/explain', { revision_ref: revisionRef, finding_id: findingId }),
    voice: (audio, revisionRef) => {
      const form = new FormData()
      form.append('audio', audio, audio.type.includes('ogg') ? 'clip.ogg' : 'clip.webm')
      form.append('revision_ref', revisionRef)
      return call('/api/voice', { method: 'POST', body: form })
    },
    asset: (pack) => post(`/api/asset/${pack}`),
    erpMaterials: () => call('/api/enterprise/erp/materials'),
    erpPrs: () => call('/api/enterprise/erp/prs'),
    crmOpportunities: () => call('/api/enterprise/crm/opportunities'),
    fileBlob: async (path) => {
      // Ruling R19: get the signed URL as JSON, then fetch it with no auth/App Check headers (no CORS preflight).
      const r = await fetcher(`/api/files/${path.replace(/^\/+/, '')}?redirect=0`)
      if (!r.ok) throw new ApiError(r.status, r.statusText)
      if (r.headers.get('X-Kirchhoff-Inline') === '1') return r.blob() // WS2 local fakes serve bytes inline
      const { url } = (await r.json()) as { url: string }
      const f = await plainFetch(url)
      if (!f.ok) throw new ApiError(f.status, f.statusText)
      return f.blob()
    },
  }
}
