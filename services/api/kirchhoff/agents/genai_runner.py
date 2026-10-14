"""google-genai runner: audio input for /api/voice and the fallback agent backend (spec §18)."""
import os
import threading
from collections.abc import Callable, Sequence

from .runner import MODEL, THINKING_LEVELS, AgentResult, AgentSpec, Attachment, ToolCall, with_retries


class GenaiRunner:
    def __init__(self, model: str = MODEL, location: str | None = None) -> None:
        self.model, self.location = model, location
        self._client = None
        self._lock = threading.Lock()

    def _get(self):
        with self._lock:
            if self._client is None:
                from google import genai
                self._client = genai.Client(
                    vertexai=True, project=os.environ.get("GOOGLE_CLOUD_PROJECT", "ordinal-mep"),
                    location=self.location or os.environ.get("GOOGLE_CLOUD_LOCATION", "global"))
            return self._client

    def run(self, spec: AgentSpec, key: str, message: str, tools: Sequence[Callable] = (),
            attachments: Sequence[Attachment] = ()) -> AgentResult:
        from google.genai import types

        parts = [types.Part.from_bytes(data=a.data, mime_type=a.mime_type) for a in attachments]
        parts.append(types.Part(text=message))
        config = types.GenerateContentConfig(
            system_instruction=spec.instruction, tools=list(tools) or None,
            thinking_config=types.ThinkingConfig(thinking_level=THINKING_LEVELS[spec.thinking]),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(maximum_remote_calls=8),
            http_options=types.HttpOptions(timeout=int(spec.timeout_s * 1000)))
        resp = with_retries(lambda: self._get().models.generate_content(
            model=self.model, contents=[types.Content(role="user", parts=parts)], config=config))
        calls, pending = [], {}
        for content in resp.automatic_function_calling_history or []:
            for part in content.parts or []:
                if part.function_call:
                    pending[part.function_call.name] = dict(part.function_call.args or {})
                if part.function_response:
                    fr = part.function_response
                    calls.append(ToolCall(fr.name, pending.get(fr.name, {}), fr.response))
        text = ""
        if resp.candidates and resp.candidates[0].content:
            text = "".join(p.text for p in resp.candidates[0].content.parts or []
                           if p.text and not getattr(p, "thought", False))
        u = resp.usage_metadata
        return AgentResult(text.strip(), calls, (u.prompt_token_count or 0) if u else 0,
                           (u.candidates_token_count or 0) if u else 0)
