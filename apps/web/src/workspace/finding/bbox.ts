import type { Citation } from '@/lib/types'

/**
 * pdfplumber bbox (x0, top, x1, bottom in PDF points, origin top-left) → CSS pixels on a
 * react-pdf page rendered at `scale` (pdf.js renders 1 pt as 1 CSS px at scale 1).
 */
export function bboxToCss(
  bbox: Citation['bbox'],
  scale: number,
  pad = 2,
): { left: number; top: number; width: number; height: number } | null {
  if (!bbox) return null
  const [x0, top, x1, bottom] = bbox
  return {
    left: x0 * scale - pad,
    top: top * scale - pad,
    width: (x1 - x0) * scale + pad * 2,
    height: (bottom - top) * scale + pad * 2,
  }
}
