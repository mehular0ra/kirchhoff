import { lazy, Suspense } from 'react'
import { Route, Routes, useLocation } from 'react-router'
import { ErrorBoundary } from './components/ErrorBoundary'
import { EmptyState } from './components/Labels'
import { Dashboard } from './pages/Dashboard'
import { Landing } from './pages/Landing'
import { NotFound } from './pages/NotFound'
import { AppShell } from './shell/AppShell'

// Heavy screens (React Flow + ELK, TanStack, react-pdf, three.js) load on demand.
const WorkspacePage = lazy(() => import('./workspace/WorkspacePage').then((m) => ({ default: m.WorkspacePage })))
const ReviewPage = lazy(() => import('./workspace/review/ReviewPage').then((m) => ({ default: m.ReviewPage })))
const IntegrationsPage = lazy(() => import('./pages/Integrations').then((m) => ({ default: m.IntegrationsPage })))
const AssetPackPage = lazy(() => import('./assetpack/AssetPackPage').then((m) => ({ default: m.AssetPackPage })))

export default function App() {
  const { pathname } = useLocation()
  return (
    <ErrorBoundary resetKey={pathname}>
      <Suspense fallback={<EmptyState title="Loading…" />}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/app" element={<AppShell />}>
            <Route index element={<Dashboard />} />
            <Route path="p/:pid" element={<WorkspacePage />} />
            <Route path="p/:pid/review/:rev" element={<ReviewPage />} />
            <Route path="p/grid-132kv" element={<AssetPackPage pack="grid" pid="grid-132kv" />} />
            <Route path="p/solar-5mwp" element={<AssetPackPage pack="solar" pid="solar-5mwp" />} />
            <Route path="integrations" element={<IntegrationsPage />} />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
    </ErrorBoundary>
  )
}
