"""Agent runner port. Production: AdkRunner (ADK 2.11) or GenaiRunner; tests: ReplayRunner fixtures."""
import json
import random
import re
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

MODEL = "gemini-3.8-flash"
# Gemini 3 thinking levels. If Vertex rejects "medium" (see test_medium_thinking_level_is_accepted), use "high".
THINKING_LEVELS = {"low": "low", "medium": "medium"}
RETRYABLE_CODES = {429, 500, 502, 503, 504}
# P2 final fix wave (Minor 6): the repair prompt quotes the previous reply. The intake reply is about 6-10 KB with
# `contradictions` last, so the old 4,000-character excerpt cut them off and the repair dropped the §4.2/App. B pair.
REPAIR_EXCERPT_CHARS = 40_000
RETRYABLE_NAMES = {"ResourceExhausted", "ServiceUnavailable", "InternalServerError", "TooManyRequests",
                   "ServerError"}


@dataclass(frozen=True)
class AgentSpec:
    name: str
    instruction: str
    thinking: Literal["low", "medium"] = "low"
    timeout_s: float = 30.0
    # Attempts per call, through with_retries (429/5xx). 1 means a single attempt: voice (issue #36), whose
    # back-off retry could not fit its budget.
    attempts: int = 4


@dataclass(frozen=True)
class Attachment:
    data: bytes
    mime_type: str


@dataclass
class ToolCall:
    name: str
    args: dict
    result: Any


@dataclass
class AgentResult:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0


class AgentRunner(Protocol):
    def run(self, spec: AgentSpec, key: str, message: str, tools: Sequence[Callable] = (),
            attachments: Sequence[Attachment] = ()) -> AgentResult: ...


def fixture_name(key: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", key) + ".json"


class ReplayRunner:
    """Replays recorded model decisions. Tool calls are executed for real against the offered tools."""

    def __init__(self, replies: dict[str, dict] | None = None, fixtures_dir: Path | None = None) -> None:
        self.replies = dict(replies or {})
        self.fixtures_dir = fixtures_dir
        self.calls: list[str] = []
        self._lock = threading.Lock()

    def _reply(self, k: str) -> dict:
        if k in self.replies:
            return self.replies[k]
        if self.fixtures_dir and (p := self.fixtures_dir / fixture_name(k)).exists():
            return json.loads(p.read_text(encoding="utf-8"))
        raise KeyError(f"no replay fixture for {k}")

    def run(self, spec, key, message, tools=(), attachments=()) -> AgentResult:
        k = f"{spec.name}:{key}"
        reply = self._reply(k)
        with self._lock:
            self.calls.append(k)
        if reply.get("raise"):
            raise RuntimeError(reply["raise"])
        by_name = {t.__name__: t for t in tools}
        calls = []
        for c in reply.get("tool_calls", []):
            args = c.get("args", {})
            calls.append(ToolCall(c["name"], args, by_name[c["name"]](**args)))
        text = reply.get("text", "")
        usage = reply.get("usage", {})
        return AgentResult(text if isinstance(text, str) else json.dumps(text), calls,
                           int(usage.get("in", 0)), int(usage.get("out", 0)))


class RecordingRunner:
    """Wraps a real runner and writes ReplayRunner fixtures (set KIRCHHOFF_RECORD_DIR in a live run)."""

    def __init__(self, inner: AgentRunner, out_dir: Path) -> None:
        self.inner, self.out_dir = inner, Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def run(self, spec, key, message, tools=(), attachments=()) -> AgentResult:
        res = self.inner.run(spec, key, message, tools, attachments)
        data = {"tool_calls": [{"name": c.name, "args": c.args} for c in res.tool_calls], "text": res.text,
                "usage": {"in": res.tokens_in, "out": res.tokens_out}}
        (self.out_dir / fixture_name(f"{spec.name}:{key}")).write_text(json.dumps(data, indent=2, ensure_ascii=False),
                                                                      encoding="utf-8")
        return res


def extract_json(text: str) -> Any:
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    starts = [i for i in (t.find("{"), t.find("[")) if i >= 0]
    if not starts:
        raise ValueError("no JSON object in reply")
    start = min(starts)
    end = t.rfind("}" if t[start] == "{" else "]")
    try:
        return json.loads(t[start:end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in reply: {exc}") from exc


T = TypeVar("T", bound=BaseModel)


def run_json(runner: AgentRunner, spec: AgentSpec, key: str, message: str, schema: type[T],
             tools: Sequence[Callable] = (), attachments: Sequence[Attachment] = (),
             repair: bool = True) -> tuple[T, AgentResult]:
    """Structured output with one repair attempt (spec §11). Raises ValueError if the repair also fails.
    `repair=False` makes it exactly one runner call: a bad reply raises ValueError at once (voice, issue #36)."""
    res = runner.run(spec, key, message, tools, attachments)
    try:
        return schema.model_validate(extract_json(res.text)), res
    except (ValueError, ValidationError) as exc:
        if not repair:
            raise ValueError(str(exc)[:400]) from exc
        prompt = (f"Your previous reply was not valid JSON for this schema:\n"
                  f"{json.dumps(schema.model_json_schema())}\nError: {str(exc)[:400]}\n"
                  f"Previous reply:\n{res.text[:REPAIR_EXCERPT_CHARS]}\nReply with only the corrected JSON.")
        fixed = runner.run(spec, f"{key}#repair", prompt)
        merged = AgentResult(fixed.text, res.tool_calls + fixed.tool_calls, res.tokens_in + fixed.tokens_in,
                             res.tokens_out + fixed.tokens_out)
        try:
            return schema.model_validate(extract_json(fixed.text)), merged
        except ValidationError as exc2:
            raise ValueError(str(exc2)) from exc2


def is_retryable(exc: BaseException) -> bool:
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if isinstance(code, int) and code in RETRYABLE_CODES:
        return True
    return type(exc).__name__ in RETRYABLE_NAMES


def with_retries(fn: Callable[[], Any], attempts: int = 4, base_s: float = 1.0,
                 sleep: Callable[[float], None] = time.sleep) -> Any:
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:
            if i == attempts - 1 or not is_retryable(exc):
                raise
            sleep(base_s * 2 ** i + random.uniform(0, base_s / 2))
    raise AssertionError("unreachable")
