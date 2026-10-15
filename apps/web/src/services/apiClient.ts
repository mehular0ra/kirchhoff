// Typed client for the HTTP API table in plans/2026-10-13-interfaces.md. Every mutation goes
// through /api (clients never write Firestore). Every call is aborted after 12 s (API budget < 10 s),
// except voice, aborted after 25 s (its server budget is 20 s; issue #36).
import type {
  AssetResult,
  Autonomy,
  InboxSnapshot,
  Material,
  Opportunity,
  PursueResult,
  PurchaseRequisition,
  TopologyId,
  TriageResult,
  WhatIfParam,
  WhatIfResult,
} from '@/lib/types'
import { withTimeout } from '@/lib/timeout'

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
  /** For explain_finding: `{text}`, plus an optional `revision` (the id of the earlier revision the answer
   * cites, where the check failed; present only when that differs from the requested one, issue #36). */
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
  inbox(): Promise<InboxSnapshot>
  triage(emailId: string): Promise<TriageResult>
  pursue(emailId: string): Promise<PursueResult>
}

const TIMEOUT_MS = 12_000
/** Push-to-talk (issue #36): the server's /api/voice budget is 20 s (one model round trip plus the tool). */
const VOICE_TIMEOUT_MS = 25_000

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
  inbox_unavailable: 'The live inbox is unavailable; the recorded triage is shown.',
  email_not_found: 'That email is not in the bids inbox.',
  precomputed: 'Only the Hall B email can be triaged live; this one shows the recorded triage.',
  triage_rate_limit: 'You have reached the hourly limit for live triage; the recorded triage is shown.',
  triage_failed: 'The Inbox agent could not finish this triage.',
  not_triaged: 'Triage this email before pursuing it.',
  cannot_pursue: 'Only bids with a Pursue or Clarify verdict in one of our asset packs can be pursued.',
  enterprise_unavailable: 'The ERP and CRM sandbox is not answering right now. The cached snapshot is shown where there is one.',
  run_not_found: 'That run is not in your workspace. It may have been reset or belong to another visitor; start a new run or watch the recorded one.',
  'missing bearer token': 'Your demo session has not signed in yet. Reload the page; seed projects and replays work without it.',
  'invalid app check token': 'The browser check (App Check) did not pass. Disable blockers for this site or reload; seed projects and replays still work.',
  invalid_value: 'That value is outside the range the engine can check. Pick a value within the limits shown.',
  client_timeout: 'The live backend did not answer in time. Try again in a moment; seed projects and replays still work.',
}

// The 12 s bound wraps the whole call (sign-in, App Check and fetch; final review I4).
export { withTimeout }

export function describeApiError(e: unknown): string {
  if (e instanceof ApiError) return DETAIL_TEXT[e.detail] ?? `The live backend answered ${e.status}: ${e.detail}.`
  return 'The live backend is unreachable. Seed projects and replays still work.'
}

export function httpApiClient(
  fetcher: Fetcher,
  plainFetch: (url: string) => Promise<Response> = (u) => fetch(u),
): ApiClient {
  /**
   * The 12 s budget covers the whole call — `fetcher` first awaits Firebase sign-in and an App Check
   * token, and either can hang when reCAPTCHA is blocked — not just the fetch (final review I4).
   */
  function bounded<T>(run: (signal: AbortSignal) => Promise<T>, timeoutMs = TIMEOUT_MS): Promise<T> {
    const ctrl = new AbortController()
    return withTimeout(run(ctrl.signal), timeoutMs, () => {
      ctrl.abort()
      return new ApiError(0, 'client_timeout')
    })
  }

  function call<T>(path: string, init: RequestInit = {}, timeoutMs = TIMEOUT_MS): Promise<T> {
    return bounded((signal) => send<T>(path, { ...init, signal }), timeoutMs)
  }

  async function send<T>(path: string, init: RequestInit): Promise<T> {
    const r = await fetcher(path, init)
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
      return call('/api/voice', { method: 'POST', body: form }, VOICE_TIMEOUT_MS)
    },
    asset: (pack) => post(`/api/asset/${pack}`),
    erpMaterials: () => call('/api/enterprise/erp/materials'),
    erpPrs: () => call('/api/enterprise/erp/prs'),
    crmOpportunities: () => call('/api/enterprise/crm/opportunities'),
    fileBlob: (path) =>
      bounded(async (signal) => {
        // Ruling R19: get the signed URL as JSON, then fetch it with no auth/App Check headers (no CORS preflight).
        const r = await fetcher(`/api/files/${path.replace(/^\/+/, '')}?redirect=0`, { signal })
        if (!r.ok) throw new ApiError(r.status, r.statusText)
        if (r.headers.get('X-Kirchhoff-Inline') === '1') return r.blob() // WS2 local fakes serve bytes inline
        const { url } = (await r.json()) as { url: string }
        const f = await plainFetch(url)
        if (!f.ok) throw new ApiError(f.status, f.statusText)
        return f.blob()
      }),
    inbox: () => call('/api/inbox'),
    triage: (emailId) => post(`/api/inbox/${encodeURIComponent(emailId)}/triage`),
    pursue: (emailId) => post(`/api/inbox/${encodeURIComponent(emailId)}/pursue`),
  }
}
