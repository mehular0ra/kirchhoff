import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { ServicesProvider, type Services } from '@/services/services'
import { useBundleStore } from '@/store/bundles'
import { fakeServices, resetStores } from '@/test/render'
import { useProjectData, type ProjectDataOptions } from './useProjectData'

function hook(services: Services, pid: string, opts: ProjectDataOptions = {}) {
  resetStores()
  const wrapper = ({ children }: { children: ReactNode }) => <ServicesProvider services={services}>{children}</ServicesProvider>
  return renderHook(() => useProjectData(pid, opts), { wrapper })
}

test('static: puts /demo/projects/{pid}.json in the store once', async () => {
  const services = fakeServices()
  const { result, rerender } = hook(services, 'hall-a')
  expect(result.current.status).toBe('loading')
  await waitFor(() => expect(result.current.status).toBe('ready'))
  expect(result.current.source).toBe('static')
  expect(result.current.bundle?.project.id).toBe('hall-a')
  expect(useBundleStore.getState().entries['hall-a:static'].status).toBe('ready')
  rerender()
  expect(services.getJson).toHaveBeenCalledTimes(1)
})

test('static: a missing bundle surfaces an error', async () => {
  const { result } = hook(fakeServices(), 'nope')
  await waitFor(() => expect(result.current.status).toBe('error'))
  expect(result.current.error).toContain('404')
})

test('replay: starts at frame 0 and exposes controls', async () => {
  const { result } = hook(fakeServices(), 'hall-a', { replay: true, speed: 1000 })
  await waitFor(() => expect(result.current.controls).not.toBeNull())
  expect(result.current.source).toBe('replay')
  act(() => result.current.controls!.pause())
  act(() => result.current.controls!.seek(0))
  expect(result.current.bundle?.events).toEqual([])
  expect(result.current.replay?.total).toBe(25)
  act(() => result.current.controls!.seek(25))
  expect(result.current.bundle?.revisions).toHaveLength(2)
})

test('live: without a Firestore source the view reports an error instead of hanging', async () => {
  const { result } = hook(fakeServices({ live: null }), 'hall-b', { runId: 'run-1' })
  await waitFor(() => expect(result.current.status).toBe('error'))
  expect(result.current.source).toBe('live')
})
