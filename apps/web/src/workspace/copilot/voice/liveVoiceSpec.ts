// Live-session constants only (no `@/firebase` import), so tests can check them without
// bootstrapping the real Firebase app (which throws on the test environment's placeholder API
// key). `liveVoice.ts` imports and re-exports these alongside the actual `startLiveVoice`.
import { Schema, type FunctionDeclaration } from 'firebase/ai'

export const LIVE_MODEL = 'gemini-live-2.5-flash-native-audio'

export const TOOL_DECLARATIONS: FunctionDeclaration[] = [
  {
    name: 'what_if',
    description:
      'Re-check the current revision with a changed load or limit (engine only, not saved). Returns failing checks and the impact chain.',
    parameters: Schema.object({
      properties: {
        param: Schema.enumString({ enum: ['rack_kw', 'liquid_fraction', 'dv_limit_pct', 'tx_loading_cap_pct'] }),
        value: Schema.number(),
      },
    }),
  },
  {
    name: 'explain_finding',
    description: 'Explain one checker finding, e.g. finding_id "R05:FA-01", or by element_id.',
    parameters: Schema.object({
      properties: { finding_id: Schema.string(), element_id: Schema.string() },
      optionalProperties: ['finding_id', 'element_id'],
    }),
  },
  {
    name: 'focus_element',
    description: 'Show an element (e.g. "FA-01", "H-Z2", "CDU-4") on the canvas.',
    parameters: Schema.object({ properties: { element_id: Schema.string() } }),
  },
]

/**
 * Verbatim copy of WS2's LIVE_SYSTEM_INSTRUCTION (services/api/kirchhoff/agents/specs.py; ruling R24).
 * Keep the two in sync: WS2's ledger note and the trust rules (spec §6.5) rely on this wording.
 * Guarded by liveVoice.test.ts, which pastes the same string so drift fails CI even though WS2's
 * file is outside this worktree.
 */
export const LIVE_SYSTEM_INSTRUCTION =
  'You are the Kirchhoff co-pilot in a live voice session about an AI data hall design. Answer with the tools ' +
  'what_if, explain_finding and focus_element. Speak only numbers that a tool returned; never estimate or invent ' +
  'a number. If no tool answers the question, say so briefly.'
