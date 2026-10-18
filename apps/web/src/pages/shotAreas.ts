/**
 * Where the three legend areas sit in the hero screenshot. Measured on the real layout at the size the screenshot was captured at (1000 x 625 px): the agent
 * lanes, the 3D hall and the co-pilot are the columns 0-224, 224-720 and 720-1000 px across, from 99 px down (below the app header and breadcrumb row) to the
 * revisions bar at 586.5 px. Re-measure them (and update the numbers here) whenever the screenshot is retaken at another width.
 */
export const SHOT = { w: 1000, h: 625, cols: [0, 224, 720, 1000], top: 99, bottom: 586.5 } as const

const pct = (n: number, of: number) => `${Number(((n / of) * 100).toFixed(2))}%`
const area = (from: number, to: number) => ({
  left: pct(SHOT.cols[from], SHOT.w),
  top: pct(SHOT.top, SHOT.h),
  width: pct(SHOT.cols[to] - SHOT.cols[from], SHOT.w),
  height: pct(SHOT.bottom - SHOT.top, SHOT.h),
})

/** The three areas as CSS boxes in percent of the picture: left, top, width, height. */
export const AREAS = { left: area(0, 1), centre: area(1, 2), right: area(2, 3) } as const
