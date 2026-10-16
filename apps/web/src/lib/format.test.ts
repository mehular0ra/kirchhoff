import {
  DEMO_AS_OF,
  demoClockLabel,
  demoNowMs,
  describeKey,
  fillPlaceholders,
  fmtElapsed,
  fmtInput,
  fmtKeyValue,
  fmtQty,
  fmtRelative,
  fmtTs,
  fmtUsd,
  isCountKey,
  isCountRule,
  shortHash,
  tidyPlurals,
  tidyTokens,
} from './format'

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

test('I2: WS2 tool_result summaries render arrays and dicts as counts or short lists, never [object Object]', () => {
  // Shapes from services/api/kirchhoff/runs/phase{1,2,3}.py
  expect(fmtKeyValue('options', [{ id: '2N' }, { id: 'DR' }, { id: 'N+1' }])).toBe('3 options')
  expect(fmtKeyValue('options', { '2N': { pass: 3, fail: 0 }, DR: { pass: 2, fail: 1 } })).toBe('2 options')
  expect(fmtKeyValue('pipes', { 'H-Z1': 'pipe_high', 'H-Z2': 'pipe_low' })).toBe('2 pipes')
  expect(fmtKeyValue('clashes', [{ a: 'H-Z2', b: 'FB-03' }])).toBe('1 clash')
  expect(fmtKeyValue('candidates', [])).toBe('0 candidates')
  expect(fmtKeyValue('finding_id', 'R05:FA-01')).toBe('Finding R05:FA-01')
  expect(fmtKeyValue('ok', true)).toBe('OK ✓')
  expect(fmtKeyValue('ok', false)).toBe('OK ✗')
  expect(fmtKeyValue('fail_ids', ['R05:FA-01', 'R11:H-Z2'])).toBe('Fail ids R05:FA-01, R11:H-Z2')
  expect(fmtKeyValue('changed', ['a', 'b', 'c', 'd', 'e', 'f'])).toBe('Changed a, b, c, d +2 more')
  expect(fmtKeyValue('reason', null)).toBe('Reason —')
  for (const v of [[{}], { a: {} }, [[1]], { x: [1, 2] }]) expect(fmtKeyValue('thing', v)).not.toContain('[object')
})

test('I3: delta keys get engineering labels (ΔV, Δp) and units', () => {
  expect(fmtKeyValue('dv_limit_pct', 2)).toBe('ΔV limit 2%')
  expect(fmtKeyValue('index_dp_kpa', 67.036)).toBe('Index-circuit Δp 67.04 kPa')
  expect(fmtKeyValue('added_pipe_m', -4)).toBe('Added pipe -4 m')
  expect(fmtKeyValue('rating_a', 2500)).toBe('Rating 2,500 A')
  expect(fmtKeyValue('cost_delta', -910)).toBe('Cost Δ -$910')
})

test('counts read number first, singular for one (never "Crossings 0" or "Changed pipes 1")', () => {
  expect(fmtKeyValue('changed_pipes', 1)).toBe('1 changed pipe')
  expect(fmtKeyValue('changed_pipes', 2)).toBe('2 changed pipes')
  expect(fmtKeyValue('crossings', 0)).toBe('0 crossings')
  expect(fmtKeyValue('crossings', 1)).toBe('1 crossing')
  expect(fmtKeyValue('lines', 12)).toBe('12 lines')
  expect(fmtKeyValue('lead_time_weeks', 1)).toBe('Lead time 1 week') // a duration, not a count
  expect([isCountKey('crossings'), isCountKey('changed_pipes'), isCountKey('lead_time_weeks'), isCountKey('count')]).toEqual([true, true, false, false])
})

test('backlog [7]: asset-pack keys read as engineers write them', () => {
  expect(describeKey('dc_kwp')).toEqual({ label: 'DC capacity', unit: 'kWp' })
  expect(describeKey('dc_ac')).toEqual({ label: 'DC/AC ratio' })
  expect(describeKey('n1_current_a')).toEqual({ label: 'N-1 current', unit: 'A' })
  expect(describeKey('voc_max_v')).toEqual({ label: 'Voc max', unit: 'V' })
  expect(describeKey('annual_mwh')).toEqual({ label: 'Annual energy', unit: 'MWh' })
})

test('M15: a formula input reads as label + value + unit', () => {
  expect(fmtInput('i_a', 1546.4347)).toEqual({ label: 'Current I', value: '1,546.43 A' })
  expect(fmtInput('feeder_length_m', 82)).toEqual({ label: 'Feeder length', value: '82 m' })
  expect(fmtInput('busway', 'A-01')).toEqual({ label: 'Busway', value: 'A-01' })
  expect(fmtInput('points', [1.2, 2.4])).toEqual({ label: 'Points', value: '1.2, 2.4' })
  expect(fmtInput('extra', { a: 1 }).value).not.toContain('[object')
})

test('D2: the demo clock is fixed at 16 Oct 2026, 12:00 IST, unless the demo world carries its own as_of', () => {
  expect(fmtTs(DEMO_AS_OF)).toBe('16 Oct 2026, 12:00')
  expect(demoNowMs()).toBe(DEMO_AS_OF * 1000)
  expect(demoNowMs({ as_of: 1792218600 })).toBe(1792218600 * 1000)
  expect(demoClockLabel()).toBe('Demo world as of 16 Oct 2026, 12:00 IST')
})

test('D2: relative times read against the demo clock and never run into the future', () => {
  const now = demoNowMs()
  expect(fmtRelative(DEMO_AS_OF - 3 * 3600, now)).toBe('3 hours ago')
  expect(fmtRelative(DEMO_AS_OF - 86400, now)).toBe('yesterday')
  // a timestamp after "now" is shown as its date, never "in 2 hours"
  expect(fmtRelative(DEMO_AS_OF + 2 * 3600, now)).toBe('16 Oct 2026, 14:00')
  expect(fmtRelative(DEMO_AS_OF + 30, now)).toBe('now')
})

test('N6: a timestamp that rounds to 24 hours ago reads "yesterday", the same word the day bucket gives the same moment', () => {
  const now = demoNowMs()
  // 23h59m30s ago rounds to 24h in the hour bucket; it must not say "24 hours ago" while a timestamp
  // one tick later (exactly 24h, handled by the day bucket) says "yesterday" for what is effectively the same instant.
  expect(fmtRelative(DEMO_AS_OF - (86400 - 60), now)).toBe('yesterday')
  expect(fmtRelative(DEMO_AS_OF - 86400, now)).toBe('yesterday')
  // well inside the hour bucket, still reads in hours
  expect(fmtRelative(DEMO_AS_OF - 23 * 3600, now)).toBe('23 hours ago')
})

test('D2: "(1 lines)" from the demo-world generator reads "(1 line)" on display', () => {
  expect(tidyPlurals('submitted PR-2026-0148 to the ERP sandbox (1 lines)')).toBe('submitted PR-2026-0148 to the ERP sandbox (1 line)')
  expect(tidyPlurals('submitted PR-2026-0146 to the ERP sandbox (2 lines)')).toBe('submitted PR-2026-0146 to the ERP sandbox (2 lines)')
  expect(tidyPlurals('(11 lines) and 1 PRs')).toBe('(11 lines) and 1 PR')
})

test('D9: a count of one takes the singular unit', () => {
  expect(fmtQty(1, 'crossings')).toBe('1 crossing')
  expect(fmtQty(2, 'crossings')).toBe('2 crossings')
  expect(fmtQty(1, 'lines')).toBe('1 line')
  expect(fmtQty(-1, 'pipes')).toBe('-1 pipe')
  expect(fmtQty(1, '%')).toBe('1%')
})

test('D9: the R11 location inputs carry metres; tier ids read as words', () => {
  expect(fmtInput('at_x', 28)).toEqual({ label: 'At x', value: '28 m' })
  expect(fmtInput('at_z', 3.8)).toEqual({ label: 'At z', value: '3.8 m' })
  expect(tidyTokens('Drop H-Z2 to pipe_low where it crosses FB-03')).toBe('Drop H-Z2 to the low pipe tier where it crosses FB-03')
  expect(tidyTokens('moved to pipe_high')).toBe('moved to the high pipe tier')
})

test('D9: count-type rules are recognised by their unit or a zero limit', () => {
  expect(isCountRule('crossings', 0)).toBe(true)
  expect(isCountRule('lines', 0)).toBe(true)
  expect(isCountRule(null, 0)).toBe(true)
  expect(isCountRule('%', 2)).toBe(false)
  expect(isCountRule('A', 1600)).toBe(false)
})
