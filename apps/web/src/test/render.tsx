import { render, type RenderResult } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { vi } from 'vitest'
import { TooltipProvider } from '@/components/ui/tooltip'
import { ApiError, type ApiClient } from '@/services/apiClient'
import { ServicesProvider, type Services } from '@/services/services'
import { useBundleStore } from '@/store/bundles'
import { useConversation } from '@/store/conversation'
import { useUi } from '@/store/ui'
import hallMini from './fixtures/hall-mini.json'
import inbox from './fixtures/inbox.json'
import integrations from './fixtures/integrations.json'
import world from './fixtures/world.json'

const offline = () => Promise.reject(new ApiError(503, 'offline'))

export function fakeApi(overrides: Partial<ApiClient> = {}): ApiClient {
  const base: ApiClient = {
    health: vi.fn(offline),
    ensureWorkspace: vi.fn(offline),
    resetWorkspace: vi.fn(offline),
    startRun: vi.fn(offline),
    planGate: vi.fn(offline),
    optionGate: vi.fn(offline),
    reviewGate: vi.fn(offline),
    resume: vi.fn(offline),
    whatIf: vi.fn(offline),
    explain: vi.fn(offline),
    voice: vi.fn(offline),
    asset: vi.fn(offline),
    erpMaterials: vi.fn(offline),
    erpPrs: vi.fn(offline),
    crmOpportunities: vi.fn(offline),
    fileBlob: vi.fn(offline),
    inbox: vi.fn(offline),
    triage: vi.fn(offline),
    pursue: vi.fn(offline),
  }
  return { ...base, ...overrides }
}

export const STATIC_FILES: Record<string, unknown> = {
  '/demo/world.json': world,
  '/demo/projects/hall-a.json': hallMini,
  '/demo/integrations.json': integrations,
  '/demo/inbox.json': inbox,
}

export function fakeServices(overrides: Partial<Services> = {}): Services {
  return {
    api: fakeApi(),
    getJson: vi.fn(async (url: string) => {
      if (url in STATIC_FILES) return structuredClone(STATIC_FILES[url])
      throw new Error(`${url}: 404`)
    }),
    live: null,
    uid: vi.fn(async () => 'visitor-1'),
    startLiveVoice: null,
    ...overrides,
  }
}

export function resetStores(): void {
  useBundleStore.setState({ entries: {} })
  useUi.getState().resetWorkspaceUi()
  useConversation.setState({ project: null, turns: [], saved: {} })
}

/** Renders `ui` at `route` (matched by `path`) inside router, services and tooltip providers. */
export function renderWithProviders(
  ui: ReactElement,
  { route = '/', path = '*', services = fakeServices() }: { route?: string; path?: string; services?: Services } = {},
): RenderResult & { services: Services } {
  resetStores()
  const result = render(
    <ServicesProvider services={services}>
      <TooltipProvider delayDuration={0}>
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            <Route path={path} element={ui} />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>
    </ServicesProvider>,
  )
  return { ...result, services }
}
