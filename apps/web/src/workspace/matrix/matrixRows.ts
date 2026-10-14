import { RULES, statusRank, worstStatus } from '@/lib/status'
import type { Finding, FindingStatus } from '@/lib/types'

export interface MatrixRow {
  element: string
  cells: Record<string, Finding>
  worst: FindingStatus | null
}

/** Rows = elements, columns = rules R01–R15 (+R04b and any rule id the engine adds). Fails first. */
export function buildMatrix(findings: Finding[]): { rows: MatrixRow[]; rules: string[] } {
  const byElement = new Map<string, Record<string, Finding>>()
  for (const f of findings) byElement.set(f.element_id, { ...(byElement.get(f.element_id) ?? {}), [f.rule_id]: f })
  const rows = [...byElement].map(([element, cells]) => ({
    element,
    cells,
    worst: worstStatus(Object.values(cells).map((f) => f.status)),
  }))
  rows.sort(
    (a, b) =>
      statusRank(b.worst ?? 'n/a') - statusRank(a.worst ?? 'n/a') ||
      a.element.localeCompare(b.element, 'en', { numeric: true }),
  )
  const canonical = RULES.map((r) => r.id)
  const extra = [...new Set(findings.map((f) => f.rule_id))].filter((r) => !canonical.includes(r)).sort()
  return { rows, rules: [...canonical, ...extra] }
}
