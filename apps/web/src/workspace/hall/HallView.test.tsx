import { fireEvent, render, screen } from '@testing-library/react'
import { fixtureBundle } from '@/test/fixtures'
import { useUi } from '@/store/ui'
import { WorkspaceProvider } from '../WorkspaceContext'
import { activateElements, HallIssueOverlay } from './HallView'

// Revision r1 of the fixture bundle (hall-mini.json) has 3 non-pass elements: R05:FA-01 (fail),
// R11:H-Z2 (fail) and R10:BR-R1 (warn). r2 (the latest, shown by default) fixes the two fails.

test('the keyboard overlay lists one button per non-pass element and stays collapsed by default', () => {
  useUi.getState().resetWorkspaceUi()
  useUi.getState().setViewRev('r1')
  render(
    <WorkspaceProvider bundle={fixtureBundle()} source="static">
      <HallIssueOverlay />
    </WorkspaceProvider>,
  )
  expect(screen.getByRole('button', { name: /3 issues/i })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /FA-01/ })).not.toBeInTheDocument()
})

test('activating the overlay button for a failing element opens its finding, same as clicking its mesh', () => {
  useUi.getState().resetWorkspaceUi()
  useUi.getState().setViewRev('r1')
  render(
    <WorkspaceProvider bundle={fixtureBundle()} source="static">
      <HallIssueOverlay />
    </WorkspaceProvider>,
  )
  fireEvent.click(screen.getByRole('button', { name: /3 issues/i }))
  const button = screen.getByRole('button', { name: /FA-01/ })
  fireEvent.click(button)
  expect(useUi.getState().findingId).toBe('R05:FA-01')
})

test('activateElements (the shared activation logic) falls back to focus when the element has no non-pass finding', () => {
  useUi.getState().resetWorkspaceUi()
  const openFinding = vi.fn()
  activateElements(['A1'], fixtureBundle().findings.r1, { openFinding, focus: (id) => useUi.getState().focus(id) })
  expect(openFinding).not.toHaveBeenCalled()
  expect(useUi.getState().focusId).toBe('A1')
})
