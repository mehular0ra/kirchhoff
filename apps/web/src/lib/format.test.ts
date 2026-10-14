import { describeKey, fillPlaceholders, fmtElapsed, fmtKeyValue, fmtQty, fmtTs, fmtUsd, shortHash } from './format'

test('quantities keep engine values and only add grouping and units', () => {
  expect(fmtQty(2.16, '%')).toBe('2.16%')
  expect(fmtQty(1546, 'A')).toBe('1,546 A')
  expect(fmtQty(null, 'A')).toBe('—')
  expect(fmtUsd(4200000)).toBe('$4,200,000')
  expect(fmtUsd(18000, true)).toBe('+$18,000')
})

test('timestamps are unix seconds rendered in IST', () => {
  expect(fmtTs(1760000500)).toBe('9 Oct 2025, 14:31')
})

test('elapsed clock', () => {
  expect(fmtElapsed(75)).toBe('01:15')
  expect(fmtElapsed(3725)).toBe('1:02:05')
})

test('fills {value} and {limit} from the finding record', () => {
  const text = fillPlaceholders('FA-01 drops {value}, above the {limit} limit.', { value: 2.16, limit: 2.0, unit: '%' })
  expect(text).toBe('FA-01 drops 2.16%, above the 2% limit.')
})

test('never doubles a unit the engine template already writes (ruling R20)', () => {
  const pct = { value: 2.16, limit: 2.0, unit: '%' }
  expect(fillPlaceholders('Drop via FA-01 is {value}% against a limit of {limit}%.', pct)).toBe(
    'Drop via FA-01 is 2.16% against a limit of 2%.',
  )
  expect(fillPlaceholders('One circuit carries {value} A against {limit} A.', { value: 790, limit: 500, unit: 'A' })).toBe(
    'One circuit carries 790 A against 500 A.',
  )
  expect(fillPlaceholders('Ships in {value} weeks, limit {limit}.', { value: 98, limit: 26, unit: 'weeks' })).toBe(
    'Ships in 98 weeks, limit 26 weeks.',
  )
})

test('engine keys become labels with units', () => {
  expect(describeKey('ampacity_a')).toEqual({ label: 'Ampacity', unit: 'A' })
  expect(fmtKeyValue('dv_pct', 0.84)).toBe('ΔV 0.84%')
  expect(fmtKeyValue('cost_delta', 18000)).toBe('Cost Δ +$18,000')
  expect(shortHash('a1b2c3d4e5f60718293a')).toBe('a1b2c3d4e5f6…')
})
