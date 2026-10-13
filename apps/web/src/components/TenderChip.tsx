import { FileText } from 'lucide-react'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import type { Citation } from '@/lib/types'
import { useUi } from '@/store/ui'

/** NotebookLM-style citation: hover previews the verified quote, click opens the PDF at the clause. */
export function TenderChip({ citation, onOpen }: { citation: Citation; onOpen?: () => void }) {
  const openCitation = useUi((s) => s.openCitation)
  const label = `${citation.clause ?? 'Tender'} · p.${citation.page}`
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          data-tour="tender-chip"
          aria-label={`Open tender ${label}`}
          onClick={() => {
            openCitation(citation)
            onOpen?.()
          }}
          className="inline-flex items-center gap-1 rounded border border-sky-500/40 bg-sky-500/10 px-1.5 py-0.5 font-mono text-[11px] text-sky-200 hover:bg-sky-500/20"
        >
          <FileText aria-hidden className="size-3" />
          {label}
        </button>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">"{citation.quote}"</TooltipContent>
    </Tooltip>
  )
}

export function ClauseChip({ standard, clause }: { standard: string; clause?: string | null }) {
  return (
    <span className="inline-flex items-center rounded border border-zinc-700 bg-zinc-800/60 px-1.5 py-0.5 font-mono text-[11px] text-zinc-300">
      {standard}
      {clause ? ` ${clause}` : ''}
    </span>
  )
}
