import { mkdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test } from '../tests/fixtures'
import type { Locator, Page } from '@playwright/test'

/**
 * Deck screenshots (issue #17). Drives the app to each state in docs/submission/deck/shots/README.md and saves a PNG
 * with exactly the file name the deck builder expects. Every value on screen comes from the app's own data (the recorded
 * run / static bundles); nothing is typed by hand, and the fictional-data banner stays visible.
 *
 * Each shot first asserts the content its README row describes, so a state that is still empty (for example the Options
 * tab before the golden capture, which has no options yet) FAILS the shot instead of saving an empty screen.
 *
 *   dry run (default)  writes to e2e/out/shots, so the deck's placeholders are not touched:
 *                      E2E_LOCAL=1 E2E_SHOTS=1 npx playwright test --project=shots
 *                      (s05-8 waits for the live sandbox, which a local run cannot reach: it times out there; run it against the deployed site)
 *   final capture      after the UI freeze and the golden-capture deploy, against the deployed site:
 *                      E2E_BASE_URL=https://kirchhoff.web.app E2E_SHOTS=1 SHOTS_WRITE=1 npx playwright test --project=shots
 *   manual shot        s11-2 (a frame of a live Hall B run) is captured by hand on the deployed site, because it needs the deployed agents and a
 *                      run; this spec SKIPS it always, so it can never overwrite it with a wrong screen. (s05-6 is a typed question to the
 *                      co-pilot and its engine card, so it is automated; the Gemini Live exchange itself is not captured.)
 */
const HERE = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(HERE, '..', '..')
const OUT = process.env.SHOTS_WRITE === '1' ? path.join(ROOT, 'docs', 'submission', 'deck', 'shots') : path.join(HERE, '..', 'out', 'shots')
mkdirSync(OUT, { recursive: true })

type Shot = {
  file: string
  /** Opens the state and asserts what it must show. Returns the element to crop to, or nothing for a full-screen capture. */
  open: (page: Page) => Promise<Locator | void>
  /** An explicit crop (CSS pixels) for a tile whose element is the whole page, where the element's own box would catch the fixed side panels. */
  clipOf?: (page: Page) => Promise<{ x: number; y: number; width: number; height: number }>
  live?: boolean
  /** Captured by hand (see the header); the spec never touches the file. */
  manual?: boolean
  /** Crop INSIDE the element (see tileClip): for a canvas that is already wider than the tile, where growing the crop would catch the tab strip around it. */
  inside?: boolean
}

const LONG = { timeout: 60_000 }
const settle = (page: Page, ms = 1500) => page.waitForTimeout(ms) // the 3D hall and the SLD animate in
const text = (page: Page, t: string | RegExp) => expect(page.getByText(t).first()).toBeVisible(LONG)

/** Opens a Hall A workspace URL; the lanes are hidden from the accessibility tree while a finding drawer is open. */
const workspace = async (page: Page, query = '') => {
  await page.goto(`/app/p/hall-a${query}`)
  await expect(page.getByRole('navigation', { name: 'Agent lanes' }).or(page.getByRole('dialog')).first()).toBeVisible(LONG)
  await settle(page, 2500)
}

const SHOTS: Shot[] = [
  {
    file: 's03-workspace-signed.png',
    open: async (page) => {
      await workspace(page)
      await text(page, /signed by Priya Raman/)
      await text(page, 'CDU gallery') // the lazy-loaded hall has drawn, not just its empty canvas
    },
  },
  {
    file: 's05-1-intake-quotes.png',
    // The bids inbox: the Hall B tender as the inbox agent triaged it (client, site, load, bid date, each found in the source) and the fit verdict.
    open: async (page) => {
      await page.goto('/app/inbox')
      await expect(page.getByRole('heading', { name: 'Bids inbox', level: 1 })).toBeVisible(LONG)
      await page.locator('a[href="/app/inbox/em-hall-b"]').click()
      const detail = page.getByRole('region', { name: 'Email' })
      await expect(detail.getByRole('region', { name: 'Fit verdict' })).toContainText('Pursue', LONG)
      await expect(detail.getByRole('region', { name: 'Fit verdict' })).toContainText('Day-zero supply')
      await settle(page, 800)
      return detail.getByRole('region', { name: 'Fit verdict' })
    },
  },
  {
    file: 's05-2-hall-3d-tiers.png',
    inside: true,
    open: async (page) => {
      await workspace(page, '?tab=hall')
      await text(page, 'CDU gallery') // a label of the drawn scene: the lazy-loaded hall has rendered, not just the empty canvas
      await settle(page, 1000)
      return page.locator('canvas').first()
    },
  },
  {
    file: 's05-3-compliance-matrix.png',
    open: async (page) => {
      await workspace(page, '?tab=matrix')
      // a wait only the matrix can satisfy (the text '150 checks' is also on the story strip and the Checker lane, outside the matrix)
      await expect(page.getByRole('table', { name: 'Compliance matrix' }).getByRole('button', { name: /: Pass$/ }).first()).toBeVisible(LONG)
      return page.getByRole('table', { name: 'Compliance matrix' })
    },
  },
  {
    file: 's05-4-option-r15-swap.png',
    open: async (page) => {
      await workspace(page, '?tab=options')
      await text(page, /R15, line transformer/) // the R15 swap line on the 2N card: needs the options from the golden capture
      return page.getByRole('article', { name: 'Option 2N' }) // the 2N card with its R15 swap line, not the whole (mostly empty) tab panel
    },
  },
  {
    file: 's05-5-impact-chain.png',
    open: async (page) => {
      await workspace(page)
      await page.locator('[data-tour="whatif-chip"]').click()
      const chain = page.getByRole('list', { name: 'Impact chain' })
      await expect(chain).toBeVisible()
      await text(page, 'Show all 18 impact chains')
      await settle(page, 1000)
      return chain
    },
  },
  {
    // The co-pilot after one typed question: the card in the Conversation panel (the engine check behind the answer, what changed on screen) next to the canvas it moved.
    file: 's05-6-copilot-voice.png',
    open: async (page) => {
      await workspace(page, '?tab=hall&rev=r1')
      await page.getByRole('textbox', { name: 'Ask the co-pilot' }).fill('Show me H-Z2')
      await page.getByRole('button', { name: 'Send' }).click()
      await text(page, /^Pipe H-Z2 \(header, DN\d+\) in zone Z2/) // the engine's record of the pipe
      await text(page, 'Engine check')
      await text(page, 'What changed on screen')
      await settle(page, 2500) // the camera flies to the pipe
    },
    clipOf: async () => ({ x: 700, y: 100, width: 1220, height: 813 }), // 3:2: the canvas and the whole right-hand panel
  },
  {
    file: 's05-7-review-stamp.png',
    open: async (page) => {
      await page.goto('/app/p/hall-a/review/r2')
      await text(page, 'APPROVED')
      await settle(page)
      const stamp = page.getByRole('figure', { name: 'Approval stamp' }) // the stamp's own accessible name, not a class guess
      await expect(stamp).toContainText('sha256')
      return stamp
    },
  },
  {
    file: 's05-8-integrations.png',
    open: async (page) => {
      await page.goto('/app/integrations')
      await expect(page.getByRole('region', { name: 'Latest handoff' })).toBeVisible(LONG)
      await text(page, /Connected · last sync now/) // the cards first show the cached snapshot; the shot waits for the live sandbox
      await settle(page, 1000)
    },
    // the content column from the heading to the last card, widened to 3:2 about its centre: the "Getting started" checklist stays out of the frame
    clipOf: async (page) => {
      const top = (await page.getByRole('heading', { name: 'Integrations', exact: true }).first().boundingBox())!.y - 14
      const last = (await page.getByRole('button', { name: 'View data' }).last().boundingBox())!
      const height = last.y + last.height + 22 - top
      const width = height * 1.5
      return { x: 960 - width / 2, y: top, width, height }
    },
  },
  {
    file: 's05-9-solar-field.png',
    open: async (page) => {
      await page.goto('/app/p/solar-5mwp')
      const field = page.getByRole('img', { name: 'Site geometry' })
      await expect(field).toBeVisible(LONG)
      await settle(page, 1000)
      return field
    },
  },
  {
    file: 's07-finding-drawer-r05.png',
    open: async (page) => {
      await workspace(page, '?tab=matrix&rev=r1&finding=R05%3AFA-01')
      const drawer = page.getByRole('dialog').first()
      await expect(drawer).toContainText('2.16%')
      await expect(drawer).toContainText('§4.6')
    },
    // The drawer is a full-height side sheet and its content ends about two thirds down: clip to the lowest text plus a margin, so the PNG is not a third blank
    // (a blank third made the slide's 3.9 in slot render the drawer text at about 3 pt).
    clipOf: async (page) => {
      const drawer = page.getByRole('dialog').first()
      const b = (await drawer.boundingBox())!
      const bottom = await drawer.evaluate((el) => {
        let max = 0
        el.querySelectorAll('*').forEach((n) => {
          const r = n.getBoundingClientRect()
          if (n.children.length === 0 && (n.textContent ?? '').trim() && r.width > 0 && r.height > 0) max = Math.max(max, r.bottom)
        })
        return max
      })
      return { x: b.x, y: b.y, width: b.width, height: Math.min(b.height, bottom - b.y + 24) }
    },
  },
  {
    file: 's11-1-projects-dashboard.png',
    open: async (page) => {
      await page.goto('/app')
      await text(page, 'Signed')
      await text(page, 'Not started')
      await settle(page, 1000)
    },
  },
  { file: 's11-2-hall-b-live-run.png', manual: true, open: async () => {} },
  {
    file: 's11-3-finding-drawer-r11.png',
    open: async (page) => {
      await workspace(page, '?tab=hall&rev=r1&finding=R11%3AH-Z2')
      const drawer = page.getByRole('dialog').first()
      await expect(drawer).toContainText('H-Z2')
      await expect(drawer).toContainText('§6.3.4')
      await text(page, 'CDU gallery') // the hall behind the drawer has drawn
    },
  },
  {
    file: 's11-4-options-r15-swap.png',
    open: async (page) => {
      await workspace(page, '?tab=options')
      await text(page, /R15, line transformer/) // needs the options from the golden capture
      const card = page.getByRole('article', { name: 'Option 2N' }) // the card the README row names, not any of the three
      await expect(card).toContainText('Selected')
      await expect(card).toContainText('38.07%')
    },
  },
  {
    file: 's11-5-what-if-200kw.png',
    open: async (page) => {
      await workspace(page)
      await page.locator('[data-tour="whatif-chip"]').click()
      await expect(page.getByRole('list', { name: 'Impact chain' })).toBeVisible()
      await text(page, 'Show all 18 impact chains')
      await text(page, 'Show all 60 findings')
      await settle(page, 1500)
    },
  },
  {
    file: 's11-6-review-approved.png',
    open: async (page) => {
      await page.goto('/app/p/hall-a/review/r2')
      await text(page, 'APPROVED')
      await settle(page)
    },
  },
  {
    file: 's12-compliance-matrix-first-pass.png',
    open: async (page) => {
      await workspace(page, '?tab=matrix&rev=r1')
      await text(page, '149 checks')
      await expect(page.getByRole('button', { name: /: Fail$/ })).toHaveCount(2)
    },
  },
  {
    file: 's13-grid-pack.png',
    open: async (page) => {
      await page.goto('/app/p/grid-132kv')
      await expect(page.getByRole('table', { name: 'Asset options' })).toBeVisible(LONG)
      await expect(page.getByRole('region', { name: 'Mini SLD' })).toBeVisible()
      await expect(page.getByRole('img', { name: 'Site geometry' })).toBeVisible() // the 132 kV route drawn as a line, which the README row names
      await settle(page, 1000)
    },
  },
  {
    file: 's13-solar-pack.png',
    open: async (page) => {
      await page.goto('/app/p/solar-5mwp')
      await expect(page.getByRole('table', { name: 'Asset options' })).toBeVisible(LONG)
      await text(page, /STR-28/)
      await settle(page, 1000)
    },
  },
]

/** Slide 5's nine tiles are 3:2: the crop is the named element widened or heightened to 3:2 around its centre (so a narrow lane or a small chain keeps its
 *  surroundings instead of being stretched), and a tall element (the matrix) keeps its top part. Never leaves the 1920 x 1080 page. */
const TILES = new Set(['s05-1-intake-quotes.png', 's05-2-hall-3d-tiers.png', 's05-3-compliance-matrix.png', 's05-4-option-r15-swap.png', 's05-5-impact-chain.png',
  's05-7-review-stamp.png', 's05-8-integrations.png', 's05-9-solar-field.png'])
/** Crops are taken at 2x pixel density, so a small element is still sharp on a slide; full-screen shots stay at 1x (1920 x 1080). */
const SHARP = new Set([...TILES, 's05-6-copilot-voice.png', 's07-finding-drawer-r05.png'])

async function tileClip(page: Page, target: Locator, ratio = 3 / 2, pad = 16, inside = false) {
  await target.scrollIntoViewIfNeeded()
  const b = await target.boundingBox()
  if (!b) return null
  const vp = page.viewportSize() ?? { width: 1920, height: 1080 }
  // Opt-in (`inside`, only the 3D canvas): an element already at least as wide as the ratio is cropped INSIDE itself, trimming the width from the right (the
  // canvas's legend sits at its left edge), so the crop never reaches the tab strip or the footer around it. Not for cards or figures: it would cut their content.
  if (inside && b.width / b.height >= ratio && b.height <= vp.height) {
    return { x: b.x, y: b.y, width: b.height * ratio, height: b.height }
  }
  let x = Math.max(0, b.x - pad), y = Math.max(0, b.y - pad)
  let w = Math.min(b.width + 2 * pad, vp.width), h = Math.min(b.height + 2 * pad, vp.height)
  if (b.height > vp.height) h = Math.min(w / ratio, vp.height) // taller than the screen: keep the top part
  if (w / h > ratio) h = w / ratio
  else w = h * ratio
  w = Math.min(w, vp.width)
  h = Math.min(h, vp.height)
  if (w / h > ratio) w = h * ratio
  else h = w / ratio
  if (b.height <= vp.height) {
    x = b.x + b.width / 2 - w / 2
    y = b.y + b.height / 2 - h / 2
  }
  x = Math.max(0, Math.min(x, vp.width - w))
  y = Math.max(0, Math.min(y, vp.height - h))
  return { x, y, width: w, height: h }
}

for (const [scale, group] of [[2, SHOTS.filter((s) => SHARP.has(s.file))], [1, SHOTS.filter((s) => !SHARP.has(s.file))]] as const) {
  test.describe(`shots at ${scale}x pixel density`, () => {
    test.use({ deviceScaleFactor: scale })
    for (const shot of group) {
  test(shot.file, async ({ page }) => {
    test.skip(shot.manual === true, 'captured by hand on the deployed site (see the header and the README); never rewritten here')
    test.skip(shot.live === true && process.env.E2E_LIVE !== '1', 'needs the deployed agents: set E2E_LIVE=1')
    test.setTimeout(150_000)
    await page.setViewportSize({ width: 1920, height: 1080 })
    const target = await shot.open(page)
    // The banner must be visible in every capture: full-screen shots show it; for a crop, check it is on the page.
    // (By text, not by role: an open finding drawer is a modal and hides the banner from the accessibility tree.)
    await expect(page.getByText('all companies, people and data are fictional').first()).toBeVisible()
    if (await page.getByRole('dialog').count()) await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur?.()) // the open drawer focuses its first button: no focus ring in the picture
    const file = path.join(OUT, shot.file)
    const clip = shot.clipOf ? await shot.clipOf(page) : target && TILES.has(shot.file) ? await tileClip(page, target, 3 / 2, 16, shot.inside) : null
    if (clip) await page.screenshot({ path: file, clip })
    else if (target) await target.screenshot({ path: file })
    else await page.screenshot({ path: file })
  })
    }
  })
}
