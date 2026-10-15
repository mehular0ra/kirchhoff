import type { ReactNode } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { CANVAS_TABS, useUi, type CanvasTab } from '@/store/ui'

/** Canvas tabs; `aside` (the revision story strip, I1) sits beside the tab list and wraps under it when narrow. */
export function CanvasTabs({ panes, aside }: { panes: Record<CanvasTab, ReactNode>; aside?: ReactNode }) {
  const tab = useUi((s) => s.tab)
  const setTab = useUi((s) => s.setTab)
  return (
    <Tabs value={tab} onValueChange={(v) => setTab(v as CanvasTab)} className="flex h-full min-h-0 flex-col gap-0">
      <div className="flex flex-wrap items-center gap-x-4 px-2">
        <TabsList className="my-2 self-start">
          {CANVAS_TABS.map((t) => (
            <TabsTrigger key={t.id} value={t.id} data-tour={`tab-${t.id}`}>
              {t.label}
            </TabsTrigger>
          ))}
        </TabsList>
        {aside && <div className="min-w-0 py-1">{aside}</div>}
      </div>
      {CANVAS_TABS.map((t) => (
        <TabsContent key={t.id} value={t.id} className="relative min-h-0 flex-1 overflow-hidden">
          {panes[t.id]}
        </TabsContent>
      ))}
    </Tabs>
  )
}
