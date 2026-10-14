import { renderHook } from '@testing-library/react'
import { fixtureBundle } from '@/test/fixtures'
import { useLeaseWatchdog } from './useLeaseWatchdog'

test('calls resume when the heartbeat is older than 60 s, at most once a minute', () => {
  vi.useFakeTimers()
  let now = 2000
  const resume = vi.fn(async () => ({ resumed: true }))
  const run = { ...fixtureBundle().runs[0], id: 'run-1', status: 'running' as const, lease: { owner: 'w', attempt: 1, heartbeat_at: 1950 } }
  renderHook(() => useLeaseWatchdog(run, resume, { intervalMs: 1000, now: () => now }))
  vi.advanceTimersByTime(1000)
  expect(resume).not.toHaveBeenCalled() // 50 s old
  now = 2015
  vi.advanceTimersByTime(1000)
  expect(resume).toHaveBeenCalledWith('run-1')
  now = 2030
  vi.advanceTimersByTime(1000)
  expect(resume).toHaveBeenCalledTimes(1)
  now = 2080
  vi.advanceTimersByTime(1000)
  expect(resume).toHaveBeenCalledTimes(2)
})
