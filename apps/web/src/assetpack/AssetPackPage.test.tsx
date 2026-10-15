import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { normalizeBundle, type AssetResult, type ProjectBundle } from '@/lib/types'
import grid from '@/test/fixtures/grid-132kv.json'
import gridReal from '@/test/fixtures/grid-132kv-real.json'
import solarReal from '@/test/fixtures/solar-5mwp.json'
import { fakeApi, fakeServices, renderWithProviders, STATIC_FILES } from '@/test/render'
import { assetResultFrom, chosenOption, geometryShapes, miniSld, optionColumns } from './assetResult'
import { AssetPackPage } from './AssetPackPage'

const services = (api = fakeApi()) =>
  fakeServices({
    api,
    getJson: vi.fn(async (url: string) => {
      if (url === '/demo/projects/grid-132kv.json') return structuredClone(grid)
      if (url === '/demo/projects/solar-5mwp.json') return structuredClone(solarReal)
      if (url in STATIC_FILES) return structuredClone(STATIC_FILES[url])
      throw new Error(`${url}: 404`)
    }),
  })

test('the asset result is read from the evaluate_grid tool_result event', () => {
  const r = assetResultFrom(normalizeBundle(grid as unknown as ProjectBundle))!
  expect(r.recommended).toBe('ACSR-ZEBRA')
  expect(optionColumns(r.options)).toEqual(['ampacity_a', 'regulation_pct', 'losses_kw'])
  const s = geometryShapes(r.geometry)
  expect(s.lines.map((l) => l.id)).toEqual(['route'])
  expect(s.points.map((p) => p.id)).toEqual(['substation'])
  expect(geometryShapes({ field: [[0, 0], [10, 0], [10, 5]], tables: [[1, 1, 2, 2]] })).toMatchObject({
    polygons: [{ id: 'field' }],
    rects: [{ id: 'tables-0', r: [1, 1, 2, 2] }],
  })
})

test('the Asset agent choice wins over recommended; WS1 grid nodes/edges become the mini SLD', () => {
  const base: AssetResult = { options: [], recommended: 'ACSR-ZEBRA', findings: [], geometry: {} }
  expect(chosenOption(base)).toBe('ACSR-ZEBRA')
  expect(chosenOption({ ...base, choice: { option: 'ACSR-MOOSE', reason: 'r', source: 'agent' } })).toBe('ACSR-MOOSE')
  const sld = miniSld({
    ...base,
    geometry: { nodes: [{ id: 'GRID', kv: 132 }, { id: 'SS-33', kv: 33 }], edges: [{ id: 'L-132', src: 'GRID', dst: 'SS-33' }] },
  })
  expect(sld?.nodes.map((n) => n.label)).toEqual(['132 kV', '33 kV'])
  expect(sld?.edges[0]).toEqual({ src: 'GRID', dst: 'SS-33', label: 'L-132' })
  expect(miniSld(base)).toBeNull()
})

test('grid screen shows conductor options with units, the recommendation, checks, geometry and mini SLD', async () => {
  renderWithProviders(<AssetPackPage pack="grid" pid="grid-132kv" />, { services: services() })
  const table = await screen.findByRole('table', { name: 'Asset options' })
  expect(within(table).getByText('Ampacity (A)')).toBeInTheDocument()
  expect(within(table).getByText('Regulation (%)')).toBeInTheDocument()
  expect(within(within(table).getByText('ACSR Zebra').closest('tr')!).getByText('Recommended')).toBeInTheDocument()
  expect(screen.getByText('Recommends ACSR Zebra: lowest-loss option with regulation margin')).toBeInTheDocument()
  expect(screen.getByText('Zebra carries 790 A against a 500 A requirement.')).toBeInTheDocument()
  expect(screen.getByRole('img', { name: 'Site geometry' }).querySelector('polyline')).not.toBeNull()
  expect(within(screen.getByRole('region', { name: 'Mini SLD' })).getByText('2 × 50 MVA 132/33 kV')).toBeInTheDocument()
  expect(screen.getByText('IEC-based, illustrative values, not for construction')).toBeInTheDocument()
})

test('re-run replaces the recorded result with the engine result', async () => {
  const user = userEvent.setup()
  const fresh: AssetResult = { options: [{ id: 'ACSR-MOOSE', name: 'ACSR Moose', ampacity_a: 880 }], recommended: 'ACSR-MOOSE', findings: [], geometry: {} }
  const api = fakeApi({ asset: vi.fn(async () => fresh) })
  renderWithProviders(<AssetPackPage pack="grid" pid="grid-132kv" />, { services: services(api) })
  await user.click(await screen.findByRole('button', { name: /re-run with the engine/i }))
  expect(api.asset).toHaveBeenCalledWith('grid')
  const table = screen.getByRole('table', { name: 'Asset options' })
  expect(within(within(table).getByText('ACSR Moose').closest('tr')!).getByText('Recommended')).toBeInTheDocument()
})

test('the re-run button cannot double-submit', async () => {
  const user = userEvent.setup()
  let resolveAsset!: (r: AssetResult) => void
  const asset = vi.fn(() => new Promise<AssetResult>((resolve) => (resolveAsset = resolve)))
  const api = fakeApi({ asset })
  renderWithProviders(<AssetPackPage pack="grid" pid="grid-132kv" />, { services: services(api) })
  const button = await screen.findByRole('button', { name: /re-run with the engine/i })
  await user.click(button)
  expect(button).toBeDisabled()
  await user.click(button) // second click while pending must not re-trigger the API
  expect(api.asset).toHaveBeenCalledTimes(1)
  resolveAsset({ options: [], recommended: 'ACSR-ZEBRA', findings: [], geometry: {} })
  await screen.findByRole('button', { name: /re-run with the engine/i, hidden: false })
})

test('a failed re-run shows an error with icon and text, keeping the recorded result', async () => {
  const user = userEvent.setup()
  const erroringApi = fakeApi({ asset: vi.fn(async () => Promise.reject(new Error('offline'))) })
  renderWithProviders(<AssetPackPage pack="grid" pid="grid-132kv" />, { services: services(erroringApi) })
  await user.click(await screen.findByRole('button', { name: /re-run with the engine/i }))
  const alert = await screen.findByRole('alert')
  expect(alert.querySelector('svg')).not.toBeNull()
  expect(within(alert).getByText(/unreachable/i)).toBeInTheDocument()
})

test('real grid bundle: conductor options and recommendation come from the engine, with fault-level findings', async () => {
  renderWithProviders(<AssetPackPage pack="grid" pid="grid-132kv" />, {
    services: fakeServices({
      getJson: vi.fn(async (url: string) => {
        if (url === '/demo/projects/grid-132kv.json') return structuredClone(gridReal)
        if (url in STATIC_FILES) return structuredClone(STATIC_FILES[url])
        throw new Error(`${url}: 404`)
      }),
    }),
  })
  const table = await screen.findByRole('table', { name: 'Asset options' })
  expect(within(table).getByText('ACSR Dog')).toBeInTheDocument()
  expect(within(table).getByText('ACSR Panther')).toBeInTheDocument()
  expect(within(within(table).getByText('ACSR Zebra').closest('tr')!).getByText('Recommended')).toBeInTheDocument()
  expect(screen.getByText(/132 kV fault level/)).toBeInTheDocument()
  expect(screen.getByText(/33 kV fault level/)).toBeInTheDocument()
  expect(screen.getAllByText(/11.58 kA/).length).toBeGreaterThan(0)
  expect(screen.getAllByText(/31.5 kA/).length).toBeGreaterThan(0)
})

test('real solar bundle: STR-28 is recommended with Voc, table count, DC/AC and clear-sky yield from the engine', async () => {
  renderWithProviders(<AssetPackPage pack="solar" pid="solar-5mwp" />, { services: services() })
  const table = await screen.findByRole('table', { name: 'Asset options' })
  const str28Row = within(table).getAllByText('STR-28')[0].closest('tr')!
  expect(within(str28Row).getByText('Recommended')).toBeInTheDocument()
  expect(within(str28Row).getByText('1,463.7')).toBeInTheDocument()
  expect(within(table).getByText('327')).toBeInTheDocument()
  expect(within(str28Row).getByText('1.26')).toBeInTheDocument()
  const checks = screen.getByRole('region', { name: 'Checks' })
  expect(within(checks).getAllByText(/1,500/).length).toBeGreaterThan(0)
  expect(screen.getByText(/2,639 kWh\/kWp/)).toBeInTheDocument()
  expect(screen.getByText(/clear-sky \(no weather data\)/i)).toBeInTheDocument()
})

test('backlog [7]: boolean *_ok/passes columns are hidden (the Checker section covers them); passes reads as a status', async () => {
  renderWithProviders(<AssetPackPage pack="solar" pid="solar-5mwp" />, { services: services() })
  const table = await screen.findByRole('table', { name: 'Asset options' })
  expect(within(table).getAllByRole('columnheader')).toHaveLength(9)
  expect(within(table).queryByText('true')).not.toBeInTheDocument()
  expect(within(table).queryByText('false')).not.toBeInTheDocument()
  expect(within(table).getByText('DC capacity (kWp)')).toBeInTheDocument()
  expect(within(table).getByText('DC/AC ratio')).toBeInTheDocument()
  // STR-30 fails Voc in the engine's option dict: icon + text next to the option name.
  expect(within(within(table).getAllByText('STR-30')[0].closest('tr')!).getByText('Fail')).toBeInTheDocument()
})
