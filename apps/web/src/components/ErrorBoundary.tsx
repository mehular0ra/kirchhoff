import { Component, type ErrorInfo, type ReactNode } from 'react'
import { EmptyState } from './Labels'
import { Button } from './ui/button'

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
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <EmptyState
        title="This view hit an error"
        action={
          <Button size="sm" variant="outline" onClick={() => window.location.reload()}>
            Reload this view
          </Button>
        }
      >
        The rest of the demo still works. Try the projects page or reload.
      </EmptyState>
    )
  }
}
