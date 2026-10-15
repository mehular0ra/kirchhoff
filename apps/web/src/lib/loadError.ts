// Classifies a static-data load failure for a friendly message (UX-1 D11). Firebase Hosting answers a
// missing JSON file with index.html, so a JSON parse error means "not found", like a 404.
// A raw transport error ("Failed to fetch", "…json: 503") reads as "check your connection"; a sentence written
// by our own code ("Live data is unavailable in this environment") is shown as it is.
export type LoadErrorKind = 'not_found' | 'network' | 'message'

export function classifyLoadError(message: string | null | undefined): LoadErrorKind {
  if (message && /\b404\b|Unexpected token|not valid JSON|JSON\.parse|Unexpected end of JSON/i.test(message)) return 'not_found'
  if (!message || /Failed to fetch|NetworkError|Load failed|network|timed? ?out|: \d{3}$/i.test(message)) return 'network'
  return 'message'
}
