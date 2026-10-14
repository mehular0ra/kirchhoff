import { readJson, writeJson } from './storage'

/**
 * Presentation mode (`?present=1`, persists for the browser session; `?present=0` turns it off):
 * hides dev affordances ([data-dev]) and enlarges type for screen recording.
 */
export function initPresentationMode(search: string = window.location.search): boolean {
  const q = new URLSearchParams(search).get('present')
  if (q === '1') writeJson('present', true, sessionStorage)
  if (q === '0') writeJson('present', false, sessionStorage)
  const on = readJson<boolean>('present', false, sessionStorage)
  document.documentElement.dataset.present = on ? '1' : '0'
  return on
}

export function isPresentationMode(): boolean {
  return document.documentElement.dataset.present === '1'
}

/** Optional film shot (`?shot=cold-open`) used by the 3D view for the video's first beat. */
export function currentShot(search: string = window.location.search): string | null {
  return new URLSearchParams(search).get('shot')
}
