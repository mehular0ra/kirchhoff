import { render, screen } from '@testing-library/react'
import { fixtureBundle } from '@/test/fixtures'
import { WorkspaceProvider } from '../WorkspaceContext'
import { SldView } from './SldView'

test('SLD explains itself when there is no revision yet', () => {
  const b = { ...fixtureBundle(), revisions: [], findings: {} }
  render(
    <WorkspaceProvider bundle={b} source="live">
      <SldView />
    </WorkspaceProvider>,
  )
  expect(screen.getByText('No revision yet')).toBeInTheDocument()
})

test('SLD mounts a figure for a revision with a model', () => {
  render(
    <WorkspaceProvider bundle={fixtureBundle()} source="static">
      <SldView />
    </WorkspaceProvider>,
  )
  expect(screen.getByRole('figure', { name: 'Single-line diagram' })).toBeInTheDocument()
})
