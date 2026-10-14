import { Component, type ErrorInfo, type ReactNode } from 'react'
import { EmptyState } from './Labels'
import { Button } from './ui/button'

const CHUNK_ERROR = /Failed to fetch dynamically imported module|Importing a module script failed|error loading dynamically imported module|Loading chunk/i
const RELOADED_KEY = 'kirchhoff.chunkReload'

/** A lazy chunk that 404s after a redeploy (an old tab asks for the previous build's file). */
function isChunkLoadError(e: unknown): boolean {
  return e instanceof Error && CHUNK_ERROR.test(e.message)
}

/** Keeps one broken view from blanking the demo; resets when `resetKey` (the route) changes. */
export class ErrorBoundary extends Component<{ resetKey: string; children: ReactNode }, { error: Error | null; key: string }> {
  state = { error: null as Error | null, key: this.props.resetKey }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  static getDerivedStateFromProps(props: { resetKey: string }, state: { error: Error | null; key: string }) {
    return props.resetKey !== state.key ? { error: null, key: props.resetKey } : null
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[kirchhoff] view crashed', error, info.componentStack)
    // After a redeploy, reload once to pick up the new build (M14); never loop.
    if (!isChunkLoadError(error)) return
    try {
      if (sessionStorage.getItem(RELOADED_KEY)) return
      sessionStorage.setItem(RELOADED_KEY, '1')
    } catch {
      return
    }
    window.location.reload()
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <EmptyState
        tone="error"
        title="This view hit an error"
        action={
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={() => window.location.reload()}>
              Reload this view
            </Button>
            <Button size="sm" variant="ghost" asChild>
              <a href="/app">Back to projects</a>
            </Button>
          </div>
        }
      >
        The rest of the demo still works: go back to the projects page, or reload.
      </EmptyState>
    )
  }
}
