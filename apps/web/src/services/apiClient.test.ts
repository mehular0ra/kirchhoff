import { ApiError, describeApiError, httpApiClient, withTimeout, type Fetcher } from './apiClient'
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

test('voice has its own 25 s client timeout, above the 12 s /api default (issue #36)', async () => {
  vi.useFakeTimers()
  const hanging: Fetcher = () => new Promise<Response>(() => {})
  const api = httpApiClient(hanging)
  const voice = api.voice(new Blob(['x'], { type: 'audio/webm' }), 'ws:r2').catch((e: unknown) => e)
  const other = api.erpPrs().catch((e: unknown) => e)
  let settled = false
  void voice.then(() => (settled = true))
  await vi.advanceTimersByTimeAsync(12_000)
  expect(await other).toMatchObject({ detail: 'client_timeout' }) // every other call keeps the 12 s bound
  await vi.advanceTimersByTimeAsync(24_999 - 12_000)
  expect(settled).toBe(false) // the server's 20 s voice budget answers well before this
  await vi.advanceTimersByTimeAsync(1)
  expect(await voice).toMatchObject({ detail: 'client_timeout' })
  vi.useRealTimers()
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

test('inbox calls hit the inbox routes; inbox error codes read as sentences', async () => {
  const { calls, fetcher } = recorder(json({ email_id: 'em-hall-b' }))
  const api = httpApiClient(fetcher)
  await api.inbox()
  await api.triage('em-hall-b')
  await api.pursue('em-hall-b')
  expect(calls.map((c) => [c.path, c.init?.method ?? 'GET'])).toEqual([
    ['/api/inbox', 'GET'],
    ['/api/inbox/em-hall-b/triage', 'POST'],
    ['/api/inbox/em-hall-b/pursue', 'POST'],
  ])
  expect(describeApiError(new ApiError(409, 'precomputed'))).toBe(
    'Only the Hall B email can be triaged live; this one shows the recorded triage.',
  )
})

test('I4: a call whose sign-in/App Check never settles is rejected after 12 s (the whole call, not just fetch)', async () => {
  vi.useFakeTimers()
  const hanging: Fetcher = () => new Promise<Response>(() => {}) // e.g. Auth waiting forever on reCAPTCHA
  const api = httpApiClient(hanging)
  const call = api.erpPrs().catch((e: unknown) => e)
  const blob = api.fileBlob('exports/r2/boq.csv').catch((e: unknown) => e)
  await vi.advanceTimersByTimeAsync(11_999)
  let settled = false
  void call.then(() => (settled = true))
  await Promise.resolve()
  expect(settled).toBe(false)
  await vi.advanceTimersByTimeAsync(1)
  const err = await call
  expect(err).toBeInstanceOf(ApiError)
  expect((err as ApiError).detail).toBe('client_timeout')
  expect(describeApiError(err)).toMatch(/did not answer in time/)
  expect(await blob).toMatchObject({ detail: 'client_timeout' })
})

test('I4: withTimeout rejects a promise that never settles, and passes through one that does', async () => {
  vi.useFakeTimers()
  const never = withTimeout(new Promise(() => {}), 5_000, () => new Error('sign-in timed out')).catch((e: Error) => e.message)
  await vi.advanceTimersByTimeAsync(5_000)
  expect(await never).toBe('sign-in timed out')
  await expect(withTimeout(Promise.resolve(7), 5_000, () => new Error('x'))).resolves.toBe(7)
})

test('DETAIL_TEXT covers run_not_found, the two 401s, enterprise_unavailable and invalid_value with plain sentences', () => {
  for (const [status, code] of [
    [404, 'run_not_found'],
    [401, 'missing bearer token'],
    [401, 'invalid app check token'],
    [502, 'enterprise_unavailable'],
    [422, 'invalid_value'],
  ] as const) {
    const text = describeApiError(new ApiError(status, code))
    expect(text).not.toMatch(/answered/)
    expect(text).not.toMatch(/\d/)
    expect(text.endsWith('.')).toBe(true)
  }
  expect(describeApiError(new ApiError(404, 'run_not_found'))).toMatch(/run/i)
  expect(describeApiError(new ApiError(422, 'invalid_value'))).toMatch(/range/)
})
