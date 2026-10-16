import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import type { Autonomy } from '@/lib/types'

/**
 * Ask | Auto (spec §6.1). Autonomy is chosen when a run starts (POST /api/runs); during or after a
 * run the switch shows the run's autonomy read-only.
 */
// Locked is read-only, not unavailable: the run's autonomy stays legible at full contrast (no disabled fade), with
// the unchosen side muted so the chosen one reads as the state.
const LOCKED = 'disabled:opacity-100 disabled:cursor-default data-[state=off]:text-muted-foreground'

export function AutonomySwitch({
  value,
  onChange,
  locked = false,
}: {
  value: Autonomy
  onChange?: (a: Autonomy) => void
  locked?: boolean
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span data-tour="autonomy">
          <ToggleGroup
            type="single"
            size="sm"
            variant="outline"
            value={value}
            disabled={locked}
            aria-label="Autonomy"
            onValueChange={(v) => v && onChange?.(v as Autonomy)}
          >
            <ToggleGroupItem value="ask" className={locked ? LOCKED : undefined} aria-label="Ask: pause at every gate">
              Ask
            </ToggleGroupItem>
            <ToggleGroupItem value="auto" className={locked ? LOCKED : undefined} aria-label="Auto: resolve plan and option gates by the tender's rules">
              Auto
            </ToggleGroupItem>
          </ToggleGroup>
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">
        Ask pauses at the plan and option gates for you. Auto resolves them by the tender (a numbered clause beats an
        appendix) and logs why. The review gate always waits for a human.{locked ? ' Set when the run started.' : ''}
      </TooltipContent>
    </Tooltip>
  )
}
