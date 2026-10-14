// Replay = a static bundle's events played back on a timer (spec §11). frameAt() derives the
// bundle as it looked after `cursor` events; nothing is computed beyond revealing recorded data.
import { artifactPayload, findingPayload, planPayload, refTail } from '@/lib/events'
import type { Bundle, Finding } from '@/lib/types'
import type { ReplayState } from '@/store/bundles'

/** seq of each finding event → revision it belongs to (payload.rev, else the latest revision artifact). */
function attribution(full: Bundle): Map<number, string> {
  const out = new Map<number, string>()
  let cur: string | null = null
  for (const e of full.events) {
    const a = artifactPayload(e)
    if (a?.type === 'revision') cur = refTail(a.ref)
    const f = findingPayload(e)
    if (f) {
      const rev = f.rev ?? cur ?? full.revisions[0]?.id
      if (rev) out.set(e.seq, rev)
    }
  }
  return out
}

export function frameAt(full: Bundle, cursor: number): Bundle {
  const total = full.events.length
  if (cursor >= total) return full
  const played = full.events.slice(0, Math.max(0, cursor))
  const attr = attribution(full)
  const has = (pred: (e: Bundle['events'][number]) => boolean) => played.some(pred)
  const hasAny = (pred: (e: Bundle['events'][number]) => boolean) => full.events.some(pred)

  const revealed = new Set<string>()
  const shown = new Map<string, Set<string>>()
  for (const e of played) {
    const a = artifactPayload(e)
    if (a?.type === 'revision') revealed.add(refTail(a.ref))
    const f = findingPayload(e)
    const rev = attr.get(e.seq)
    if (f && rev) {
      revealed.add(rev)
      shown.set(rev, (shown.get(rev) ?? new Set()).add(f.finding_id))
    }
  }
  const revsWithEvents = new Set(attr.values())
  const findings: Record<string, Finding[]> = {}
  for (const rev of revealed) {
    const all = full.findings[rev] ?? []
    findings[rev] = revsWithEvents.has(rev) ? all.filter((f) => shown.get(rev)?.has(f.id)) : all
  }

  const isBrief = (e: Bundle['events'][number]) => artifactPayload(e)?.type === 'brief'
  const isOptions = (e: Bundle['events'][number]) => artifactPayload(e)?.type === 'options'
  const isPlan = (e: Bundle['events'][number]) => planPayload(e) !== null
  const inP3 = has((e) => e.phase === 'p3' || e.phase === 'p4')
  const inP4 = has((e) => e.phase === 'p4')
  const last = played[played.length - 1]
  const playedSteps = new Set(played.map((e) => e.step))

  return {
    ...full,
    project: { ...full.project, state: 'running' },
    brief: has(isBrief) || (!hasAny(isBrief) && played.length > 0) ? full.brief : null,
    runs: full.runs.map((r) => ({
      ...r,
      status: 'running' as const,
      phase: last?.phase ?? 'p1',
      gate: null,
      plan: has(isPlan) || !hasAny(isPlan) ? r.plan : [],
      open_questions: has(isPlan) || !hasAny(isPlan) ? r.open_questions : [],
      options: has(isOptions) || (!hasAny(isOptions) && inP3) ? r.options : [],
      selected_option: inP3 ? r.selected_option : null,
      finished_at: null,
    })),
    steps: full.steps
      .filter((s) => playedSteps.has(s.id))
      .map((s) => ({ ...s, status: s.id === last?.step ? ('running' as const) : s.status, finished_at: s.id === last?.step ? null : s.finished_at })),
    events: played,
    revisions: full.revisions.filter((r) => revealed.has(r.id)),
    findings,
    approvals: inP4 ? full.approvals : [],
    prs: inP4 ? full.prs : [],
    crm: inP4 ? full.crm : null,
  }
}

export interface ReplayControls {
  play(): void
  pause(): void
  seek(cursor: number): void
  setSpeed(speed: number): void
  dispose(): void
  state(): ReplayState
}

/** Recorded gaps are compressed by `speed` and clamped so dead air never exceeds 1.5 s. */
export function createReplay(
  full: Bundle,
  opts: { speed?: number; autoplay?: boolean; onFrame: (b: Bundle, s: ReplayState) => void },
): ReplayControls {
  const events = full.events
  let cursor = 0
  let speed = opts.speed ?? 8
  let playing = false
  let timer: ReturnType<typeof setTimeout> | null = null

  const state = (): ReplayState => ({
    cursor,
    total: events.length,
    playing,
    speed,
    elapsedS: cursor > 0 ? events[cursor - 1].ts - events[0].ts : 0,
  })
  const emit = () => opts.onFrame(frameAt(full, cursor), state())
  const delayMs = () => {
    if (cursor === 0) return 300
    const gapS = events[cursor].ts - events[cursor - 1].ts
    return Math.min(1500, Math.max(40, (gapS * 1000) / speed))
  }
  const stop = () => {
    if (timer) clearTimeout(timer)
    timer = null
  }
  const tick = () => {
    if (cursor >= events.length) {
      playing = false
      emit()
      return
    }
    timer = setTimeout(() => {
      cursor += 1
      emit()
      tick()
    }, delayMs())
  }

  const controls: ReplayControls = {
    play() {
      if (playing) return
      if (cursor >= events.length) cursor = 0
      playing = true
      emit()
      tick()
    },
    pause() {
      playing = false
      stop()
      emit()
    },
    seek(n) {
      cursor = Math.max(0, Math.min(events.length, n))
      emit()
      if (playing) {
        stop()
        tick()
      }
    },
    setSpeed(s) {
      speed = s
      emit()
    },
    dispose() {
      playing = false
      stop()
    },
    state,
  }
  emit()
  if (opts.autoplay ?? true) controls.play()
  return controls
}
