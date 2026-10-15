"""One agent call = one small ADK 2.11 graph (spec §6.2: steps stay checkpointable; no session crosses steps)."""
import asyncio
import os
from collections.abc import Callable, Sequence

from .runner import MODEL, THINKING_LEVELS, AgentResult, AgentSpec, Attachment, ToolCall, with_retries


class AdkRunner:
    def __init__(self, model: str = MODEL, mode: str | None = None, app_name: str = "kirchhoff") -> None:
        self.model = model
        # agent mode measured fastest live (94 s against 130 s for workflow, 14 Oct); workflow still
        # selectable via KIRCHHOFF_ADK_MODE.
        self.mode = mode or os.environ.get("KIRCHHOFF_ADK_MODE", "agent")  # "workflow" | "agent"
        self.app_name = app_name

    def run(self, spec: AgentSpec, key: str, message: str, tools: Sequence[Callable] = (),
            attachments: Sequence[Attachment] = ()) -> AgentResult:
        def once() -> AgentResult:
            return asyncio.run(asyncio.wait_for(self._run_async(spec, message, tools, attachments), spec.timeout_s))
        return with_retries(once)

    def _node(self, spec: AgentSpec, tools: Sequence[Callable]):
        from google.adk.agents import LlmAgent
        from google.genai import types

        # instruction=<callable> (an InstructionProvider), not a bare str: ADK's canonical_instruction()
        # only sets bypass_state_injection=True for the callable form. COPILOT's EXPLAIN_RULE (specs.py) has
        # a literal "{value}"/"{limit}" in its instruction text, and COPILOT_VOICE a literal JSON shape in
        # braces -- neither is an ADK session-state ref, but the plain-str path runs them through
        # inject_session_state() regardless and raises KeyError("value" not in session.state).
        agent = LlmAgent(name=spec.name, model=self.model, instruction=lambda _ctx: spec.instruction,
                         tools=list(tools),
                         generate_content_config=types.GenerateContentConfig(
                             thinking_config=types.ThinkingConfig(thinking_level=THINKING_LEVELS[spec.thinking])))
        if self.mode == "agent":
            return agent
        from google.adk.workflow import START, Workflow
        return Workflow(name=f"{spec.name}_step", edges=[(START, agent)])

    def _runner(self, node, sessions):
        # ADK 2.11's Runner accepts either `agent=` or `node=`: both wrap the given root in a new App
        # without an isinstance check (runners.py `_resolve_app`), so `node=` works uniformly for an
        # LlmAgent (agent mode) and a Workflow (workflow mode). Adapted from the brief's agent/node
        # try-except, which is unnecessary with this installed version.
        from google.adk.runners import Runner
        return Runner(app_name=self.app_name, node=node, session_service=sessions)

    async def _run_async(self, spec, message, tools, attachments) -> AgentResult:
        from google.adk.sessions import InMemorySessionService
        from google.genai import types

        sessions = InMemorySessionService()
        runner = self._runner(self._node(spec, tools), sessions)
        session = await sessions.create_session(app_name=self.app_name, user_id="kirchhoff")
        parts = [types.Part.from_bytes(data=a.data, mime_type=a.mime_type) for a in attachments]
        parts.append(types.Part(text=message))
        last_text, calls, args_by_id, t_in, t_out = "", [], {}, 0, 0
        async for ev in runner.run_async(user_id="kirchhoff", session_id=session.id,
                                         new_message=types.Content(role="user", parts=parts)):
            usage = getattr(ev, "usage_metadata", None)
            if usage:
                t_in += usage.prompt_token_count or 0
                t_out += (usage.candidates_token_count or 0) + (getattr(usage, "thoughts_token_count", 0) or 0)
            content = getattr(ev, "content", None)
            texts = []
            for part in (content.parts or []) if content else []:
                if getattr(part, "thought", False):
                    continue
                if part.function_call:
                    fc = part.function_call
                    args_by_id[fc.id or fc.name] = dict(fc.args or {})
                elif part.function_response:
                    fr = part.function_response
                    calls.append(ToolCall(fr.name, args_by_id.get(fr.id or fr.name, {}), fr.response))
                elif part.text:
                    texts.append(part.text)
            if texts:
                last_text = "".join(texts)
        return AgentResult(last_text.strip(), calls, t_in, t_out)
