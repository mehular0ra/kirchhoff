import { CirclePlay, Factory, Inbox, Radio, SunMedium, UtilityPole, Zap, type LucideIcon } from 'lucide-react'
import { Link } from 'react-router'
import { EmptyState } from '@/components/Labels'
import { LoadError } from '@/components/LoadError'
import { ProjectStateBadge } from '@/components/ProjectState'
import { Button } from '@/components/ui/button'
import { useRecordedRun } from '@/data/useRecordedRun'
import { useWorld } from '@/data/useWorld'
import { unreadCount, useInbox } from '@/inbox/useInbox'
import { demoClockLabel, demoNowMs, fmtRelative, tidyPlurals } from '@/lib/format'
import { readJson } from '@/lib/storage'
import type { AssetPack, Project } from '@/lib/types'
import { Checklist } from '@/onboarding/checklist/Checklist'
import { useTour } from '@/onboarding/tour/tour'
import { Welcome } from './Welcome'

const PACKS: { id: AssetPack; label: string; icon: LucideIcon }[] = [
  { id: 'datahall', label: 'AI data halls', icon: Factory },
  { id: 'grid', label: 'Grid', icon: UtilityPole },
  { id: 'solar', label: 'Solar', icon: SunMedium },
]

export function lastLiveRun(pid: string): string | null {
  return readJson<string | null>(`lastRun.${pid}`, null)
}

function ProjectCard({ p, nowMs, recordedRun }: { p: Project; nowMs: number; recordedRun: boolean | null }) {
  const liveRun = p.id === 'hall-b' ? lastLiveRun('hall-b') : null
  const href = liveRun ? `/app/p/${p.id}?run=${liveRun}` : `/app/p/${p.id}`
  return (
    <article
      data-tour={p.id === 'hall-b' ? 'hall-b' : undefined}
      className="group relative flex flex-col gap-2 rounded-lg border bg-card p-4 transition-colors hover:border-zinc-400"
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-medium text-foreground">
          <Link to={href} className="after:absolute after:inset-0 focus-visible:outline-none">
            {p.name}
          </Link>
        </h3>
        {p.sample && <span className="rounded bg-zinc-100 px-1.5 py-0.5 text-[11px] text-muted-foreground">sample</span>}
      </div>
      <p className="text-xs text-muted-foreground">{p.client}</p>
      <div className="mt-auto flex items-center justify-between pt-2">
        {/* The dashboard does not watch the run, so it never claims "Running" for a stored run id (M12). */}
        {liveRun ? (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-blue-700">
            <Radio aria-hidden className="size-3.5" /> Your live run
          </span>
        ) : (
          <ProjectStateBadge state={p.state} />
        )}
        <span className="text-xs text-muted-foreground">{fmtRelative(p.updated_at, nowMs)}</span>
      </div>
      {p.id === 'hall-b' && (
        <div className="relative z-10 flex gap-2 pt-1">
          <Button asChild size="xs">
            <Link to={href}>
              <Zap aria-hidden /> {liveRun ? 'Open your live run' : 'Run it live'}
            </Link>
          </Button>
          {/* Replay only when Hall A carries a recorded run to play (D10). */}
          {recordedRun === true && (
            <Button asChild size="xs" variant="ghost">
              <Link to="/app/p/hall-a?replay=1">
                <CirclePlay aria-hidden /> Replay
              </Link>
            </Button>
          )}
        </div>
      )}
    </article>
  )
}

/** Front door (spec §20): "Bids inbox · N new"; N counts emails this browser has not opened (static first). */
function InboxEntry() {
  const { data, read } = useInbox()
  return (
    <Link
      to="/app/inbox"
      data-tour="inbox"
      className="flex items-center gap-2 self-start rounded-lg border bg-card px-3 py-2 text-sm text-foreground hover:border-zinc-400 focus-visible:outline-2 focus-visible:outline-blue-600"
    >
      <Inbox aria-hidden className="size-4 text-blue-700" />
      {data ? `Bids inbox · ${unreadCount(data, read)} new` : 'Bids inbox'}
    </Link>
  )
}

export function Dashboard() {
  const { world, error } = useWorld()
  const startTour = useTour((s) => s.start)
  const recordedRun = useRecordedRun()
  if (error) return <LoadError error={error} what="the projects" back={false} />
  if (!world) return <EmptyState title="Loading projects…" />
  const activity = [...world.activity].sort((a, b) => b.ts - a.ts)
  const nowMs = demoNowMs(world) // seed times read against the labelled demo clock (D2)
  return (
    <div className="mx-auto grid h-full max-w-7xl grid-cols-1 gap-6 overflow-auto p-6 lg:grid-cols-[1fr_18rem]">
      <Welcome onStartTour={startTour} />
      <section aria-labelledby="projects-h" className="flex flex-col gap-6">
        <div>
          <h1 id="projects-h" className="text-lg font-semibold">
            Projects
          </h1>
          <p className="text-sm text-muted-foreground">
            {world.org.name}
            <span aria-hidden> · </span>
            <span className="text-xs">{demoClockLabel(world)}</span>
          </p>
        </div>
        <InboxEntry />
        {PACKS.map((pack) => {
          const projects = world.projects.filter((p) => p.asset_pack === pack.id)
          if (!projects.length) return null
          const Icon = pack.icon
          return (
            // Tour step 1 spotlights the data-hall group (a target that fits on screen), not the whole column.
            <div key={pack.id} role="group" aria-label={pack.label} data-tour={pack.id === 'datahall' ? 'projects' : undefined} className="flex flex-col gap-3">
              <h2 className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                <Icon aria-hidden className="size-4" /> {pack.label}
              </h2>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {projects.map((p) => (
                  <ProjectCard key={p.id} p={p} nowMs={nowMs} recordedRun={recordedRun} />
                ))}
              </div>
            </div>
          )
        })}
      </section>
      <aside data-dashboard-side className="flex flex-col gap-6">
        <Checklist docked />
        <section aria-labelledby="activity-h">
          <h2 id="activity-h" className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Activity
          </h2>
          <ol className="flex flex-col gap-2 text-sm">
            {activity.map((a) => (
              <li key={a.id} className="border-l border-zinc-300 pl-3">
                <span className="text-foreground">{a.actor}</span> <span className="text-muted-foreground">{tidyPlurals(a.text)}</span>
                <div className="text-xs text-muted-foreground">{fmtRelative(a.ts, nowMs)}</div>
              </li>
            ))}
          </ol>
        </section>
        <section aria-labelledby="team-h">
          <h2 id="team-h" className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Team
          </h2>
          <ul className="flex flex-col gap-2 text-sm">
            {world.people.map((p) => (
              <li key={p.id} className="flex items-center gap-2">
                <span aria-hidden className="grid size-6 place-items-center rounded-full bg-zinc-100 text-[10px] text-zinc-700">
                  {p.initials ?? p.name.slice(0, 2).toUpperCase()}
                </span>
                <span className="text-foreground">{p.name}</span>
                <span className="truncate text-xs text-muted-foreground">{p.role}</span>
              </li>
            ))}
            <li className="flex items-center gap-2 text-muted-foreground">
              <span aria-hidden className="grid size-6 place-items-center rounded-full bg-blue-100 text-[10px] text-blue-800">
                YOU
              </span>
              You (Demo Reviewer)
            </li>
          </ul>
        </section>
      </aside>
    </div>
  )
}
