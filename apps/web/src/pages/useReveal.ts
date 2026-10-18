import { useReducedMotion } from 'motion/react'

const EASE = [0.2, 0.7, 0.2, 1] as const

/** Motion that starts when something scrolls into view needs IntersectionObserver; where it is missing (an old browser, a server render) the page just shows. */
export const canObserveViewport = () => typeof IntersectionObserver !== 'undefined'

type RevealOptions = { on?: 'load' | 'view'; delay?: number; y?: number; fade?: boolean }

/**
 * Props for a `motion.*` element that enters once, on load (the hero) or when it is scrolled to. Spread them on the element.
 * Under reduced motion (or without viewport observing, for `on: 'view'`) they are empty, so the element is plain and in its final state from the first frame.
 * `fade: false` only moves it, so what it holds is painted from the first frame (the hero screenshot, which would otherwise hold back the page's largest paint).
 */
export function useReveal() {
  const reduce = useReducedMotion()
  return ({ on = 'view', delay = 0, y = 14, fade = true }: RevealOptions = {}) => {
    if (reduce || (on === 'view' && !canObserveViewport())) return {}
    const shown = { ...(fade ? { opacity: 1 } : {}), y: 0, transition: { duration: 0.55, delay, ease: EASE } }
    const initial = { ...(fade ? { opacity: 0 } : {}), y }
    return on === 'load' ? { initial, animate: shown } : { initial, whileInView: shown, viewport: { once: true, amount: 0.3 } }
  }
}
