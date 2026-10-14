import { createColumnHelper, tableFeatures, useTable } from '@tanstack/react-table'
import { cn } from 'cn'
import { motion } from 'motion/react'
import { useMemo } from 'react'
import { EmptyState, IllustrativeLabel } from '@/components/Labels'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { canvasesFor } from '@/lib/model'
import { countByStatus } from '@/lib/select'
import { STATUS_META, ruleName } from '@/lib/status'
import type { Finding } from '@/lib/types'
import { useUi } from '@/store/ui'
import { useWorkspace } from '../WorkspaceContext'
import { buildMatrix, type MatrixRow } from './matrixRows'

const features = tableFeatures({})
const helper = createColumnHelper<typeof features, MatrixRow>()

function Cell({ f }: { f: Finding }) {
  const openFinding = useUi((s) => s.openFinding)
  const m = STATUS_META[f.status]
  const Icon = m.icon
  return (
    <motion.button
      key={`${f.id}:${f.status}`}
      type="button"
      initial={{ opacity: 0, scale: 0.85 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.25 }}
      aria-label={`${f.rule_id} ${f.element_id}: ${m.label}`}
      onClick={() => openFinding(f.id)}
      className={cn('inline-flex w-full items-center justify-center gap-1 rounded px-1 py-0.5 text-[11px]', m.text, m.bg, 'hover:ring-1 hover:ring-zinc-500')}
    >
      <Icon aria-hidden className="size-3.5" />
      <span>{m.label}</span>
    </motion.button>
  )
}

export function ComplianceMatrix() {
  const view = useWorkspace()
  const focus = useUi((s) => s.focus)
  const whatIf = view.whatIf
  const model = view.model
  const findings = whatIf ? whatIf.findings : view.findings
  const { rows, rules } = useMemo(() => buildMatrix(findings), [findings])
  const rulesKey = rules.join(',')
  const columns = useMemo(
    () =>
      helper.columns([
        helper.display({
          id: 'element',
          header: 'Element',
          cell: (ctx) => (
            <button
              type="button"
              onClick={() => focus(ctx.row.original.element, canvasesFor(model, ctx.row.original.element))}
              className="font-mono text-zinc-100 hover:underline"
            >
              {ctx.row.original.element}
            </button>
          ),
        }),
        ...rules.map((rule) =>
          helper.display({
            id: rule,
            header: rule,
            cell: (ctx) => {
              const f = ctx.row.original.cells[rule]
              return f ? <Cell f={f} /> : <span aria-label="not checked" className="text-zinc-700">·</span>
            },
          }),
        ),
      ]),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [rulesKey, focus, model],
  )
  const table = useTable({ features, columns, data: rows, getRowId: (r) => r.element })

  if (!findings.length) {
    return <EmptyState title="No checks yet">The Checker fills this matrix as it runs the rule pack on a revision.</EmptyState>
  }
  const c = countByStatus(findings)
  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center gap-3 border-b px-3 py-2 text-xs">
        {whatIf && (
          <span className="rounded border border-amber-400/50 bg-amber-500/10 px-1.5 py-0.5 text-amber-200">
            What-if view (not saved)
          </span>
        )}
        <span className="font-mono text-zinc-200" aria-live="polite">
          {findings.length} checks
        </span>
        {(['fail', 'warn', 'pass'] as const).map((s) => (
          <span key={s} className={cn('inline-flex items-center gap-1 font-mono', STATUS_META[s].text)}>
            {c[s]} {STATUS_META[s].label.toLowerCase()}
          </span>
        ))}
        <IllustrativeLabel className="ml-auto" />
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        <table className="w-full border-separate border-spacing-0 text-xs" aria-label="Compliance matrix">
          <thead className="sticky top-0 z-10 bg-background">
            {table.getHeaderGroups().map((g) => (
              <tr key={g.id}>
                {g.headers.map((h) => (
                  <th key={h.id} scope="col" className="border-b px-1 py-1.5 text-left font-mono font-medium text-zinc-400">
                    {h.id === 'element' ? (
                      'Element'
                    ) : (
                      <Tooltip>
                        <TooltipTrigger className="cursor-help">{h.id}</TooltipTrigger>
                        <TooltipContent>{ruleName(h.id)}</TooltipContent>
                      </Tooltip>
                    )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row, i) => (
              <tr key={row.id} data-tour={i === 0 ? 'matrix-row' : undefined} className="hover:bg-zinc-900/60">
                {row.getAllCells().map((cell) => (
                  <td key={cell.id} className="border-b border-zinc-800/70 px-1 py-1">
                    <table.FlexRender cell={cell} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
