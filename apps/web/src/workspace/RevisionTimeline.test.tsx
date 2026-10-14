import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { fixtureBundle } from '@/test/fixtures'
import { resetStores } from '@/test/render'
import { RevisionTimeline } from './RevisionTimeline'
import { WorkspaceProvider } from './WorkspaceContext'

function renderTimeline(bundle = fixtureBundle()) {
  resetStores()
  return render(
    <MemoryRouter>
      <WorkspaceProvider bundle={bundle} source="static">
        <RevisionTimeline />
      </WorkspaceProvider>
    </MemoryRouter>,
  )
}

test('M7: a revision pill says "warn" when it has warnings and never "all pass" before any check', () => {
  const b = fixtureBundle()
  b.findings = { ...b.findings, r2: b.findings.r2 } // r2: no fails, one warn (R10 BR-R1)
  renderTimeline(b)
  expect(screen.getByRole('button', { name: /r1/ })).toHaveTextContent('2 fail')
  expect(screen.getByRole('button', { name: /r2/ })).toHaveTextContent('1 warn')
  expect(screen.getByRole('button', { name: /r2/ })).not.toHaveTextContent('all pass')
})

test('M7: a revision without findings yet reads "not checked yet"', () => {
  const b = fixtureBundle()
  b.findings = { r1: b.findings.r1 }
  renderTimeline(b)
  expect(screen.getByRole('button', { name: /r2/ })).toHaveTextContent('not checked yet')
})
