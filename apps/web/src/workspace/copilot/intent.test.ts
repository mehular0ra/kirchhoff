import { parseIntent } from './intent'

// Typed questions about an element reach the same tool a spoken one does, so both give the same engine answer.
test.each([
  ['What is the power of rack R1-01?', 'R1-01'],
  ['tell me the details of rack r1-01', 'R1-01'],
  ['details R1 - 01', 'R1-01'],
  ['describe T-A1', 'T-A1'],
  ['how long is FA-01', 'FA-01'],
  ["what's the rating of UPS-A1", 'UPS-A1'],
  ['how much capacity does CDU-4 have', 'CDU-4'],
  ['which feeds does R2-03 have', 'R2-03'],
])('“%s” asks for the details of %s', (text, element) => {
  expect(parseIntent(text)).toEqual({ tool: 'focus_element', element })
})

test('a spoken id with spaces around the dash is still found', () => {
  expect(parseIntent('show h - z2')).toEqual({ tool: 'focus_element', element: 'H-Z2' })
  expect(parseIntent('why fa - 01')).toEqual({ tool: 'explain_finding', element: 'FA-01', rule: undefined })
})

test('the other tools keep their own phrasing', () => {
  expect(parseIntent('what is wrong with H-Z2')).toEqual({ tool: 'explain_finding', element: 'H-Z2', rule: undefined })
  expect(parseIntent('why FA-01')).toEqual({ tool: 'explain_finding', element: 'FA-01', rule: undefined })
  expect(parseIntent('what if racks go to 200 kW')).toEqual({ tool: 'what_if', param: 'rack_kw', value: 200 })
})

test('a question that names no element is still not understood', () => {
  expect(parseIntent('what is the power')).toBeNull()
  expect(parseIntent('tell me about the weather')).toBeNull()
})
