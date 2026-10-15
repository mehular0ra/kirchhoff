import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { fixtureIntegrations } from '@/test/fixtures'
import { fakeApi, fakeServices, renderWithProviders } from '@/test/render'
import type { IntegrationsSnapshot } from '@/lib/types'
import realSnapshot from '@/test/fixtures/integrations-real.json'
import { IntegrationsPage } from './Integrations'

test('with the API up, ERP and CRM come from /api/enterprise/* and are labelled sandbox (simulated)', async () => {
  const user = userEvent.setup()
  const snap = fixtureIntegrations()
  const api = fakeApi({
    erpMaterials: vi.fn(async () => snap.erp.materials),
    erpPrs: vi.fn(async () => snap.erp.prs),
    crmOpportunities: vi.fn(async () => snap.crm.opportunities),
  })
  renderWithProviders(<IntegrationsPage />, { services: fakeServices({ api }) })
  const erp = await screen.findByRole('article', { name: 'ERP (SAP-style)' })
  expect(within(erp).getByText('sandbox (simulated)')).toBeInTheDocument()
  expect(within(erp).getByText('2 materials')).toBeInTheDocument()
  expect(within(erp).getByText(/^Connected · last sync/)).toBeInTheDocument()
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
  expect(within(screen.getByRole('article', { name: 'Document store' })).queryByText('sandbox (simulated)')).not.toBeInTheDocument()
  await user.click(within(erp).getByRole('button', { name: 'View data: ERP (SAP-style)' }))
  const materials = await screen.findByRole('table', { name: 'Materials' })
  expect(within(materials).getByText('TX-3150')).toBeInTheDocument()
  expect(within(materials).getByText('98 weeks')).toBeInTheDocument()
})

test('with the API down, the static snapshot renders with a cached note and the handoff strip', async () => {
  renderWithProviders(<IntegrationsPage />)
  expect(await screen.findByText(/API unreachable — showing cached snapshot/)).toBeInTheDocument()
  const handoff = screen.getByRole('region', { name: 'Latest handoff' })
  expect(handoff).toHaveAttribute('data-tour', 'integrations-prs')
  expect(within(handoff).getByText('PR-2026-0142')).toBeInTheDocument()
  expect(within(handoff).getByText('CRM stage: Design approved')).toBeInTheDocument()
  expect(screen.getByRole('article', { name: 'PLM' })).toHaveTextContent('Coming soon')
})

test('M1: each card\'s own status line is icon plus text, never colour alone', async () => {
  renderWithProviders(<IntegrationsPage />)
  const erp = await screen.findByRole('article', { name: 'ERP (SAP-style)' })
  const cachedLine = within(erp).getByText(/^Cached snapshot/)
  expect(cachedLine.querySelector('svg')).toBeTruthy()
  const store = screen.getByRole('article', { name: 'Document store' })
  const connectedLine = within(store).getByText('Connected (Cloud Storage)')
  expect(connectedLine.querySelector('svg')).toBeTruthy()
  const plm = screen.getByRole('article', { name: 'PLM' })
  const comingSoonLine = within(plm).getByText('Coming soon')
  expect(comingSoonLine.querySelector('svg')).toBeTruthy()
})

test('with the real generated snapshot, counts, Hall A PRs and opportunity stages render correctly', async () => {
  const user = userEvent.setup()
  const snap = structuredClone(realSnapshot) as unknown as IntegrationsSnapshot
  renderWithProviders(<IntegrationsPage />, {
    services: fakeServices({
      getJson: vi.fn(async (url: string) => {
        if (url === '/demo/integrations.json') return structuredClone(snap)
        throw new Error(`${url}: 404`)
      }),
    }),
  })
  await screen.findByText(/API unreachable — showing cached snapshot/)
  const erp = screen.getByRole('article', { name: 'ERP (SAP-style)' })
  expect(within(erp).getByText('60 materials')).toBeInTheDocument()
  expect(within(erp).getByText('17 purchase requisitions')).toBeInTheDocument()

  const crm = screen.getByRole('article', { name: 'CRM (Salesforce-style)' })
  expect(within(crm).getByText('9 opportunities')).toBeInTheDocument()

  expect(within(screen.getByRole('article', { name: 'Document store' })).getByText('7 documents')).toBeInTheDocument()
  expect(within(screen.getByRole('article', { name: 'Notifications' })).getByText('6 notifications')).toBeInTheDocument()

  const handoff = screen.getByRole('region', { name: 'Latest handoff' })
  for (const id of ['PR-2026-0142', 'PR-2026-0143', 'PR-2026-0144', 'PR-2026-0145', 'PR-2026-0146', 'PR-2026-0147', 'PR-2026-0148']) {
    expect(within(handoff).getByText(id)).toBeInTheDocument()
  }
  expect(within(handoff).getByText('CRM stage: Design approved')).toBeInTheDocument()
  expect(within(handoff).getByText('CRM stage: Design in progress')).toBeInTheDocument()

  await user.click(within(crm).getByRole('button', { name: 'View data: CRM (Salesforce-style)' }))
  const opps = await screen.findByRole('table', { name: 'Opportunities' })
  for (const stage of ['Negotiation', 'Design approved', 'Design in progress', 'Qualification', 'Closed won', 'Proposal']) {
    expect(within(opps).getAllByText(stage).length).toBeGreaterThan(0)
  }
})

test('I4: with the API hanging (sign-in or App Check stuck), the cached snapshot shows at once with a connecting note', async () => {
  const never = () => new Promise<never>(() => {})
  const api = fakeApi({ erpMaterials: vi.fn(never), erpPrs: vi.fn(never), crmOpportunities: vi.fn(never) })
  renderWithProviders(<IntegrationsPage />, { services: fakeServices({ api }) })
  const handoff = await screen.findByRole('region', { name: 'Latest handoff' })
  expect(within(handoff).getByText('PR-2026-0142')).toBeInTheDocument()
  expect(screen.getByRole('status')).toHaveTextContent(/Connecting to the live sandbox/)
  expect(within(screen.getByRole('article', { name: 'ERP (SAP-style)' })).getByText(/^Cached snapshot/)).toBeInTheDocument()
})

test('backlog [4]: the "API unreachable" note carries an icon as well as text', async () => {
  renderWithProviders(<IntegrationsPage />)
  const note = await screen.findByText(/API unreachable/)
  expect(note.closest('[role="status"]')!.querySelector('svg')).not.toBeNull()
})

test('D5: the handoff names the project, lists each PR\'s material lines, and labels the sandbox once', async () => {
  renderWithProviders(<IntegrationsPage />)
  const handoff = await screen.findByRole('region', { name: 'Latest handoff' })
  expect(await within(handoff).findByText(/Deccan AI Campus · Hall A/)).toBeInTheDocument() // from world.json, not the slug
  expect(within(handoff).queryByText(/hall-a/)).not.toBeInTheDocument()
  expect(within(handoff).getByText(/2 × TX-3150/)).toBeInTheDocument()
  expect(within(handoff).getAllByText('sandbox (simulated)')).toHaveLength(1)
})
