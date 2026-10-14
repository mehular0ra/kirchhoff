import { render, screen } from '@testing-library/react'
import { StatusBadge } from './StatusBadge'

test.each([
  ['pass', 'Pass'],
  ['fail', 'Fail'],
  ['warn', 'Warn'],
  ['n/a', 'N/A'],
] as const)('status %s is shown as icon plus the text "%s", never colour alone', (status, label) => {
  const { container } = render(<StatusBadge status={status} />)
  expect(screen.getByText(label)).toBeInTheDocument()
  expect(container.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
})
