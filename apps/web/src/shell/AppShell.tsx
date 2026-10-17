import { cn } from 'cn'
import { CircleQuestionMark } from 'lucide-react'
import { useCallback, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { KirchhoffMark } from '@/components/KirchhoffMark'
import { DemoBanner } from '@/components/Labels'
import { Button } from '@/components/ui/button'
import { Checklist } from '@/onboarding/checklist/Checklist'
import { TourHost } from '@/onboarding/tour/TourHost'
import { ShortcutsDialog } from './ShortcutsDialog'
import { useShortcuts } from './useShortcuts'

const nav = [
  { to: '/app', label: 'Projects', end: true },
  // "Inbox" below sm so the nav fits a 390 px phone on one line (D14); the link's name stays "Bids inbox".
  { to: '/app/inbox', label: 'Bids inbox', short: 'Inbox', end: false },
  { to: '/app/integrations', label: 'Integrations', end: false },
]

export function AppShell() {
  const [help, setHelp] = useState(false)
  const { pathname } = useLocation()
  const openHelp = useCallback(() => setHelp(true), [])
  useShortcuts(openHelp)
  return (
    <div className="blueprint flex h-dvh flex-col">
      <a
        href="#main"
        className="sr-only z-[80] rounded bg-foreground px-3 py-1.5 text-sm text-background focus:not-sr-only focus:fixed focus:left-3 focus:top-3"
      >
        Skip to content
      </a>
      <DemoBanner />
      <header className="z-20 flex h-11 shrink-0 items-center gap-3 border-b border-[var(--glass-edge)] bg-[var(--glass-strong)] px-4 shadow-[0_8px_24px_-16px_rgb(30_58_138/0.4)] backdrop-blur-xl backdrop-saturate-150 sm:gap-6">
        <Link to="/app" className="flex items-center gap-2 font-semibold tracking-tight">
          <KirchhoffMark />
          Kirchhoff
        </Link>
        <nav aria-label="Main" className="flex items-center gap-1 text-sm">
          {nav.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                cn(
                  'rounded px-2 py-1 whitespace-nowrap text-muted-foreground hover:bg-white/70 hover:text-foreground',
                  isActive && 'bg-brand/10 font-medium text-brand-text hover:bg-brand/10 hover:text-brand-text',
                )
              }
              aria-label={n.short ? n.label : undefined}
            >
              {n.short ? (
                <>
                  <span className="sm:hidden">{n.short}</span>
                  <span className="hidden sm:inline">{n.label}</span>
                </>
              ) : (
                n.label
              )}
            </NavLink>
          ))}
        </nav>
        <Button data-dev variant="ghost" size="icon-sm" className="ml-auto" aria-label="Help and shortcuts" onClick={openHelp}>
          <CircleQuestionMark aria-hidden />
        </Button>
      </header>
      <main id="main" tabIndex={-1} className="min-h-0 flex-1 focus:outline-none">
        {/* Inside the shell, a crashing view keeps the navigation and the demo banner (M14). */}
        <ErrorBoundary resetKey={pathname}>
          <Outlet />
        </ErrorBoundary>
      </main>
      <Checklist />
      <TourHost />
      <ShortcutsDialog open={help} onOpenChange={setHelp} />
    </div>
  )
}
