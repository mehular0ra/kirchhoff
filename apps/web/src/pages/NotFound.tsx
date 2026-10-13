import { Link } from 'react-router'
import { EmptyState } from '@/components/Labels'
import { Button } from '@/components/ui/button'

export function NotFound() {
  return (
    <div className="grid min-h-dvh place-items-center">
      <EmptyState
        title="This page does not exist"
        action={
          <Button asChild variant="outline" size="sm">
            <Link to="/app">Back to projects</Link>
          </Button>
        }
      >
        The demo workspace has projects, integrations and a guided tour.
      </EmptyState>
    </div>
  )
}
