import type { CitationKind } from '@/store/ui'

/** "Tender" or "Drawing" for a cited PDF: the opener's hint, else the doc id ("hall-a-plan" is the drawing plot). */
export function docLabel(docId: string, kind: CitationKind | null): string {
  return (kind ?? (/(plan|drawing|dwg|layout)/i.test(docId) ? 'drawing' : 'tender')) === 'drawing' ? 'Drawing' : 'Tender'
}
