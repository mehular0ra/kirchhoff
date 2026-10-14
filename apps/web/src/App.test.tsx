import { screen } from '@testing-library/react'
import { vi } from 'vitest'
import { useWorldStore } from '@/data/useWorld'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { renderWithProviders } from '@/test/render'
import App from './App'

beforeEach(() => {
  localStorage.setItem('kirchhoff.welcomed', 'true')
  useWorldStore.setState({ world: null, error: null, loading: false })
})

test('lazy routes resolve: review page and integrations', async () => {
  const { unmount } = renderWithProviders(<App />, { route: '/app/p/hall-a/review/r2' })
  expect(await screen.findByRole('figure', { name: 'Approval stamp' })).toBeInTheDocument()
  unmount()
  renderWithProviders(<App />, { route: '/app/integrations' })
  expect(await screen.findByRole('heading', { name: 'Integrations' })).toBeInTheDocument()
})

test('presentation mode hides dev affordances: checklist and help carry data-dev', async () => {
  renderWithProviders(<App />, { route: '/app' })
  await screen.findByText('Deccan AI Campus · Hall A')
  expect(screen.getByRole('complementary', { name: 'Getting started' })).toHaveAttribute('data-dev')
  expect(screen.getByRole('button', { name: 'Help and shortcuts' })).toHaveAttribute('data-dev')
  expect(screen.getByRole('note')).not.toHaveAttribute('data-dev') // the fictional-data banner always shows
})

test('a crashing view shows a recoverable error instead of a blank page', () => {
  const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
  const Boom = () => {
    throw new Error('boom')
  }
  renderWithProviders(
    <ErrorBoundary resetKey="/x">
      <Boom />
    </ErrorBoundary>,
  )
  expect(screen.getByText('This view hit an error')).toBeInTheDocument()
  spy.mockRestore()
})

test('every demo route renders inside the error boundary without crashing', async () => {
  const pids = ['hall-a', 'hall-b', 'grid-132kv', 'solar-5mwp', 'vindhya-lv']
  for (const pid of pids) {
    const { unmount } = renderWithProviders(<App />, { route: `/app/p/${pid}` })
    await screen.findAllByText(/./)
    unmount()
  }
  {
    const { unmount } = renderWithProviders(<App />, { route: '/app/integrations' })
    await screen.findByRole('heading', { name: 'Integrations' })
    unmount()
  }
  {
    const { unmount } = renderWithProviders(<App />, { route: '/app/p/hall-a/review/r2' })
    await screen.findByRole('figure', { name: 'Approval stamp' })
    unmount()
  }
})
