// Guards LIVE_SYSTEM_INSTRUCTION against silent drift from WS2's copy (services/api/kirchhoff/agents/specs.py),
// which lives outside this worktree and cannot be imported directly. This pastes that file's current value;
// if WS2 changes it, this test fails until the two are re-synced (ruling R24).
// Imports the constants-only module, not ./liveVoice: liveVoice.ts pulls in `@/firebase`, which
// eagerly calls getAuth() and throws on this test environment's placeholder API key. This guard
// only needs the constants, so it never touches Firebase bootstrapping.
import { LIVE_MODEL, LIVE_SYSTEM_INSTRUCTION, TOOL_DECLARATIONS } from './liveVoiceSpec'

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

test('TOOL_DECLARATIONS exposes exactly the three co-pilot tools', () => {
  expect(TOOL_DECLARATIONS.map((d) => d.name)).toEqual(['what_if', 'explain_finding', 'focus_element'])
})
