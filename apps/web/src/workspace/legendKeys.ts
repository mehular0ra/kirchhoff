import type { FindingStatus } from '@/lib/types'
import type { WorkspaceView } from './WorkspaceContext'

/** The legend keys present in a view (UX-1 I1): statuses on screen, plus the diff and what-if keys in use. */
export function legendKeys(v: WorkspaceView): { statuses: Set<FindingStatus>; diff: boolean; resolved: boolean; whatIf: boolean } {
  const whatIf = v.highlights.size > 0 || !!v.whatIf
  return {
    statuses: new Set<FindingStatus>([...v.status.values(), ...(whatIf ? v.whatIfStatus.values() : [])]),
    diff: !!v.diff && v.diff.changes.length > 0 && !whatIf, // N7: the "changed" key is stale compare styling during a what-if
    resolved: !!v.diff && v.resolved.size > 0 && !whatIf, // what-if callouts replace the resolved ones
    whatIf,
  }
}
