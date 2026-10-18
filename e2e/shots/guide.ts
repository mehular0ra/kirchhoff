import type { Locator, Page } from '@playwright/test'

/**
 * A visible cursor and highlight boxes drawn INTO the page, so a screen recording shows where the user is clicking and what is
 * being explained (Mehul's video review, 18 Oct 2026). Everything is pointer-events: none and lives in its own fixed layer, so it
 * cannot change what the app does. Call `installGuide(page)` before the first `page.goto`.
 *
 *   await installGuide(page)
 *   await clickAt(page, locator)                       // the cursor glides to the element, a ripple shows the click
 *   await highlight(page, locator, 'what to look at')  // a ring with a label, held for ms (spot: dims the rest of the page)
 */
const SCRIPT = `(() => {
  if (window.__kov) return
  const boot = () => {
    if (window.__kov || !document.documentElement) return
    const st = document.createElement('style')
    st.textContent = '@keyframes __kr{from{transform:translate(-50%,-50%) scale(.2);opacity:.9}to{transform:translate(-50%,-50%) scale(2.4);opacity:0}}'
    document.documentElement.appendChild(st)
    const root = document.createElement('div')
    root.style.cssText = 'position:fixed;inset:0;z-index:2147483647;pointer-events:none'
    const cur = document.createElement('div')
    cur.style.cssText = 'position:absolute;left:0;top:0;width:36px;height:36px;transform:translate(-200px,-200px);filter:drop-shadow(0 2px 4px rgba(0,0,0,.4))'
    cur.innerHTML = '<svg viewBox="0 0 24 24" width="36" height="36"><path d="M4 2l15 9-6.5 1.6L9 19z" fill="#fff" stroke="#0b0b0f" stroke-width="1.5" stroke-linejoin="round"/></svg>'
    root.appendChild(cur)
    document.documentElement.appendChild(root)
    window.__kov = { root, cur }
    document.addEventListener('mousemove', (e) => { cur.style.transform = 'translate(' + e.clientX + 'px,' + e.clientY + 'px)' }, true)
    document.addEventListener('mousedown', (e) => {
      const r = document.createElement('div')
      r.style.cssText = 'position:absolute;left:' + e.clientX + 'px;top:' + e.clientY + 'px;width:44px;height:44px;border-radius:50%;border:3px solid #6366f1;background:rgba(99,102,241,.18);animation:__kr .55s ease-out forwards'
      root.appendChild(r)
      setTimeout(() => r.remove(), 650)
    }, true)
  }
  if (document.documentElement) boot()
  document.addEventListener('DOMContentLoaded', boot)
  window.__khl = (b, label, ms, spot) => {
    boot()
    const root = window.__kov.root
    const box = document.createElement('div')
    box.style.cssText = 'position:absolute;left:' + b.x + 'px;top:' + b.y + 'px;width:' + b.width + 'px;height:' + b.height + 'px;border:3px solid #6366f1;border-radius:12px;opacity:0;transition:opacity .25s;box-shadow:' + (spot ? '0 0 0 9999px rgba(8,10,30,.42),' : '') + '0 0 0 5px rgba(99,102,241,.28),0 0 28px rgba(99,102,241,.6)'
    const tag = document.createElement('div')
    tag.textContent = label
    tag.style.cssText = 'position:absolute;left:0;top:0;padding:7px 16px;border-radius:10px;background:#0b0b0f;color:#fff;font:600 21px Inter,system-ui,sans-serif;white-space:nowrap;opacity:0;transition:opacity .25s;box-shadow:0 4px 14px rgba(0,0,0,.35)'
    root.appendChild(box)
    root.appendChild(tag)
    const w = tag.offsetWidth, h = tag.offsetHeight
    const above = b.y - h - 10 >= 6
    tag.style.left = Math.max(8, Math.min(b.x, window.innerWidth - w - 8)) + 'px'
    tag.style.top = (above ? b.y - h - 10 : Math.min(b.y + b.height + 10, window.innerHeight - h - 8)) + 'px'
    requestAnimationFrame(() => { box.style.opacity = 1; tag.style.opacity = 1 })
    setTimeout(() => { box.style.opacity = 0; tag.style.opacity = 0; setTimeout(() => { box.remove(); tag.remove() }, 320) }, ms)
  }
})()`

const position = new WeakMap<Page, { x: number; y: number }>()

/**
 * FOOTAGE_ZOOM=1.5 lays the app out as if the window were 1280 wide and draws it 1.5x larger (CSS zoom on the body, not on the
 * overlay layer), so the 1920 x 1080 recording keeps full sharpness and the platform's small text becomes readable.
 */
export async function installGuide(page: Page, zoom = Number(process.env.FOOTAGE_ZOOM ?? 1)) {
  await page.addInitScript(SCRIPT)
  if (zoom !== 1) {
    await page.addInitScript((z) => {
      const apply = () => {
        document.body.style.zoom = String(z)
      }
      if (document.body) apply()
      else document.addEventListener('DOMContentLoaded', apply)
    }, zoom)
  }
}

type Box = { x: number; y: number; width: number; height: number }
const center = (b: Box) => ({ x: b.x + b.width / 2, y: b.y + b.height / 2 })

/** The cursor glides (eased) from where it was to the point, over about ms. */
export async function glide(page: Page, to: { x: number; y: number }, ms = 800) {
  const from = position.get(page) ?? { x: 1500, y: 760 }
  const n = Math.max(10, Math.round(ms / 18))
  for (let i = 1; i <= n; i++) {
    const t = i / n
    const e = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2
    await page.mouse.move(from.x + (to.x - from.x) * e, from.y + (to.y - from.y) * e)
    await page.waitForTimeout(ms / n)
  }
  position.set(page, to)
}

/** Moves the cursor to the element (scrolling it into view first), pauses a beat, then clicks it. */
export async function clickAt(page: Page, target: Locator, ms = 800) {
  await target.scrollIntoViewIfNeeded()
  const b = (await target.boundingBox())!
  await glide(page, center(b), ms)
  await page.waitForTimeout(260)
  await target.click()
}

/** Moves the cursor over an element without clicking (a hover, to point at it). */
export async function pointAt(page: Page, target: Locator, ms = 700) {
  const b = (await target.boundingBox())!
  await glide(page, center(b), ms)
}

/** A highlight ring (or a dimming spotlight) with a short label around the element, held for ms. Resolves after the hold. */
export async function highlight(page: Page, target: Locator | Box, label: string, ms = 2600, opts: { spot?: boolean; pad?: number } = {}) {
  if ('scrollIntoViewIfNeeded' in target) {
    await target.scrollIntoViewIfNeeded()
    // Centre it when it sits against an edge of the screen, so its ring and label are both in frame.
    await target.evaluate((el) => {
      const r = el.getBoundingClientRect()
      if (r.top < 120 || r.bottom > window.innerHeight - 120) el.scrollIntoView({ block: 'center', behavior: 'instant' })
    })
    await target.page().waitForTimeout(250)
  }
  const raw = 'boundingBox' in target ? await target.boundingBox() : target
  if (!raw) return
  const pad = opts.pad ?? 8
  const b = { x: Math.max(2, raw.x - pad), y: Math.max(2, raw.y - pad), width: raw.width + 2 * pad, height: raw.height + 2 * pad }
  await page.evaluate(([bb, l, m, s]) => (window as unknown as { __khl: (b: unknown, l: string, m: number, s: boolean) => void }).__khl(bb, l, m, s), [b, label, ms, !!opts.spot] as const)
  await page.waitForTimeout(ms)
}
