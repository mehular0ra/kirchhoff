import { ApiError, describeApiError, httpApiClient, type Fetcher } from './apiClient'
import { test, expect, vi } from 'vitest'

function recorder(response: Response) {
  const calls: { path: string; init?: RequestInit }[] = []
  const fetcher: Fetcher = async (path, init) => {
    calls.push({ path, init })
    return response.clone()
  }
  return { calls, fetcher }
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

test('startRun posts the interface body and returns the run id', async () => {
  const { calls, fetcher } = recorder(json({ run_id: 'r-1' }, 202))
  const api = httpApiClient(fetcher)
  await expect(api.startRun('hall-b', 'ask')).resolves.toEqual({ run_id: 'r-1' })
  expect(calls[0].path).toBe('/api/runs')
  expect(calls[0].init?.method).toBe('POST')
  expect(JSON.parse(String(calls[0].init?.body))).toEqual({ project_id: 'hall-b', autonomy: 'ask' })
})

test('gate calls hit the gate routes with snake_case bodies', async () => {
  const { calls, fetcher } = recorder(new Response(null, { status: 202 }))
  const api = httpApiClient(fetcher)
  await api.planGate('r-1', { 'Q-redundancy': '2N' }, { 'p2.place_racks': 'keep row R1 short' })
  await api.optionGate('r-1', '2N')
  await api.reviewGate('r-1', 'approved', 'ok')
  expect(calls.map((c) => c.path)).toEqual([
    '/api/runs/r-1/gates/plan',
    '/api/runs/r-1/gates/option',
    '/api/runs/r-1/gates/review',
  ])
  expect(JSON.parse(String(calls[0].init?.body))).toEqual({
    answers: { 'Q-redundancy': '2N' },
    plan_notes: { 'p2.place_racks': 'keep row R1 short' },
  })
  expect(JSON.parse(String(calls[1].init?.body))).toEqual({ option_id: '2N' })
})

test('non-2xx responses raise ApiError with the server detail', async () => {
  const { fetcher } = recorder(json({ detail: 'live-run cap reached' }, 429))
  const err = await httpApiClient(fetcher).startRun('hall-b', 'auto').catch((e: unknown) => e)
  expect(err).toBeInstanceOf(ApiError)
  expect((err as ApiError).status).toBe(429)
  expect((err as ApiError).detail).toBe('live-run cap reached')
})

test('voice sends multipart audio plus the revision ref', async () => {
  const { calls, fetcher } = recorder(json({ transcript: 't', answer: 'a', tool_results: [] }))
  await httpApiClient(fetcher).voice(new Blob(['x'], { type: 'audio/webm' }), 'ws:r2')
  const body = calls[0].init?.body as FormData
  expect(body.get('revision_ref')).toBe('ws:r2')
  expect(body.get('audio')).toBeInstanceOf(Blob)
})

test('fileBlob asks for the signed URL, then fetches it without auth headers', async () => {
  const { calls, fetcher } = recorder(json({ url: 'https://storage.example/x?sig=1', expires_in: 600 }))
  const plain = vi.fn(async () => new Response('a,b'))
  const blob = await httpApiClient(fetcher, plain).fileBlob('exports/run-r2/boq.csv')
  expect(calls[0].path).toBe('/api/files/exports/run-r2/boq.csv?redirect=0')
  expect(plain).toHaveBeenCalledWith('https://storage.example/x?sig=1')
  expect(await blob.text()).toBe('a,b')
})

test('fileBlob takes inline bytes when the API serves them (local fakes)', async () => {
  const inline = new Response('{"racks":[]}', { headers: { 'X-Kirchhoff-Inline': '1', 'Content-Type': 'application/json' } })
  const { fetcher } = recorder(inline)
  const plain = vi.fn()
  const blob = await httpApiClient(fetcher, plain).fileBlob('revisions/run-r1/model.json')
  expect(plain).not.toHaveBeenCalled()
  expect(JSON.parse(await blob.text())).toEqual({ racks: [] })
})

test('describeApiError turns WS2 detail codes into sentences', () => {
  expect(describeApiError(new ApiError(429, 'global_cap'))).toMatch(/at capacity/)
  expect(describeApiError(new ApiError(409, 'run_in_progress'))).toMatch(/still working/)
  expect(describeApiError(new ApiError(500, 'boom'))).toBe('The live backend answered 500: boom.')
  expect(describeApiError(new TypeError('Failed to fetch'))).toMatch(/unreachable/)
})
