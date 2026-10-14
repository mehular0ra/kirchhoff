// Static-first browsing (spec §11): seed projects, golden runs and the integrations snapshot load
// from Hosting and never depend on Cloud Run, Gemini, Firestore or App Check.
import { normalizeBundle, type Bundle, type IntegrationsSnapshot, type ProjectBundle, type World } from '@/lib/types'

export type JsonFetch = (url: string) => Promise<unknown>

export const fetchJson: JsonFetch = async (url) => {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`${url}: ${r.status}`)
  return r.json()
}

export async function loadWorld(get: JsonFetch = fetchJson): Promise<World> {
  return (await get('/demo/world.json')) as World
}

export async function staticBundle(pid: string, get: JsonFetch = fetchJson): Promise<Bundle> {
  return normalizeBundle((await get(`/demo/projects/${encodeURIComponent(pid)}.json`)) as ProjectBundle)
}

export async function loadIntegrationsSnapshot(get: JsonFetch = fetchJson): Promise<IntegrationsSnapshot> {
  return (await get('/demo/integrations.json')) as IntegrationsSnapshot
}

/** Tender/drawing PDFs are served from Hosting so citations work with the backend down. */
export function docUrl(docId: string): string {
  return `/demo/docs/${encodeURIComponent(docId)}.pdf`
}
