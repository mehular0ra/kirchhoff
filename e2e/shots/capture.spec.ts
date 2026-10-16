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
 *   final capture      after the UI freeze and the golden-capture deploy, against the deployed site:
 *                      E2E_BASE_URL=https://kirchhoff.web.app E2E_SHOTS=1 SHOTS_WRITE=1 npx playwright test --project=shots
 *   live-only shots    (Hall B live run, voice) also need E2E_LIVE=1: they call the deployed agents.
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
    },
  },
  {
    file: 's05-1-intake-quotes.png',
    open: async (page) => {
      await workspace(page, '?replay=1')
      await text(page, /quote verified/i) // needs the recorded run (golden capture)
      const lanes = page.getByRole('navigation', { name: 'Agent lanes' })
      await lanes.getByRole('button', { name: /Intake/ }).click() // expand: the verified quotes, the DXF read and the contradiction it found
      await text(page, 'Contradiction found')
      await settle(page, 800)
      return lanes.getByRole('listitem').first() // the Intake lane itself, not the whole column
    },
  },
  {
    file: 's05-2-hall-3d-tiers.png',
    open: async (page) => {
      await workspace(page, '?tab=hall')
      return page.locator('canvas').first()
    },
  },
  {
    file: 's05-3-compliance-matrix.png',
    open: async (page) => {
      await workspace(page, '?tab=matrix')
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
  { file: 's05-6-copilot-voice.png', live: true, open: async (page) => { await workspace(page) } },
  {
    file: 's05-7-review-stamp.png',
    open: async (page) => {
      await page.goto('/app/p/hall-a/review/r2')
      await text(page, 'APPROVED')
      await settle(page)
      return page.getByRole('figure', { name: 'Approval stamp' }) // the stamp's own accessible name, not a class guess
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
      return drawer
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
  { file: 's11-2-hall-b-live-run.png', live: true, open: async (page) => { await page.goto('/app/p/hall-b') } },
  {
    file: 's11-3-finding-drawer-r11.png',
    open: async (page) => {
      await workspace(page, '?tab=hall&rev=r1&finding=R11%3AH-Z2')
      const drawer = page.getByRole('dialog').first()
      await expect(drawer).toContainText('H-Z2')
      await expect(drawer).toContainText('§6.3.4')
    },
  },
  {
    file: 's11-4-options-r15-swap.png',
    open: async (page) => {
      await workspace(page, '?tab=options')
      await text(page, /R15, line transformer/) // needs the options from the golden capture
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
const SHARP = new Set([...TILES, 's07-finding-drawer-r05.png'])

async function tileClip(page: Page, target: Locator, ratio = 3 / 2, pad = 16) {
  await target.scrollIntoViewIfNeeded()
  const b = await target.boundingBox()
  if (!b) return null
  const vp = page.viewportSize() ?? { width: 1920, height: 1080 }
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
    test.skip(shot.live === true && process.env.E2E_LIVE !== '1', 'needs the deployed agents: set E2E_LIVE=1')
    test.setTimeout(150_000)
    await page.setViewportSize({ width: 1920, height: 1080 })
    const target = await shot.open(page)
    // The banner must be visible in every capture: full-screen shots show it; for a crop, check it is on the page.
    // (By text, not by role: an open finding drawer is a modal and hides the banner from the accessibility tree.)
    await expect(page.getByText('all companies, people and data are fictional').first()).toBeVisible()
    const file = path.join(OUT, shot.file)
    const clip = shot.clipOf ? await shot.clipOf(page) : target && TILES.has(shot.file) ? await tileClip(page, target) : null
    if (clip) await page.screenshot({ path: file, clip })
    else if (target) await target.screenshot({ path: file })
    else await page.screenshot({ path: file })
  })
    }
  })
}
