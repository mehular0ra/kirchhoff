import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PaneSplitter } from './PaneSplitter'

function setup(props: Partial<React.ComponentProps<typeof PaneSplitter>> = {}) {
  const onChange = vi.fn()
  const onReset = vi.fn()
  render(<PaneSplitter label="Resize the agents lane" value={256} min={160} max={480} grow={1} onChange={onChange} onReset={onReset} {...props} />)
  return { onChange, onReset, bar: screen.getByRole('separator', { name: props.label ?? 'Resize the agents lane' }) }
}

test('it is a keyboard-reachable separator that says its size and limits', () => {
  const { bar } = setup()
  expect(bar).toHaveAttribute('aria-orientation', 'vertical')
  expect(bar).toHaveAttribute('aria-valuenow', '256')
  expect(bar).toHaveAttribute('aria-valuemin', '160')
  expect(bar).toHaveAttribute('aria-valuemax', '480')
  expect(bar).toHaveAttribute('tabindex', '0')
})

test('the arrow keys move it by 16 px, or 64 px with Shift, towards the side the key points to', async () => {
  const user = userEvent.setup()
  const { bar, onChange } = setup()
  bar.focus()
  await user.keyboard('{ArrowRight}')
  expect(onChange).toHaveBeenLastCalledWith(272)
  await user.keyboard('{ArrowLeft}')
  expect(onChange).toHaveBeenLastCalledWith(240)
  await user.keyboard('{Shift>}{ArrowRight}{/Shift}')
  expect(onChange).toHaveBeenLastCalledWith(320)
})

test('for a panel on the right, dragging or pressing left makes it wider', async () => {
  const user = userEvent.setup()
  const { bar, onChange } = setup({ label: 'Resize the co-pilot', value: 320, min: 260, max: 600, grow: -1 })
  bar.focus()
  await user.keyboard('{ArrowLeft}')
  expect(onChange).toHaveBeenLastCalledWith(336)
  await user.keyboard('{ArrowRight}')
  expect(onChange).toHaveBeenLastCalledWith(304)
})

test('Home and End go to the smallest and largest width, and never past them', async () => {
  const user = userEvent.setup()
  const { bar, onChange } = setup({ value: 470 })
  bar.focus()
  await user.keyboard('{End}')
  expect(onChange).toHaveBeenLastCalledWith(480)
  await user.keyboard('{Home}')
  expect(onChange).toHaveBeenLastCalledWith(160)
  await user.keyboard('{ArrowRight}')
  expect(onChange).toHaveBeenLastCalledWith(480) // 470 + 16 is held at the largest width
})

test('Enter or a double click puts it back to the usual width', async () => {
  const user = userEvent.setup()
  const { bar, onReset } = setup()
  bar.focus()
  await user.keyboard('{Enter}')
  expect(onReset).toHaveBeenCalledTimes(1)
  await user.dblClick(bar)
  expect(onReset).toHaveBeenCalledTimes(2)
})

test('dragging with the pointer follows it until it is released', () => {
  const { bar, onChange } = setup()
  fireEvent.pointerDown(bar, { pointerId: 1, clientX: 100 })
  fireEvent.pointerMove(bar, { pointerId: 1, buttons: 1, clientX: 140 })
  expect(onChange).toHaveBeenLastCalledWith(296)
  fireEvent.pointerMove(bar, { pointerId: 1, buttons: 1, clientX: 60 })
  expect(onChange).toHaveBeenLastCalledWith(216)
  fireEvent.pointerUp(bar, { pointerId: 1, clientX: 60 })
  onChange.mockClear()
  fireEvent.pointerMove(bar, { pointerId: 1, buttons: 1, clientX: 300 })
  expect(onChange).not.toHaveBeenCalled()
})

test('dragging a right-hand panel to the left makes it wider, and to the right narrower', () => {
  const { bar, onChange } = setup({ label: 'Resize the co-pilot', value: 320, min: 260, max: 600, grow: -1 })
  fireEvent.pointerDown(bar, { pointerId: 1, clientX: 500 })
  fireEvent.pointerMove(bar, { pointerId: 1, buttons: 1, clientX: 460 })
  expect(onChange).toHaveBeenLastCalledWith(360)
  fireEvent.pointerMove(bar, { pointerId: 1, buttons: 1, clientX: 530 })
  expect(onChange).toHaveBeenLastCalledWith(290)
})

test('a drag is held between the smallest and largest width', () => {
  const { bar, onChange } = setup()
  fireEvent.pointerDown(bar, { pointerId: 1, clientX: 100 })
  fireEvent.pointerMove(bar, { pointerId: 1, buttons: 1, clientX: 2000 })
  expect(onChange).toHaveBeenLastCalledWith(480)
  fireEvent.pointerMove(bar, { pointerId: 1, buttons: 1, clientX: -2000 })
  expect(onChange).toHaveBeenLastCalledWith(160)
})

test('a right-click does not start a drag, so the panel does not follow the mouse afterwards', () => {
  const { bar, onChange } = setup()
  fireEvent.pointerDown(bar, { pointerId: 1, button: 2, buttons: 2, clientX: 100 })
  fireEvent.pointerMove(bar, { pointerId: 1, buttons: 2, clientX: 130 }) // the right button is still down
  fireEvent.pointerMove(bar, { pointerId: 1, buttons: 0, clientX: 160 })
  expect(onChange).not.toHaveBeenCalled()
})

test('a drag ends when a move arrives with no button held (the release was swallowed, e.g. by a menu)', () => {
  const { bar, onChange } = setup()
  fireEvent.pointerDown(bar, { pointerId: 1, button: 0, buttons: 1, clientX: 100 })
  fireEvent.pointerMove(bar, { pointerId: 1, buttons: 1, clientX: 120 })
  expect(onChange).toHaveBeenCalledTimes(1)
  fireEvent.pointerMove(bar, { pointerId: 1, buttons: 0, clientX: 200 })
  expect(onChange).toHaveBeenCalledTimes(1)
})

test('losing the pointer capture ends the drag', () => {
  const { bar, onChange } = setup()
  fireEvent.pointerDown(bar, { pointerId: 1, button: 0, buttons: 1, clientX: 100 })
  fireEvent.lostPointerCapture(bar, { pointerId: 1 })
  fireEvent.pointerMove(bar, { pointerId: 1, buttons: 1, clientX: 140 })
  expect(onChange).not.toHaveBeenCalled()
})

test('moving over it without pressing does nothing', () => {
  const { bar, onChange } = setup()
  fireEvent.pointerMove(bar, { pointerId: 1, buttons: 1, clientX: 140 })
  expect(onChange).not.toHaveBeenCalled()
})
