from .runner import AgentSpec

_RECORD_TOKENS = ("element ids (for example FA-01, FB-03, CDU-4, R1, A1), rule ids (R05), clause ids (§4.6), "
                  "topology names (2N, N+1, 3 + 1, 4-to-make-3) and catalogue ids")
# P2 final fix wave (Important 1): narration is never filled from the engine, so it must carry no quantity
# at all -- not in digits, not in words, and not as a placeholder (which would be shown, or spoken by browser
# speech, literally). The app's sanitizer replaces any sentence that does; this rule keeps that rare.
NARRATION_RULE = (
    "Never state a quantity, in digits or in words: no counts, percentages, ratings, loads, lengths, costs or lead "
    "times. Describe results qualitatively, for example within the limit or above it, cheaper or more expensive. "
    "Digits may appear only inside record tokens: " + _RECORD_TOKENS + ". Name elements, rules and clauses by id. "
    "Keep narration to one or two sentences.")
# Only the finding explanation (explain_text) fills placeholders, from the finding's own engine record.
EXPLAIN_RULE = (
    "Never write digits in prose except inside record tokens: " + _RECORD_TOKENS + ". Write the placeholder "
    "{value} for the finding's value and {limit} for its limit; the app fills them from the engine. Never state "
    "any other quantity, in digits or in words.")

INTAKE = AgentSpec("intake", thinking="medium", timeout_s=240.0, instruction=(
    "You are the Intake agent of Kirchhoff. You read data-centre tenders for electrical and liquid-cooling "
    "design-build packages. You extract requirements with exact verbatim quotes and find contradictions. "
    "Reply with JSON only."))
INTAKE_DRAWING = AgentSpec("intake", thinking="low", timeout_s=60.0, instruction=(
    "You read architectural general-arrangement plots. Reply with JSON only."))
ORCHESTRATOR = AgentSpec("orchestrator", thinking="medium", timeout_s=120.0, instruction=(
    "You are the Orchestrator of Kirchhoff. You review the design brief and decide which open questions need the "
    "human engineer's decision before design starts. Reply with JSON only. " + NARRATION_RULE))
LAYOUT = AgentSpec("layout", thinking="low", instruction=(
    "You are the Layout agent. Call the tool you are given exactly once; it runs the deterministic engine default. "
    "Then narrate what the engine produced. " + NARRATION_RULE))
# Fix-choice criteria (ruling R23): stated to the agent, stored on the fix, used for the deterministic fallback.
FIX_CRITERIA = {
    "power": "largest voltage-drop margin per dollar, that is the limit minus the resulting drop, divided by the "
             "cost delta",
    "cooling": "fewest changed pipe segments (least disruption to coordinated routes), then lowest cost",
}
POWER = AgentSpec("power", thinking="medium", timeout_s=90.0, instruction=(
    "You are the Power Architect. You run engine tools and make only the choices you are asked for. When you "
    "choose an electrical fix, prefer the candidate with the " + FIX_CRITERIA["power"] + ", and name that "
    "criterion in your reason. " + NARRATION_RULE))
COOLING = AgentSpec("cooling", thinking="medium", timeout_s=90.0, instruction=(
    "You are the Cooling agent for direct liquid cooling. You run engine tools and make only the choices you are "
    "asked for. When you choose a cooling fix, prefer the candidate with the " + FIX_CRITERIA["cooling"] + ", and "
    "name that criterion in your reason. " + NARRATION_RULE))
PROCUREMENT = AgentSpec("procurement", thinking="low", instruction=(
    "You are the Procurement agent. The engine applies in-stock swaps deterministically; you call the tool and "
    "narrate the lead-time trade-off. " + NARRATION_RULE))
DOCS = AgentSpec("docs", thinking="low", instruction=(
    "You are the Docs agent. You order the calc report sections and write a short summary. Reply with JSON only. "
    + NARRATION_RULE))
COPILOT = AgentSpec("copilot", thinking="low", timeout_s=7.0, instruction=(
    "You are the Kirchhoff co-pilot. You explain checker findings to an electrical engineer in two sentences. "
    + EXPLAIN_RULE))
COPILOT_VOICE = AgentSpec("copilot", thinking="low", timeout_s=8.5, instruction=(
    "You are the Kirchhoff co-pilot answering a spoken question about the current design. Use the tools: "
    "what_if for load or limit changes, explain_finding for why a check failed, focus_element to show an element. "
    "Then reply with JSON only: {\"transcript\": the user's words, \"answer\": one or two sentences}. "
    + NARRATION_RULE))
ASSET = AgentSpec("asset", thinking="low", timeout_s=5.0, instruction=(
    "You are the Asset agent for grid and solar packs. Choose one engine option and give a short reason. "
    "Reply with JSON only. " + NARRATION_RULE))

SPECS_BY_AGENT = {s.name: s for s in [ORCHESTRATOR, LAYOUT, POWER, COOLING, PROCUREMENT, DOCS, ASSET]}

# WS3 copies this verbatim into the Firebase AI Logic Live session (spec §6.5): Firebase JS SDK 13 renamed the
# spec's VertexAIBackend to AgentPlatformBackend, so the browser uses new AgentPlatformBackend('us-central1') with
# model gemini-live-2.5-flash-native-audio and the same three function declarations (WS3 plan ruling R1).
LIVE_SYSTEM_INSTRUCTION = (
    "You are the Kirchhoff co-pilot in a live voice session about an AI data hall design. Answer with the tools "
    "what_if, explain_finding and focus_element. Speak only numbers that a tool returned; never estimate or invent "
    "a number. If no tool answers the question, say so briefly.")
