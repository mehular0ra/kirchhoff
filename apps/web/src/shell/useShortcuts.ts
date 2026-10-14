import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router'
import { isPresentationMode } from '@/lib/flags'

const typing = (t: EventTarget | null) =>
  t instanceof HTMLElement && (t.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName))

/** Keyboard (spec §13.5): `?` help and tour, `g p` projects, `g i` integrations. Disabled in presentation mode (`?present=1`), so a recording never pops the dialog. */
export function useShortcuts(onHelp: () => void): void {
  const navigate = useNavigate()
  const pendingG = useRef(0)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isPresentationMode() || typing(e.target) || e.metaKey || e.ctrlKey || e.altKey) return
      if (e.key === '?') {
        e.preventDefault()
        onHelp()
        return
      }
      if (e.key === 'g') {
        pendingG.current = Date.now()
        return
      }
      if (Date.now() - pendingG.current < 1000) {
        if (e.key === 'p') navigate('/app')
        if (e.key === 'i') navigate('/app/integrations')
        pendingG.current = 0
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [navigate, onHelp])
}
