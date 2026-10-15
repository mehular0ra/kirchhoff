import { render, screen } from '@testing-library/react'
import { Legend } from './Legend'

test('I1: the legend lists only the statuses present in the view', () => {
  const { rerender } = render(<Legend statuses={new Set(['pass'])} diff={false} resolved={false} whatIf={false} />)
  expect(screen.getByText('Pass')).toBeInTheDocument()
  expect(screen.queryByText('Fail')).not.toBeInTheDocument()
  expect(screen.queryByText('Warn')).not.toBeInTheDocument()
  rerender(<Legend statuses={new Set(['pass', 'fail'])} diff resolved whatIf={false} />)
  expect(screen.getByText('Fail')).toBeInTheDocument()
  expect(screen.getByText('changed')).toBeInTheDocument()
  expect(screen.getByText('✓ resolved')).toBeInTheDocument()
  expect(screen.getByText('IEC-based, illustrative values, not for construction')).toBeInTheDocument()
})

test('D6: what-if impact keys are line swatches labelled by discipline', () => {
  render(<Legend statuses={new Set(['fail'])} diff={false} resolved={false} whatIf />)
  expect(screen.getByText('electrical impact')).toBeInTheDocument()
  expect(screen.getByText('cooling impact')).toBeInTheDocument()
})
