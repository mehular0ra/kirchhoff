import type { ReactNode } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { CANVAS_TABS, useUi, type CanvasTab } from '@/store/ui'

export function CanvasTabs({ panes }: { panes: Record<CanvasTab, ReactNode> }) {
  const tab = useUi((s) => s.tab)
  const setTab = useUi((s) => s.setTab)
  return (
    <Tabs value={tab} onValueChange={(v) => setTab(v as CanvasTab)} className="flex h-full min-h-0 flex-col gap-0">
      <TabsList className="m-2 self-start">
        {CANVAS_TABS.map((t) => (
          <TabsTrigger key={t.id} value={t.id} data-tour={`tab-${t.id}`}>
            {t.label}
          </TabsTrigger>
        ))}
      </TabsList>
      {CANVAS_TABS.map((t) => (
        <TabsContent key={t.id} value={t.id} className="relative min-h-0 flex-1 overflow-hidden">
          {panes[t.id]}
        </TabsContent>
      ))}
    </Tabs>
  )
}
