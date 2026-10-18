import { defineConfig, devices } from '@playwright/test'

/**
 * Kirchhoff e2e (spec section 16). Three ways to run it:
 *   make e2e-local   serves apps/web itself (E2E_LOCAL=1), blocks Google endpoints, needs no cloud access
 *   make e2e-static  the static journeys against E2E_BASE_URL (default https://kirchhoff.web.app)
 *   make e2e-live    the Hall B live run, opt-in (E2E_LIVE=1): it calls the deployed agents (Gemini)
 */
const local = process.env.E2E_LOCAL === '1'
const LOCAL_URL = 'http://localhost:5173'
const desktop = { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } }

export default defineConfig({
  testDir: './tests',
  globalSetup: './global-setup.ts', // local runs only: pays the Vite dev server's first-compile cost before test 1
  outputDir: './out/artifacts',
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list'], ['html', { outputFolder: './out/report', open: 'never' }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? (local ? LOCAL_URL : 'https://kirchhoff.web.app'),
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  webServer: local
    ? { command: 'npm run dev -- --port 5173 --strictPort', cwd: '../apps/web', url: LOCAL_URL, reuseExistingServer: true, timeout: 120_000 }
    : undefined,
  projects: [
    { name: 'static', testMatch: /(static|replay-offline|inbox)\.spec\.ts$/, use: desktop },
    { name: 'phone', testMatch: /phone\.spec\.ts$/, use: { ...devices['Pixel 7'] } },
    { name: 'live', testMatch: /live\.spec\.ts$/, use: desktop },
    // Deck screenshots (issue #17): opt-in, never part of a normal run. See shots/capture.spec.ts.
    ...(process.env.E2E_SHOTS === '1'
      ? [{ name: 'shots', testDir: './shots', testMatch: /capture\.spec\.ts$/, use: { ...devices['Desktop Chrome'], viewport: { width: 1920, height: 1080 } } }]
      : []),
    // Video footage (issue #25): opt-in, one WebM clip per storyboard beat at 1920 x 1080. See shots/footage.spec.ts.
    ...(process.env.E2E_FOOTAGE === '1'
      ? [
          {
            name: 'footage',
            testDir: './shots',
            testMatch: /footage(-guided)?(-live)?\.spec\.ts$/,
            use: {
              ...devices['Desktop Chrome'],
              // FOOTAGE_VIEWPORT=1280x720 records the app at a smaller window: its UI is then larger in the frame, and the clip is upscaled to 1920 x 1080 when it is converted
              viewport: { width: Number((process.env.FOOTAGE_VIEWPORT ?? '1920x1080').split('x')[0]), height: Number((process.env.FOOTAGE_VIEWPORT ?? '1920x1080').split('x')[1]) },
              deviceScaleFactor: 1,
              video: { mode: 'on' as const, size: { width: Number((process.env.FOOTAGE_VIEWPORT ?? '1920x1080').split('x')[0]), height: Number((process.env.FOOTAGE_VIEWPORT ?? '1920x1080').split('x')[1]) } },
              screenshot: 'off' as const,
              trace: 'off' as const,
            },
          },
        ]
      : []),
  ],
})