import { useState, type ReactElement } from 'react'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { readJson, writeJson } from '@/lib/storage'

/** One-line first-hover tip (spec §13.5 contextual hints); never shown again once dismissed. */
export function Hint({ id, text, children }: { id: string; text: string; children: ReactElement }) {
  const key = `hints.${id}`
  const [seen, setSeen] = useState(() => readJson<boolean>(key, false))
  const [open, setOpen] = useState(false)
  if (seen) return children
  return (
    <Tooltip
      open={open}
      onOpenChange={(o) => {
        if (!o && open) {
          writeJson(key, true)
          setSeen(true)
        }
        setOpen(o)
      }}
    >
      <TooltipTrigger asChild>{children}</TooltipTrigger>
      <TooltipContent data-dev className="max-w-xs">
        {text}
      </TooltipContent>
    </Tooltip>
  )
}
