import { RotateCcw } from 'lucide-react'
import { Link } from 'react-router'
import { Button } from '@/components/ui/button'
import { classifyLoadError } from '@/lib/loadError'
import { EmptyState } from './Labels'

/**
 * A load failure in words with a way out (UX-1 D11): "Project not found" for a missing file (a mistyped or old
 * link), else "Couldn't load …" with Try again. The raw error ("Failed to fetch", a JSON parse error) never shows.
 */
export function LoadError({
  error,
  what = 'this page',
  notFoundTitle = 'Project not found',
  back = true,
}: {
  error: string | null | undefined
  /** "this page", "the projects", "the bids inbox", … */
  what?: string
  notFoundTitle?: string
  /** Offer "Back to projects" (not on the projects page itself). */
  back?: boolean
}) {
  const kind = classifyLoadError(error)
  const backLink = back && (
    <Button asChild size="sm" variant={kind === 'not_found' ? 'default' : 'outline'}>
      <Link to="/app">Back to projects</Link>
    </Button>
  )
  if (kind === 'not_found')
    return (
      <EmptyState tone="error" title={notFoundTitle} action={backLink}>
        This link may be mistyped or out of date.
      </EmptyState>
    )
  return (
    <EmptyState
      tone="error"
      title={`Couldn't load ${what}`}
      action={
        <div className="flex flex-wrap justify-center gap-2">
          <Button size="sm" onClick={() => window.location.reload()}>
            <RotateCcw aria-hidden /> Try again
          </Button>
          {backLink}
        </div>
      }
    >
      {kind === 'message' ? error : 'Check your connection and try again.'}
    </EmptyState>
  )
}
