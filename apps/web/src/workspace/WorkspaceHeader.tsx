import { ChevronDown, ChevronRight } from 'lucide-react'
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
import { buildLanes } from '@/lib/select'
import type { ReactNode } from 'react'
import { useWorkspace } from './WorkspaceContext'

const SOURCE_LABEL = { static: 'Recorded design', live: 'Live run', replay: 'Replay' } as const
const PACK_LABEL = { datahall: 'AI data hall', grid: 'Grid', solar: 'Solar' } as const

export function WorkspaceHeader({ actions }: { actions?: ReactNode }) {
  const { bundle, source } = useWorkspace()
  const { world } = useWorld()
  const p = bundle.project
  const working = buildLanes(bundle).filter((l) => l.status === 'running')
  return (
    <div className="flex h-11 items-center gap-3 border-b px-4 text-sm">
      <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1 text-zinc-400">
        <Link to="/app" className="hover:text-zinc-100">
          Kirchhoff
        </Link>
        <ChevronRight aria-hidden className="size-3.5" />
        <h1 className="truncate font-medium text-zinc-100">
          {p.name}
          {p.sample && <span className="text-zinc-500"> (sample)</span>}
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
      <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[11px] text-zinc-300">{SOURCE_LABEL[source]}</span>
      <span className="inline-flex items-center gap-1.5 text-xs text-zinc-400" aria-live="polite">
        {working.length ? (
          <>
            {working.map((l) => (
              <AgentDot key={l.agent} agent={l.agent} className="animate-pulse motion-reduce:animate-none" />
            ))}
            {working.length} agents working
          </>
        ) : (
          'No agents working'
        )}
      </span>
      <div className="ml-auto flex items-center gap-2">{actions}</div>
    </div>
  )
}
