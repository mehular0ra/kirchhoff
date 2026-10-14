import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { readJson, writeJson } from '@/lib/storage'
import { useState } from 'react'

export function hasBeenWelcomed(): boolean {
  return readJson<boolean>('welcomed', false)
}

/** First-visit welcome (spec §13.5): one sentence, "Take the 2-minute tour" (primary) or "Explore on my own". */
export function Welcome({ onStartTour }: { onStartTour: () => void }) {
  const [open, setOpen] = useState(() => !hasBeenWelcomed())
  const close = () => {
    writeJson('welcomed', true)
    setOpen(false)
  }
  return (
    <Dialog open={open} onOpenChange={(o) => !o && close()}>
      <DialogContent showCloseButton={false} className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Welcome to Meridian Power Engineering's Kirchhoff workspace</DialogTitle>
          <DialogDescription>
            Kirchhoff's agents design power and cooling for AI data halls; a deterministic checker proves every number,
            and an engineer reviews and signs.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="gap-2 sm:justify-start">
          <Button
            onClick={() => {
              close()
              onStartTour()
            }}
          >
            Take the 2-minute tour
          </Button>
          <Button variant="ghost" onClick={close}>
            Explore on my own
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
