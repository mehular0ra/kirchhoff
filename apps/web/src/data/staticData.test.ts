import { test, expect } from 'vitest'
import { fakeServices } from '@/test/render'
import { docUrl, loadIntegrationsSnapshot, loadWorld, staticBundle } from './staticData'

test('static adapter normalises /demo/projects/{pid}.json into a Bundle', async () => {
  const s = fakeServices()
  const b = await staticBundle('hall-a', s.getJson)
  expect(s.getJson).toHaveBeenCalledWith('/demo/projects/hall-a.json')
  expect(b.revisions.map((r) => r.id)).toEqual(['r1', 'r2'])
  expect(b.events[0].seq).toBe(1)
})

test('world, integrations snapshot and tender PDFs load from Hosting paths', async () => {
  const s = fakeServices()
  expect((await loadWorld(s.getJson)).projects).toHaveLength(5)
  expect((await loadIntegrationsSnapshot(s.getJson)).erp.materials[0].id).toBe('TX-2500')
  expect(docUrl('tender-hall-a')).toBe('/demo/docs/tender-hall-a.pdf')
  await expect(staticBundle('nope', s.getJson)).rejects.toThrow('404')
})
