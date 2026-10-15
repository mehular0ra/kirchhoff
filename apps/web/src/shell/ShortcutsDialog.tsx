import { CircleX } from 'lucide-react'
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

/** A reset that could not fully complete: kept (409, nothing cleared) or failed after clearing local progress. */
interface ResetFailure {
  kept: boolean
  message: string
}

export function ShortcutsDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const { api } = useServices()
  const start = useTour((s) => s.start)
  const [confirm, setConfirm] = useState(false)
  const [resetFailure, setResetFailure] = useState<ResetFailure | null>(null)

  const reset = async () => {
    // Deletes the visitor's Firestore overlay (live runs, approvals, PRs, CRM stage) and local progress.
    try {
      await api.resetWorkspace()
    } catch (e) {
      // WS2 refuses while a run holds a live lease (409 run_in_progress): keep everything and say so.
      if (e instanceof ApiError && e.status === 409) {
        setResetFailure({ kept: true, message: describeApiError(e) })
        return
      }
      // Backend unreachable or a server error: still clear local progress, but never navigate away
      // silently — the server-side overlay (live runs, approvals, PRs, CRM stage) was NOT cleared,
      // so the visitor needs to see that and retry later.
      clearKirchhoffStorage()
      setResetFailure({
        kept: false,
        message: 'Your local progress was cleared, but the server-side reset failed. You can retry it later; some data may still be in your workspace.',
      })
      return
    }
    clearKirchhoffStorage()
    window.location.assign('/app')
  }

  const dismissFailure = () => {
    const failed = resetFailure
    setResetFailure(null)
    if (failed && !failed.kept) window.location.assign('/app')
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
                <kbd className="rounded border border-zinc-300 bg-zinc-100 px-1.5 font-mono text-xs">{k}</kbd>
              </dt>
              <dd className="text-zinc-700">{v}</dd>
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
        {resetFailure && (
          <p role="alert" className="flex items-center gap-1.5 text-xs text-amber-700">
            <CircleX aria-hidden className="size-3.5 shrink-0" />
            <span>{resetFailure.message}</span>
            <Button size="xs" variant="ghost" className="ml-auto" onClick={dismissFailure}>
              Dismiss
            </Button>
          </p>
        )}
      </DialogContent>
    </Dialog>
  )
}
