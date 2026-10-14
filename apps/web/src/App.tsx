import { Route, Routes } from 'react-router'
import { AssetPackPage } from './assetpack/AssetPackPage'
import { Dashboard } from './pages/Dashboard'
import { IntegrationsPage } from './pages/Integrations'
import { Landing } from './pages/Landing'
import { NotFound } from './pages/NotFound'
import { AppShell } from './shell/AppShell'
import { ReviewPage } from './workspace/review/ReviewPage'
import { WorkspacePage } from './workspace/WorkspacePage'

export default function App() {
  return (
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
  )
}
