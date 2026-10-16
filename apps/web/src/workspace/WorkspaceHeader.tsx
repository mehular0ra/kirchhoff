import { ChevronDown, ChevronRight, Stamp } from 'lucide-react'
import { Link } from 'react-router'
import { AgentDot } from '@/components/Labels'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useWorld } from '@/data/useWorld'
import { buildLanes, signedRevision } from '@/lib/select'
import type { ReactNode } from 'react'
import { useWorkspace } from './WorkspaceContext'

const SOURCE_LABEL = { static: 'Recorded design', live: 'Live run', replay: 'Replay' } as const
const PACK_LABEL = { datahall: 'AI data hall', grid: 'Grid', solar: 'Solar' } as const

export function WorkspaceHeader({ actions }: { actions?: ReactNode }) {
  const { bundle, source } = useWorkspace()
  const { world } = useWorld()
  const p = bundle.project
  const working = buildLanes(bundle).filter((l) => l.status === 'running')
  // "No agents working" only makes sense for a live run; a recorded design says what it is (D4).
  const signed = signedRevision(bundle)
  return (
    <div className="flex h-11 min-w-0 items-center gap-3 overflow-x-auto whitespace-nowrap border-b px-4 text-sm">
      <nav aria-label="Breadcrumb" className="flex min-w-40 items-center gap-1 overflow-hidden text-muted-foreground">
        <Link to="/app" className="shrink-0 hover:text-foreground">
          Kirchhoff
        </Link>
        <ChevronRight aria-hidden className="size-3.5" />
        <h1 className="truncate font-medium text-foreground">
          {p.name}
          {p.sample && <span className="text-muted-foreground"> (sample)</span>}
        </h1>
      </nav>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="xs">
            {PACK_LABEL[p.asset_pack]} <ChevronDown aria-hidden />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          <DropdownMenuLabel>Asset packs</DropdownMenuLabel>
          {(world?.projects ?? []).map((wp) => (
            <DropdownMenuItem key={wp.id} asChild>
              <Link to={`/app/p/${wp.id}`}>
                {PACK_LABEL[wp.asset_pack]} · {wp.name}
              </Link>
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
      <span className="rounded bg-zinc-100 px-1.5 py-0.5 text-[11px] text-zinc-700">{SOURCE_LABEL[source]}</span>
      <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground" aria-live="polite">
        {working.length ? (
          <>
            {working.map((l) => (
              <AgentDot key={l.agent} agent={l.agent} className="animate-pulse motion-reduce:animate-none" />
            ))}
            {working.length} {working.length === 1 ? 'agent' : 'agents'} working
          </>
        ) : source === 'live' ? (
          'No agents working'
        ) : signed ? (
          <span className="inline-flex items-center gap-1 text-emerald-700">
            <Stamp aria-hidden className="size-3.5" />
            {`signed ${signed.id}`}
          </span>
        ) : null}
      </span>
      <div className="ml-auto flex items-center gap-2">{actions}</div>
    </div>
  )
}
