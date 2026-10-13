import { ensureSignedIn, appCheckToken } from './firebase'

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const user = await ensureSignedIn()
  const headers = new Headers(init.headers)
  headers.set('Authorization', `Bearer ${await user.getIdToken()}`)
  const ac = await appCheckToken()
  if (ac) headers.set('X-Firebase-AppCheck', ac)
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  return fetch(path, { ...init, headers })
}
