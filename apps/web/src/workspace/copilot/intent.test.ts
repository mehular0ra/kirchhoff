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

test.each([
  ['explain R05', 'R05'],
  ['why did r05 fail', 'R05'],
  ['Yeah, can you explain me about r05?', 'R05'],
  ['what is wrong with R11', 'R11'],
])('“%s” explains the rule %s', (text, rule) => {
  expect(parseIntent(text)).toEqual({ tool: 'explain_finding', element: '', rule })
})

test('a rule id wins over words like "the design" or "summary": the question is about that rule', () => {
  expect(parseIntent('why does R05 fail in the design')).toEqual({ tool: 'explain_finding', element: '', rule: 'R05' })
  expect(parseIntent('what is the summary of R05')).toEqual({ tool: 'focus_element', element: 'R05' })
})

test('"show R05", "rule R05" and a spoken "R 05" reach the rule too', () => {
  expect(parseIntent('show R05')).toEqual({ tool: 'focus_element', element: 'R05' })
  expect(parseIntent('rule R05')).toEqual({ tool: 'focus_element', element: 'R05' })
  expect(parseIntent('what is R 05')).toEqual({ tool: 'focus_element', element: 'R05' })
  expect(parseIntent('why did R 04 b fail')).toEqual({ tool: 'explain_finding', element: '', rule: 'R04b' })
})

test('a rule id with a "what is" question is looked up as a rule', () => {
  expect(parseIntent('what is R05')).toEqual({ tool: 'focus_element', element: 'R05' })
})

test.each(['give me an overview', 'what is in the whole design', 'explain the entire workflow of this hall', 'summarise everything'])('“%s” asks for the design overview', (text) => {
  expect(parseIntent(text)).toEqual({ tool: 'focus_element', element: 'DESIGN' })
})

test('a question that names no element is still not understood', () => {
  expect(parseIntent('what is the power')).toBeNull()
  expect(parseIntent('tell me about the weather')).toBeNull()
})
