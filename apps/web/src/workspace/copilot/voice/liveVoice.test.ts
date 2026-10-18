// Guards LIVE_SYSTEM_INSTRUCTION against silent drift from WS2's copy (services/api/kirchhoff/agents/specs.py),
// which lives outside this worktree and cannot be imported directly. This pastes that file's current value;
// if WS2 changes it, this test fails until the two are re-synced (ruling R24).
// Imports the constants-only module, not ./liveVoice: liveVoice.ts pulls in `@/firebase`, which
// eagerly calls getAuth() and throws on this test environment's placeholder API key. This guard
// only needs the constants, so it never touches Firebase bootstrapping.
import { liveSystemInstruction, LIVE_MODEL, LIVE_SYSTEM_INSTRUCTION, TOOL_DECLARATIONS } from './liveVoiceSpec'

const WS2_LIVE_SYSTEM_INSTRUCTION =
  'You are the Kirchhoff co-pilot in a live voice session about an AI data hall design. Answer with the tools ' +
  'what_if, explain_finding and focus_element. Speak only numbers that a tool returned; never estimate or invent ' +
  'a number. If no tool answers the question, say so briefly.'

test('LIVE_SYSTEM_INSTRUCTION matches WS2 specs.py verbatim', () => {
  expect(LIVE_SYSTEM_INSTRUCTION).toBe(WS2_LIVE_SYSTEM_INSTRUCTION)
})

test('LIVE_MODEL is the Gemini Live native-audio model', () => {
  expect(LIVE_MODEL).toBe('gemini-live-2.5-flash-native-audio')
})

test('focus_element is described as the way to ask about a rack or any other element, not only to show it', () => {
  const focus = TOOL_DECLARATIONS.find((d) => d.name === 'focus_element')!
  expect(focus.description).toMatch(/rack/i)
  expect(focus.description).toMatch(/power/i)
  expect(focus.description).toMatch(/details/i)
})

test('the tools say that R05 is a rule id for explain_finding and that DESIGN means the whole design', () => {
  const by = (n: string) => TOOL_DECLARATIONS.find((d) => d.name === n)!.description
  expect(by('explain_finding')).toMatch(/rule id/i)
  expect(by('explain_finding')).toMatch(/R05/)
  expect(by('focus_element')).toMatch(/DESIGN/)
  expect(by('focus_element')).toMatch(/rule id/i)
})

describe('the instruction Gemini is given', () => {
  test('starts with the WS2 instruction verbatim, then says how to use the tools and to answer once', () => {
    const text = liveSystemInstruction()
    expect(text.startsWith(LIVE_SYSTEM_INSTRUCTION)).toBe(true)
    expect(text).toMatch(/rule id such as R05/i)
    expect(text).toMatch(/element_id DESIGN/)
    expect(text).toMatch(/once/i)
    expect(text).toMatch(/never repeat/i)
  })

  test('carries the design facts when there are some, and is unchanged without them', () => {
    expect(liveSystemInstruction('Design: topology 2N; 48 racks.')).toContain('Design facts')
    expect(liveSystemInstruction('Design: topology 2N; 48 racks.')).toContain('48 racks')
    expect(liveSystemInstruction()).not.toContain('Design facts')
  })

  test('the design facts are kept to a size a spoken session can carry', () => {
    const long = 'x'.repeat(10_000)
    expect(liveSystemInstruction(long).length).toBeLessThan(LIVE_SYSTEM_INSTRUCTION.length + 4_000)
  })
})

test('TOOL_DECLARATIONS exposes exactly the three co-pilot tools', () => {
  expect(TOOL_DECLARATIONS.map((d) => d.name)).toEqual(['what_if', 'explain_finding', 'focus_element'])
})
