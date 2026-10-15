import { createColumnHelper, tableFeatures, useTable } from '@tanstack/react-table'
import { cn } from 'cn'
import { createContext, useContext, useMemo, useState, type KeyboardEvent } from 'react'
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

/**
 * Roving tabindex (backlog [3]): the whole matrix is one tab stop. The active cell has tabIndex 0,
 * every other control -1; arrow keys, Home/End and Page Up/Down move between cells.
 */
interface Nav {
  active: string // "row:col"
  setActive(key: string): void
}
const NavCtx = createContext<Nav>({ active: '0:0', setActive: () => {} })
const cellKey = (r: number, c: number) => `${r}:${c}`

function Cell({ f, r, c }: { f: Finding; r: number; c: number }) {
  const openFinding = useUi((s) => s.openFinding)
  const nav = useContext(NavCtx)
  const m = STATUS_META[f.status]
  const Icon = m.icon
  const key = cellKey(r, c)
  return (
    // A plain button with a CSS entrance (tw-animate-css; off under reduced motion via index.css):
    // ~150 Motion components per matrix made the first render the slowest thing in the workspace.
    <button
      key={`${f.id}:${f.status}`}
      type="button"
      data-cell={key}
      tabIndex={nav.active === key ? 0 : -1}
      onFocus={() => nav.setActive(key)}
      aria-label={`${f.rule_id} ${f.element_id}: ${m.label}`}
      onClick={() => openFinding(f.id)}
      className={cn(
        'inline-flex w-full animate-in items-center justify-center gap-1 rounded px-1 py-0.5 text-[11px] duration-300 fade-in-0 zoom-in-90',
        m.text,
        m.bg,
        'hover:ring-1 hover:ring-zinc-500',
      )}
    >
      <Icon aria-hidden className="size-3.5" />
      <span>{m.label}</span>
    </button>
  )
}

function ElementCell({ id, r }: { id: string; r: number }) {
  const focus = useUi((s) => s.focus)
  const { model } = useWorkspace()
  const nav = useContext(NavCtx)
  const key = cellKey(r, 0)
  return (
    <button
      type="button"
      data-cell={key}
      tabIndex={nav.active === key ? 0 : -1}
      onFocus={() => nav.setActive(key)}
      onClick={() => focus(id, canvasesFor(model, id))}
      className="whitespace-nowrap font-mono text-zinc-100 hover:underline"
    >
      {id}
    </button>
  )
}

/** Focusable columns per row: 0 (the element) plus every rule column with a finding. */
function focusableColumns(rows: MatrixRow[], rules: string[]): number[][] {
  return rows.map((row) => [0, ...rules.flatMap((rule, i) => (row.cells[rule] ? [i + 1] : []))])
}

function nearest(cols: number[], c: number): number {
  return cols.reduce((best, x) => (Math.abs(x - c) < Math.abs(best - c) ? x : best), cols[0])
}

export function ComplianceMatrix() {
  const view = useWorkspace()
  const whatIf = view.whatIf
  const findings = whatIf ? whatIf.findings : view.findings
  const { rows, rules } = useMemo(() => buildMatrix(findings), [findings])
  const rulesKey = rules.join(',')
  const [active, setActive] = useState('0:0')
  const columns = useMemo(
    () =>
      helper.columns([
        helper.display({
          id: 'element',
          header: 'Element',
          cell: (ctx) => <ElementCell id={ctx.row.original.element} r={ctx.row.index} />,
        }),
        ...rules.map((rule, i) =>
          helper.display({
            id: rule,
            header: rule,
            cell: (ctx) => {
              const f = ctx.row.original.cells[rule]
              // Unchecked cells stay empty (a CSS dot marks them); no element per blank cell.
              return f ? <Cell f={f} r={ctx.row.index} c={i + 1} /> : null
            },
          }),
        ),
      ]),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [rulesKey],
  )
  const table = useTable({ features, columns, data: rows, getRowId: (r) => r.element })
  const grid = useMemo(() => focusableColumns(rows, rules), [rows, rules])
  const [ar, ac] = active.split(':').map(Number)
  // Keep the single tab stop on a cell that exists (rows re-sort and change with revisions/what-ifs).
  const activeKey = grid[ar]?.includes(ac) ? active : grid.length ? cellKey(Math.min(ar, grid.length - 1), 0) : '0:0'
  const nav = useMemo(() => ({ active: activeKey, setActive }), [activeKey])

  const onKeyDown = (e: KeyboardEvent<HTMLTableElement>) => {
    const from = (e.target as HTMLElement).closest<HTMLElement>('[data-cell]')?.dataset.cell
    if (!from || !grid.length) return
    const [r, c] = from.split(':').map(Number)
    const last = grid.length - 1
    const moveRow = (to: number) => {
      const r2 = Math.max(0, Math.min(last, to))
      return cellKey(r2, nearest(grid[r2], c))
    }
    const next: Record<string, () => string> = {
      ArrowRight: () => cellKey(r, grid[r].find((x) => x > c) ?? c),
      ArrowLeft: () => cellKey(r, [...grid[r]].reverse().find((x) => x < c) ?? c),
      ArrowDown: () => moveRow(r + 1),
      ArrowUp: () => moveRow(r - 1),
      PageDown: () => moveRow(r + 10),
      PageUp: () => moveRow(r - 10),
      Home: () => (e.ctrlKey ? cellKey(0, 0) : cellKey(r, 0)),
      End: () => (e.ctrlKey ? cellKey(last, grid[last][grid[last].length - 1]) : cellKey(r, grid[r][grid[r].length - 1])),
    }
    const go = next[e.key]
    if (!go) return
    e.preventDefault()
    const key = go()
    setActive(key)
    e.currentTarget.querySelector<HTMLElement>(`[data-cell="${key}"]`)?.focus()
  }

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
          {/* A what-if result lists only the checks that fail or warn (M13). */}
          {whatIf ? `${findings.length} what-if findings` : `${findings.length} checks`}
        </span>
        {(['fail', 'warn', 'pass', 'n/a'] as const)
          // A what-if lists only failing checks, so its zero counts would read "0 pass" (D6): show non-zero ones.
          .filter((s) => (whatIf ? c[s] > 0 : s !== 'n/a' || c[s] > 0))
          .map((s) => {
            const Icon = STATUS_META[s].icon
            return (
              <span key={s} className={cn('inline-flex items-center gap-1 font-mono', STATUS_META[s].text)}>
                <Icon aria-hidden className="size-3.5" />
                {c[s]} {STATUS_META[s].label.toLowerCase()}
              </span>
            )
          })}
        {whatIf && <span className="text-zinc-400">({c.warn > 0 ? 'only failing and warning checks are listed' : 'only failing checks are listed'})</span>}
        <IllustrativeLabel className="ml-auto" />
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        <p id="matrix-keys" className="sr-only">
          Use the arrow keys to move between cells, Enter to open a finding.
        </p>
        <NavCtx.Provider value={nav}>
          <table
            className="w-full border-separate border-spacing-0 text-xs"
            aria-label="Compliance matrix"
            aria-describedby="matrix-keys"
            onKeyDown={onKeyDown}
          >
            <thead className="sticky top-0 z-10 bg-background">
              {table.getHeaderGroups().map((g) => (
                <tr key={g.id}>
                  {g.headers.map((h) => (
                    <th key={h.id} scope="col" className="border-b px-1 py-1.5 text-left font-mono font-medium text-zinc-400">
                      {h.id === 'element' ? (
                        'Element'
                      ) : (
                        <Tooltip>
                          {/* Hover help only; kept out of the tab order so the matrix stays one stop. */}
                          <TooltipTrigger tabIndex={-1} className="cursor-help">
                            {h.id}
                          </TooltipTrigger>
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
                    <td
                      key={cell.id}
                      className="border-b border-zinc-800/70 px-1 py-1 empty:text-center empty:text-zinc-600 empty:after:content-['·']"
                    >
                      <table.FlexRender cell={cell} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </NavCtx.Provider>
      </div>
    </div>
  )
}
