// Live-session constants only (no `@/firebase` import), so tests can check them without
// bootstrapping the real Firebase app (which throws on the test environment's placeholder API
// key). `liveVoice.ts` imports and re-exports these alongside the actual `startLiveVoice`.
import { Schema, type FunctionDeclaration } from 'firebase/ai'

export const LIVE_MODEL = 'gemini-live-2.5-flash-native-audio'

export const TOOL_DECLARATIONS: FunctionDeclaration[] = [
  {
    name: 'what_if',
    description:
      'Re-check the design with a changed load or limit: the latest revision, or the one the engineer picked (engine only, not saved). Returns the revision, failing checks and the impact chain.',
    parameters: Schema.object({
      properties: {
        param: Schema.enumString({ enum: ['rack_kw', 'liquid_fraction', 'dv_limit_pct', 'tx_loading_cap_pct'] }),
        value: Schema.number(),
      },
    }),
  },
  {
    name: 'explain_finding',
    description:
      'Explain one checker finding, e.g. finding_id "R05:FA-01", or by element_id. A rule id alone, such as "R05" (a check ' +
      'on the design, not an element), explains that rule\'s worst finding: pass it as finding_id.',
    parameters: Schema.object({
      properties: { finding_id: Schema.string(), element_id: Schema.string() },
      optionalProperties: ['finding_id', 'element_id'],
    }),
  },
  {
    name: 'focus_element',
    description:
      'Show an element on the canvas and return its details from the design model: a rack (e.g. "R1-01": power in kW, ' +
      'liquid fraction, feeds), a board or transformer (rating), a feeder (e.g. "FA-01": ends and length), a CDU or pipe ' +
      '(zone, capacity), and the checks on it. Use it for any question about what a rack or other element is. A rule id such ' +
      'as "R05" gives the results of that rule; element_id "DESIGN" answers questions about the whole design (racks, ' +
      'equipment, cooling, checks).',
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

/**
 * Added after WS2's instruction (which stays verbatim above): which tool a rule id, an element id and a question about the
 * whole design go to, and to answer once. Without it the model asked for "R05" looked it up as an element, was told it was
 * not there, and kept re-explaining the same answer.
 */
const LIVE_ADDENDUM =
  'A rule id such as R05 names a check on the design: use explain_finding with it. An element id such as R1-01, FA-01 or ' +
  'CDU-4 is looked up with focus_element; for a question about the whole design use focus_element with element_id DESIGN. ' +
  'After a tool answers, say its answer once, briefly, and then stop and wait for the visitor; never repeat or rephrase an ' +
  'answer unless asked.'

/** The design facts the session starts with are cut to this many characters. */
const MAX_FACTS = 3000

/** What Gemini Live is told at connect: WS2's instruction, the addendum, and (when given) facts about the design from the engine. */
export function liveSystemInstruction(facts?: string): string {
  const base = `${LIVE_SYSTEM_INSTRUCTION} ${LIVE_ADDENDUM}`
  return facts ? `${base} Design facts from the engine (you may state these numbers too): ${facts.slice(0, MAX_FACTS)}` : base
}
