import { render, screen } from '@testing-library/react'
import { EmptyState } from './Labels'

test('M1: EmptyState always shows an icon with its text; errors use the error icon and tone', () => {
  const { container, rerender } = render(<EmptyState title="No checks yet">The Checker fills this.</EmptyState>)
  expect(container.querySelector('svg')).not.toBeNull()
  expect(container.querySelector('[data-tone="info"]')).not.toBeNull()
  rerender(<EmptyState tone="error" title="Could not load the demo world" />)
  expect(container.querySelector('[data-tone="error"] svg')).not.toBeNull()
  rerender(<EmptyState title="Loading projects…" />)
  expect(container.querySelector('[data-tone="loading"] svg')).not.toBeNull()
  expect(screen.getByRole('status')).toHaveTextContent('Loading projects…')
})
