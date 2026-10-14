import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { clearKirchhoffStorage } from '@/lib/storage'
import { useTour } from '@/onboarding/tour/tour'
import { ApiError, describeApiError } from '@/services/apiClient'
import { useServices } from '@/services/services'

const KEYS: [string, string][] = [
  ['?', 'Shortcuts, tour and reset'],
  ['g then p', 'Projects'],
  ['g then i', 'Integrations'],
  ['← →', 'Previous / next tour step'],
  ['Esc', 'Close a drawer, dialog or the tour'],
]

export function ShortcutsDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const { api } = useServices()
  const start = useTour((s) => s.start)
  const [confirm, setConfirm] = useState(false)
  const [resetError, setResetError] = useState<string | null>(null)

  const reset = async () => {
    // Deletes the visitor's Firestore overlay (live runs, approvals, PRs, CRM stage) and local progress.
    try {
      await api.resetWorkspace()
    } catch (e) {
      // WS2 refuses while a run holds a live lease (409 run_in_progress): keep everything and say so.
      if (e instanceof ApiError && e.status === 409) {
        setResetError(describeApiError(e))
        return
      }
      // Backend unreachable: still clear local progress (the Firestore overlay stays until the next reset).
    }
    clearKirchhoffStorage()
    window.location.assign('/app')
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setConfirm(false)
        onOpenChange(o)
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Help and shortcuts</DialogTitle>
          <DialogDescription>Keyboard works everywhere except while typing.</DialogDescription>
        </DialogHeader>
        <dl className="grid grid-cols-[6rem_1fr] gap-y-1 text-sm">
          {KEYS.map(([k, v]) => (
            <div key={k} className="contents">
              <dt>
                <kbd className="rounded border border-zinc-600 bg-zinc-800 px-1.5 font-mono text-xs">{k}</kbd>
              </dt>
              <dd className="text-zinc-300">{v}</dd>
            </div>
          ))}
        </dl>
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            onClick={() => {
              onOpenChange(false)
              start()
            }}
          >
            Restart the tour
          </Button>
          {confirm ? (
            <Button size="sm" variant="destructive" onClick={() => void reset()}>
              Confirm: reset my demo workspace
            </Button>
          ) : (
            <Button size="sm" variant="outline" onClick={() => setConfirm(true)}>
              Reset demo workspace
            </Button>
          )}
        </div>
        {resetError && (
          <p role="alert" className="text-xs text-amber-200">
            {resetError}
          </p>
        )}
      </DialogContent>
    </Dialog>
  )
}
