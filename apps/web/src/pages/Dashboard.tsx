import { CirclePlay, Factory, Inbox, SunMedium, UtilityPole, Zap, type LucideIcon } from 'lucide-react'
import { Link } from 'react-router'
import { EmptyState } from '@/components/Labels'
import { ProjectStateBadge } from '@/components/ProjectState'
import { Button } from '@/components/ui/button'
import { useWorld } from '@/data/useWorld'
import { unreadCount, useInbox } from '@/inbox/useInbox'
import { fmtRelative } from '@/lib/format'
import { readJson } from '@/lib/storage'
import type { AssetPack, Project } from '@/lib/types'
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

function ProjectCard({ p }: { p: Project }) {
  const liveRun = p.id === 'hall-b' ? lastLiveRun('hall-b') : null
  const href = liveRun ? `/app/p/${p.id}?run=${liveRun}` : `/app/p/${p.id}`
  return (
    <article
      data-tour={p.id === 'hall-b' ? 'hall-b' : undefined}
      className="group relative flex flex-col gap-2 rounded-lg border bg-card p-4 transition-colors hover:border-zinc-600"
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-medium text-zinc-100">
          <Link to={href} className="after:absolute after:inset-0 focus-visible:outline-none">
            {p.name}
          </Link>
        </h3>
        {p.sample && <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[11px] text-zinc-400">sample</span>}
      </div>
      <p className="text-xs text-zinc-400">{p.client}</p>
      <div className="mt-auto flex items-center justify-between pt-2">
        <ProjectStateBadge state={liveRun ? 'running' : p.state} />
        <span className="text-xs text-zinc-500">{fmtRelative(p.updated_at)}</span>
      </div>
      {p.id === 'hall-b' && (
        <div className="relative z-10 flex gap-2 pt-1">
          <Button asChild size="xs">
            <Link to={href}>
              <Zap aria-hidden /> {liveRun ? 'Open your live run' : 'Run it live'}
            </Link>
          </Button>
          <Button asChild size="xs" variant="ghost">
            <Link to="/app/p/hall-a?replay=1">
              <CirclePlay aria-hidden /> Replay
            </Link>
          </Button>
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
      className="flex items-center gap-2 self-start rounded-lg border bg-card px-3 py-2 text-sm text-zinc-200 hover:border-zinc-600 focus-visible:outline-2 focus-visible:outline-sky-400"
    >
      <Inbox aria-hidden className="size-4 text-sky-300" />
      {data ? `Bids inbox · ${unreadCount(data, read)} new` : 'Bids inbox'}
    </Link>
  )
}

export function Dashboard() {
  const { world, error } = useWorld()
  const startTour = useTour((s) => s.start)
  if (error) return <EmptyState title="Could not load the demo world">{error}</EmptyState>
  if (!world) return <EmptyState title="Loading projects…" />
  const activity = [...world.activity].sort((a, b) => b.ts - a.ts)
  return (
    <div className="mx-auto grid h-full max-w-7xl grid-cols-1 gap-6 overflow-auto p-6 lg:grid-cols-[1fr_18rem]">
      <Welcome onStartTour={startTour} />
      <section aria-labelledby="projects-h" data-tour="projects" className="flex flex-col gap-6">
        <div>
          <h1 id="projects-h" className="text-lg font-semibold">
            Projects
          </h1>
          <p className="text-sm text-zinc-400">{world.org.name}</p>
        </div>
        <InboxEntry />
        {PACKS.map((pack) => {
          const projects = world.projects.filter((p) => p.asset_pack === pack.id)
          if (!projects.length) return null
          const Icon = pack.icon
          return (
            <div key={pack.id} role="group" aria-label={pack.label} className="flex flex-col gap-3">
              <h2 className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-zinc-400">
                <Icon aria-hidden className="size-4" /> {pack.label}
              </h2>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {projects.map((p) => (
                  <ProjectCard key={p.id} p={p} />
                ))}
              </div>
            </div>
          )
        })}
      </section>
      <aside className="flex flex-col gap-6">
        <section aria-labelledby="activity-h">
          <h2 id="activity-h" className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-400">
            Activity
          </h2>
          <ol className="flex flex-col gap-2 text-sm">
            {activity.map((a) => (
              <li key={a.id} className="border-l border-zinc-700 pl-3">
                <span className="text-zinc-200">{a.actor}</span> <span className="text-zinc-400">{a.text}</span>
                <div className="text-xs text-zinc-500">{fmtRelative(a.ts)}</div>
              </li>
            ))}
          </ol>
        </section>
        <section aria-labelledby="team-h">
          <h2 id="team-h" className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-400">
            Team
          </h2>
          <ul className="flex flex-col gap-2 text-sm">
            {world.people.map((p) => (
              <li key={p.id} className="flex items-center gap-2">
                <span aria-hidden className="grid size-6 place-items-center rounded-full bg-zinc-800 text-[10px] text-zinc-300">
                  {p.initials ?? p.name.slice(0, 2).toUpperCase()}
                </span>
                <span className="text-zinc-200">{p.name}</span>
                <span className="truncate text-xs text-zinc-500">{p.role}</span>
              </li>
            ))}
            <li className="flex items-center gap-2 text-zinc-400">
              <span aria-hidden className="grid size-6 place-items-center rounded-full bg-sky-900 text-[10px] text-sky-200">
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
