import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { HelloRun } from './HelloRun'
import type { RunEvent } from '../contracts/generated'

const ev = (seq: number, title: string): RunEvent => ({
  seq, phase: 'p1', step: 'p1.hello', attempt: 1, agent: 'system', kind: 'status', title, detail: '', payload: {}, ts: seq,
})

test('starts a run and renders streamed events in seq order', async () => {
  let push: (e: RunEvent[]) => void = () => {}
  render(<HelloRun start={async () => 'run1'} subscribe={(_id, cb) => { push = cb; return () => {} }} />)
  fireEvent.click(screen.getByRole('button', { name: /start run/i }))
  await waitFor(() => expect(screen.getByText(/run1/)).toBeInTheDocument())
  push([ev(2, 'Layout placing racks'), ev(1, 'Intake reading tender')])
  await waitFor(() => {
    const items = screen.getAllByRole('listitem').map((li) => li.textContent)
    expect(items[0]).toContain('Intake reading tender')
    expect(items[1]).toContain('Layout placing racks')
  })
})
