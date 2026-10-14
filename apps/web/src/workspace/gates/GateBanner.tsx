import { useEffect } from 'react'
import { useUi } from '@/store/ui'
import { useWorkspace } from '../WorkspaceContext'
import { PlanGate } from './PlanGate'

/** Shows the interactive plan gate above the canvas and jumps to Options at the option gate. */
export function GateBanner() {
  const { run, source } = useWorkspace()
  const setTab = useUi((s) => s.setTab)
  const gate = source === 'live' && run?.status === 'at_gate' ? run.gate : null
  useEffect(() => {
    if (gate === 'option') setTab('options')
  }, [gate, setTab])
  if (gate !== 'plan' || !run) return null
  return (
    <div className="max-h-[55%] overflow-auto border-b p-3">
      <PlanGate run={run} interactive />
    </div>
  )
}
