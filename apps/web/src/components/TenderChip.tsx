import { FileText } from 'lucide-react'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import type { Citation } from '@/lib/types'
import { completeItem } from '@/onboarding/checklist/checklistStore'
import { useUi } from '@/store/ui'

/** NotebookLM-style citation: hover previews the verified quote, click opens the PDF at the clause. */
export function TenderChip({ citation, onOpen, verified = true }: { citation: Citation; onOpen?: () => void; verified?: boolean }) {
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
            completeItem('inspect_source')
            onOpen?.()
          }}
          className="inline-flex items-center gap-1 rounded border border-blue-500/40 bg-blue-500/10 px-1.5 py-0.5 font-mono text-[11px] text-blue-700 hover:bg-blue-500/20"
        >
          <FileText aria-hidden className="size-3" />
          {label}
        </button>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">
        {verified && citation.quote ? `“${citation.quote}”` : 'Quote not found on the cited page'}
      </TooltipContent>
    </Tooltip>
  )
}

export function ClauseChip({ standard, clause }: { standard: string; clause?: string | null }) {
  return (
    <span className="inline-flex items-center rounded border border-zinc-300 bg-zinc-100 px-1.5 py-0.5 font-mono text-[11px] text-zinc-700">
      {standard}
      {clause ? ` ${clause}` : ''}
    </span>
  )
}
