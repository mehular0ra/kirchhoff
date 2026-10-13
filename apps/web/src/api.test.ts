import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('./firebase', () => ({
  ensureSignedIn: vi.fn(async () => ({
    getIdToken: vi.fn(async () => 'fake-id-token'),
  })),
  appCheckToken: vi.fn(async () => null),
}))

import { apiFetch } from './api'

describe('apiFetch', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(null)))
  })

  it('sets application/json content-type for a string body', async () => {
    await apiFetch('/api/x', { method: 'POST', body: JSON.stringify({ a: 1 }) })
    const [, init] = (fetch as any).mock.calls[0]
    const headers = init.headers as Headers
    expect(headers.get('Content-Type')).toBe('application/json')
  })

  it('does not set content-type for a FormData body', async () => {
    const fd = new FormData()
    fd.append('a', '1')
    await apiFetch('/api/x', { method: 'POST', body: fd })
    const [, init] = (fetch as any).mock.calls[0]
    const headers = init.headers as Headers
    expect(headers.has('Content-Type')).toBe(false)
  })

  it('always sets the Authorization header', async () => {
    await apiFetch('/api/x')
    const [, init] = (fetch as any).mock.calls[0]
    const headers = init.headers as Headers
    expect(headers.get('Authorization')).toBe('Bearer fake-id-token')
  })
})
