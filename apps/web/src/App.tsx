import { Route, Routes } from 'react-router'
import { Dashboard } from './pages/Dashboard'
import { Landing } from './pages/Landing'
import { NotFound } from './pages/NotFound'
import { AppShell } from './shell/AppShell'
import { WorkspacePage } from './workspace/WorkspacePage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/app" element={<AppShell />}>
        <Route index element={<Dashboard />} />
        <Route path="p/:pid" element={<WorkspacePage />} />
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}
