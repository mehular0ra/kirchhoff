import { cn } from 'cn'
import {
  BookOpen,
  ChevronDown,
  CircleCheck,
  CircleDot,
  CircleX,
  FileText,
  Hand,
  ListChecks,
  LoaderCircle,
  MessageSquare,
  Wrench,
  type LucideIcon,
} from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'
import { Hint } from '@/components/Hint'
import { AgentDot } from '@/components/Labels'
import { StatusBadge } from '@/components/StatusBadge'
import { AGENTS } from '@/lib/agents'
import { artifactPayload, findingPayload, gatePayload, ledgerPayload, toolPayload } from '@/lib/events'
import { fmtKeyValue } from '@/lib/format'
import { buildLanes, type Lane, type LaneStatus } from '@/lib/select'
import type { RunEvent } from '@/lib/types'
import { useUi } from '@/store/ui'
import { useWorkspace } from './WorkspaceContext'

const LANE_STATUS: Record<LaneStatus, { label: string; icon: LucideIcon; cls: string }> = {
  idle: { label: 'Waiting', icon: CircleDot, cls: 'text-muted-foreground' },
  running: { label: 'Working', icon: LoaderCircle, cls: 'text-blue-700' },
  waiting: { label: 'At gate', icon: Hand, cls: 'text-amber-700' },
  done: { label: 'Done', icon: CircleCheck, cls: 'text-emerald-700' },
  failed: { label: 'Failed', icon: CircleX, cls: 'text-rose-700' },
}

const KIND_ICON: Record<RunEvent['kind'], LucideIcon> = {
  plan: ListChecks,
  tool_call: Wrench,
  tool_result: Wrench,
  message: MessageSquare,
  artifact: FileText,
  finding: CircleCheck,
  gate: Hand,
  ledger: BookOpen,
  status: CircleDot,
}

function EventLine({ ev }: { ev: RunEvent }) {
  const openFinding = useUi((s) => s.openFinding)
  const setViewRev = useUi((s) => s.setViewRev)
  const Icon = KIND_ICON[ev.kind]
  const f = findingPayload(ev)
  if (f) {
    return (
      <button
        type="button"
        className="flex w-full items-center gap-2 text-left hover:text-foreground"
        onClick={() => {
          if (f.rev) setViewRev(f.rev)
          openFinding(f.finding_id)
        }}
      >
        <StatusBadge status={f.status} compact />
        <span className="font-mono">{f.rule_id}</span>
        <span className="truncate font-mono text-muted-foreground">{f.element_id}</span>
      </button>
    )
  }
  const tool = toolPayload(ev)
  const gate = gatePayload(ev)
  const ledger = ledgerPayload(ev)
  const artifact = artifactPayload(ev)
  let text: string = ev.title
  if (tool && ev.kind === 'tool_call') text = `${tool.tool}()`
  if (tool && ev.kind === 'tool_result') {
    const parts = Object.entries(tool.summary).slice(0, 3).map(([k, v]) => fmtKeyValue(k, v))
    text = parts.length ? `${tool.tool} → ${parts.join(' · ')}` : `${tool.tool} ✓`
  }
  if (gate) text = `Gate: ${gate}`
  if (ledger) text = `${ledger.kind.replace('_', ' ')}: ${ledger.text}`
  if (artifact) text = `${artifact.type}: ${ev.title}`
  return (
    <div className="flex items-start gap-2">
      <Icon aria-hidden className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
      <span className="min-w-0">
        <span className="break-words">{text}</span>
        {ev.detail && <span className="block truncate text-muted-foreground">{ev.detail}</span>}
      </span>
    </div>
  )
}

function LaneView({ lane, recordedOnly }: { lane: Lane; recordedOnly: boolean }) {
  const [open, setOpen] = useState(lane.status === 'running' || lane.status === 'waiting')
  const [all, setAll] = useState(false)
  const meta = AGENTS[lane.agent]
  const st = LANE_STATUS[lane.status]
  const StIcon = st.icon
  const shown = all ? lane.events : lane.events.slice(-5)
  const header = (
    <>
      <AgentDot agent={lane.agent} />
      <span className="font-medium text-foreground">{meta.label}</span>
      {/* A recorded design without agent events has no lane activity to report (M3): no status chip. */}
      {!(recordedOnly && lane.status === 'idle') && (
        <span className={cn('ml-auto inline-flex items-center gap-1 text-xs', st.cls)}>
          <StIcon aria-hidden className={cn('size-3.5', lane.status === 'running' && 'animate-spin motion-reduce:animate-none')} />
          {st.label}
        </span>
      )}
    </>
  )
  return (
    <li className="border-b border-border px-3 py-2" style={{ boxShadow: `inset 2px 0 0 0 ${lane.status === 'idle' ? 'transparent' : meta.color.startsWith('#') ? meta.color : '#a78bfa'}` }}>
      {/* A lane with no events has nothing to expand (D10): a plain header, no chevron. */}
      {lane.events.length > 0 ? (
        <button type="button" aria-expanded={open} onClick={() => setOpen(!open)} className="flex w-full items-center gap-2 text-left text-sm">
          {header}
          <ChevronDown aria-hidden className={cn('size-3.5 text-muted-foreground transition-transform', open && 'rotate-180')} />
        </button>
      ) : (
        <div className="flex w-full items-center gap-2 text-sm">{header}</div>
      )}
      {lane.counters.length > 0 && (
        <ul className="mt-1 flex flex-wrap gap-1" aria-label={`${meta.label} summary`}>
          {lane.counters.map((c) => (
            <li key={c} className="rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-[11px] text-zinc-700">
              {c}
            </li>
          ))}
        </ul>
      )}
      <AnimatePresence initial={false}>
        {open && lane.events.length > 0 && (
          <motion.ol
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="mt-2 flex flex-col gap-1.5 overflow-hidden text-xs text-zinc-700"
          >
            {shown.map((ev) => (
              <li key={ev.seq}>
                <EventLine ev={ev} />
              </li>
            ))}
            {lane.events.length > 5 && (
              <li>
                <button type="button" className="text-muted-foreground underline-offset-2 hover:underline" onClick={() => setAll(!all)}>
                  {all ? 'Show recent' : `Show all ${lane.events.length}`}
                </button>
              </li>
            )}
          </motion.ol>
        )}
      </AnimatePresence>
    </li>
  )
}

export function AgentLanes() {
  const { bundle } = useWorkspace()
  const lanes = buildLanes(bundle)
  const recordedOnly = bundle.events.length === 0
  return (
    <nav aria-label="Agent lanes" data-tour="lanes" className="h-full overflow-y-auto">
      <Hint id="lanes" text="One lane per agent: its tool calls, results, findings and logged assumptions. Click a finding to open it.">
        <h2 tabIndex={0} className="px-3 pt-3 pb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Agents
        </h2>
      </Hint>
      {recordedOnly && (
        <p className="px-3 pb-2 text-xs text-muted-foreground">
          This sample shows the recorded result: the checked design, its findings and the sign-off. Each agent&rsquo;s tool
          calls and findings appear here during a live run.
        </p>
      )}
      <ul>
        {lanes.map((l) => (
          <LaneView key={l.agent} lane={l} recordedOnly={recordedOnly} />
        ))}
      </ul>
    </nav>
  )
}
