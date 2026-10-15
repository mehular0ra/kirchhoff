import { Monitor, X } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { readJson, writeJson } from '@/lib/storage'

const KEY = 'desktopNote.dismissed'

/**
 * Phones only (CSS md:hidden; UX-1 D13 fallback): the three-pane workspace is built for a desktop screen. The
 * tour still works here (the workspace scrolls sideways inside its own frame), and the note points at the
 * pages that read well on a phone. Dismissible, remembered per browser.
 */
export function DesktopNote({ reviewHref }: { reviewHref: string | null }) {
  const [hidden, setHidden] = useState(() => readJson<boolean>(KEY, false))
  if (hidden) return null
  return (
    <div aria-label="Best on a desktop" className="flex items-start gap-2 border-b bg-zinc-900 px-3 py-2 text-xs text-zinc-300 md:hidden">
      <Monitor aria-hidden className="mt-0.5 size-3.5 shrink-0 text-sky-300" />
      <p className="min-w-0 flex-1">
        <span className="font-medium text-zinc-100">Best on a desktop.</span> This workspace is built for a large screen; swipe sideways to
        see the canvas and co-pilot. On a phone, the {reviewHref ? <Link to={reviewHref} className="text-sky-300 underline underline-offset-2">review page</Link> : 'review page'} and{' '}
        <Link to="/app/integrations" className="text-sky-300 underline underline-offset-2">
          Integrations
        </Link>{' '}
        read best.
      </p>
      <button
        type="button"
        aria-label="Dismiss"
        onClick={() => {
          writeJson(KEY, true)
          setHidden(true)
        }}
        className="-m-1 rounded p-1 text-zinc-400 hover:text-zinc-100"
      >
        <X aria-hidden className="size-3.5" />
      </button>
    </div>
  )
}
