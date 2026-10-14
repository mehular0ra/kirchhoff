import { cn } from 'cn'
import { CircleQuestionMark } from 'lucide-react'
import { useCallback, useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router'
import { DemoBanner } from '@/components/Labels'
import { Button } from '@/components/ui/button'
import { Checklist } from '@/onboarding/checklist/Checklist'
import { TourHost } from '@/onboarding/tour/TourHost'
import { ShortcutsDialog } from './ShortcutsDialog'
import { useShortcuts } from './useShortcuts'

const nav = [
  { to: '/app', label: 'Projects', end: true },
  { to: '/app/inbox', label: 'Bids inbox', end: false },
  { to: '/app/integrations', label: 'Integrations', end: false },
]

export function AppShell() {
  const [help, setHelp] = useState(false)
  const openHelp = useCallback(() => setHelp(true), [])
  useShortcuts(openHelp)
  return (
    <div className="flex h-dvh flex-col">
      <DemoBanner />
      <header className="flex h-11 shrink-0 items-center gap-6 border-b px-4">
        <Link to="/app" className="flex items-center gap-2 font-semibold tracking-tight">
          <span aria-hidden className="grid size-5 place-items-center rounded bg-zinc-100 text-[11px] font-bold text-zinc-900">
            K
          </span>
          Kirchhoff
        </Link>
        <nav aria-label="Main" className="flex items-center gap-1 text-sm">
          {nav.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                cn('rounded px-2 py-1 text-zinc-400 hover:text-zinc-100', isActive && 'bg-accent text-zinc-100')
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
        <Button data-dev variant="ghost" size="icon-sm" className="ml-auto" aria-label="Help and shortcuts" onClick={openHelp}>
          <CircleQuestionMark aria-hidden />
        </Button>
      </header>
      <main className="min-h-0 flex-1">
        <Outlet />
      </main>
      <Checklist />
      <TourHost />
      <ShortcutsDialog open={help} onOpenChange={setHelp} />
    </div>
  )
}
