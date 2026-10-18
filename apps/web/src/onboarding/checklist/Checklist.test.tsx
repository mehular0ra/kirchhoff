import { act, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { Checklist } from './Checklist'
import { CHECKLIST, completeItem, useChecklist } from './checklistStore'

beforeEach(() => {
  localStorage.clear()
  useChecklist.getState().reload()
})

const card = () =>
  render(
    <MemoryRouter>
      <Checklist docked />
    </MemoryRouter>,
  )

test('every task says in one line how to do it', () => {
  card()
  const list = within(screen.getByRole('complementary', { name: 'Getting started' }))
  for (const c of CHECKLIST) {
    expect(c.how.length).toBeGreaterThan(10)
    expect(list.getByText(c.how)).toBeInTheDocument()
  }
})

test('the tasks that happen on another page link to it', () => {
  card()
  const list = within(screen.getByRole('complementary', { name: 'Getting started' }))
  expect(list.getByRole('link', { name: 'Open Hall A' })).toHaveAttribute('href', '/app/p/hall-a')
  expect(list.getByRole('link', { name: 'Open Hall B' })).toHaveAttribute('href', '/app/p/hall-b')
})

test('a task that is done is ticked and drops its instructions and its link', () => {
  card()
  act(() => completeItem('run_whatif'))
  const list = within(screen.getByRole('complementary', { name: 'Getting started' }))
  const done = CHECKLIST.find((c) => c.id === 'run_whatif')!
  expect(list.queryByText(done.how)).not.toBeInTheDocument()
  expect(list.getByText(done.label)).toBeInTheDocument()
  expect(list.getByLabelText('done')).toBeInTheDocument()
  act(() => completeItem('run_live'))
  expect(list.queryByRole('link', { name: 'Open Hall B' })).not.toBeInTheDocument()
})

test('the tasks tick themselves; nothing on the card is a checkbox to press', () => {
  card()
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
  expect(screen.getByText(/ticks itself when you do it/i)).toBeInTheDocument()
})
