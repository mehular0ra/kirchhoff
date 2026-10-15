// Tender citation viewer: opens the PDF at the cited page with a highlight box from pdfplumber's bbox.
import 'react-pdf/dist/Page/TextLayer.css'
import { ChevronLeft, ChevronRight, CircleCheck, CircleX, FileText } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import workerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { docUrl } from '@/data/staticData'
import { useUi } from '@/store/ui'
import { bboxToCss } from './bbox'

// react-pdf requires the worker to be configured in the same module that renders <Document>.
pdfjs.GlobalWorkerOptions.workerSrc = workerSrc

const SCALE = 1.3

export default function PdfViewer() {
  const citation = useUi((s) => s.citation)
  const close = useUi((s) => s.closeCitation)
  const [page, setPage] = useState(citation?.page ?? 1)
  const [numPages, setNumPages] = useState<number | null>(null)
  const highlight = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (citation) setPage(citation.page)
  }, [citation])

  if (!citation) return null
  const box = page === citation.page ? bboxToCss(citation.bbox, SCALE) : null
  return (
    <Dialog open onOpenChange={(o) => !o && close()}>
      <DialogContent className="flex max-h-[90dvh] flex-col gap-3 sm:max-w-[min(62rem,94vw)]">
        <DialogHeader>
          <DialogTitle>
            {citation.clause ? `Tender ${citation.clause} · page ${citation.page}` : `Tender · page ${citation.page}`}
          </DialogTitle>
          {/* Only a citation that carries its quote is called verified (spec §6.3, final review I11). */}
          {citation.quote ? (
            <DialogDescription className="flex items-start gap-1.5">
              <CircleCheck aria-hidden className="mt-0.5 size-4 shrink-0 text-emerald-400" />
              <span>Verified quote: “{citation.quote}”</span>
            </DialogDescription>
          ) : (
            <DialogDescription className="flex items-start gap-1.5">
              <FileText aria-hidden className="mt-0.5 size-4 shrink-0 text-zinc-400" />
              <span>Tender PDF · page {citation.page}</span>
            </DialogDescription>
          )}
        </DialogHeader>
        <div className="min-h-0 flex-1 overflow-auto rounded border bg-zinc-200">
          <Document
            file={docUrl(citation.doc_id)}
            suspense={false}
            loading={<p className="p-6 text-sm text-zinc-700">Loading tender…</p>}
            error={
              <p className="flex items-center gap-1.5 p-6 text-sm text-rose-700">
                <CircleX aria-hidden className="size-4" /> Could not load {docUrl(citation.doc_id)}.
              </p>
            }
            onLoadSuccess={(pdf: { numPages: number }) => setNumPages(pdf.numPages)}
          >
            <div className="relative mx-auto w-fit">
              <Page
                pageNumber={page}
                scale={SCALE}
                suspense={false}
                renderAnnotationLayer={false}
                onRenderSuccess={() => highlight.current?.scrollIntoView({ block: 'center' })}
              />
              {box && (
                <div
                  ref={highlight}
                  data-testid="citation-highlight"
                  aria-hidden
                  className="pointer-events-none absolute rounded-sm bg-yellow-300/40 outline-2 outline-amber-500"
                  style={{ left: box.left, top: box.top, width: box.width, height: box.height }}
                />
              )}
            </div>
          </Document>
        </div>
        <div className="flex items-center justify-between text-xs text-zinc-400">
          <Button variant="ghost" size="xs" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            <ChevronLeft aria-hidden /> Previous
          </Button>
          <span>
            Page {page}
            {numPages ? ` of ${numPages}` : ''}
          </span>
          <Button variant="ghost" size="xs" disabled={numPages !== null && page >= numPages} onClick={() => setPage(page + 1)}>
            Next <ChevronRight aria-hidden />
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
