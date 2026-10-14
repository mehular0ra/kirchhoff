"""Steps (spec v4.1 §6.2): events stream; start and commit are transactions guarded by lease.attempt."""
import functools
import json
import logging
import threading
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel

from kirchhoff.agents.runner import AgentResult, AgentSpec, Attachment, run_json
from kirchhoff.agents.trust import allowed_ids_for, sanitize
from kirchhoff.contracts import DesignModel, LedgerEntry, RunEvent, StepRecord
from kirchhoff.store.events import EventWriter
from kirchhoff.store.validate import firestore_safe_problems, json_size_bytes

from .deps import Deps
from .leases import holds_lease, run_path
from .outputs import load_outputs, pack_outputs

log = logging.getLogger("kirchhoff.runs")
PAYLOAD_MAX = 9_000  # event docs stay < 10 KB (spec §11)
TITLE_MAX = 200  # M-1: title/detail are clipped so the *whole* serialized event, not just the payload,
DETAIL_MAX = 500  # stays comfortably under the EventWriter's MAX_EVENT_BYTES (10,000) hard cap.
EVENT_BUDGET = 9_200  # payload truncation budgets against this, leaving headroom for title/detail/fixed fields
TXN_DOC_LIMIT = 400  # Firestore transaction write limit is 500
AGENT_LABEL = {"intake": "Intake", "orchestrator": "Orchestrator", "layout": "Layout", "power": "Power",
               "cooling": "Cooling", "procurement": "Procurement", "checker": "Checker", "docs": "Docs",
               "copilot": "Co-pilot", "asset": "Asset agent", "system": "Kirchhoff"}


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit - 1] + "…"


class LeaseLost(Exception):
    """Another worker holds the run lease; stop without writing."""


class ParkAtGate(Exception):
    def __init__(self, gate: str, message: str = "") -> None:
        super().__init__(message)
        self.gate, self.message = gate, message


@dataclass
class StepOutput:
    data: dict
    docs: list[tuple[str, dict]] = field(default_factory=list)


@dataclass
class PhaseOutcome:
    gate: Literal["plan", "option", "review"] | None
    run_patch: dict = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    forced: bool = False
    message: str = ""


class PhaseContext:
    def __init__(self, deps: Deps, uid: str, rid: str, phase: str, attempt: int, events: EventWriter,
                 lease_lost: threading.Event | None = None, prior_active_s: float = 0.0) -> None:
        self.deps, self.uid, self.rid, self.phase, self.attempt = deps, uid, rid, phase, attempt
        self.events = events
        self.lease_lost = lease_lost or threading.Event()
        self.prior_active_s = prior_active_s
        self.started = deps.clock()
        self.metrics: dict[str, float] = {}
        self._mlock = threading.Lock()

    @property
    def run_path(self) -> str:
        return run_path(self.uid, self.rid)

    @property
    def ws_path(self) -> str:
        return f"workspaces/{self.uid}"

    def run(self) -> dict:
        return self.deps.store.get_doc(self.run_path) or {}

    def scenario(self):
        return self.deps.scenario()

    def erp(self):
        return self.deps.erp()

    def active_s(self) -> float:
        return self.prior_active_s + (self.deps.clock() - self.started)

    def outputs(self, step_id: str) -> dict:
        data = load_outputs(self.deps.store, self.deps.blobs, self.run_path, step_id)
        if data is None:
            raise KeyError(f"no committed outputs for {step_id}")
        return data

    def emit(self, step: str, agent: str, kind: str, title: str, detail: str = "",
             payload: dict[str, Any] | None = None) -> RunEvent:
        if self.lease_lost.is_set():  # another worker owns the run: drop pending events, write nothing more
            self.events.fence()
            raise LeaseLost(step)
        # M-1: title/detail can themselves be arbitrarily long (an LLM narration, a ledger entry's full
        # text); clip them so the whole serialized event, not just the payload, stays under the cap.
        title = _clip(title or "", TITLE_MAX)
        detail = _clip(detail or "", DETAIL_MAX)
        payload = json.loads(json.dumps(payload or {}, default=str))  # engine tuples -> lists, numpy scalars -> str
        overhead = json_size_bytes({"step": step, "agent": agent, "kind": kind, "title": title, "detail": detail})
        budget = max(0, min(PAYLOAD_MAX, EVENT_BUDGET - overhead))
        if json_size_bytes(payload) > budget:
            payload = {"truncated": True, "keys": sorted(payload)[:50]}
        # The P0 writer validates Firestore safety (ValueError) and assigns seq; `step=` tags parallel steps.
        return self.events.emit(agent, kind, title, detail, payload, step=step)

    def narrate(self, step: str, agent: str, text: str, allowed: Iterable[str], step_title: str,
                template: str | None = None) -> str:
        clean = sanitize(text, allowed, template or f"{AGENT_LABEL.get(agent, agent)} completed {step_title}.")
        self.emit(step, agent, "message", clean)
        return clean

    def ledger(self, step: str, agent: str, kind: str, text: str) -> LedgerEntry:
        entry = LedgerEntry(kind=kind, agent=agent, text=text)
        self.emit(step, agent, "ledger", text, payload={"entry": entry.model_dump()})
        return entry

    def tool(self, step: str, agent: str, fn: Callable[..., dict]) -> Callable[..., dict]:
        @functools.wraps(fn)
        def wrapped(**kwargs):
            self.emit(step, agent, "tool_call", fn.__name__, payload={"tool": fn.__name__, "args": kwargs})
            summary = fn(**kwargs)
            self.emit(step, agent, "tool_result", f"{fn.__name__} done",
                      payload={"tool": fn.__name__, "summary": summary})
            return summary
        return wrapped

    def add_tokens(self, *results: AgentResult | None) -> None:
        with self._mlock:
            for r in results:
                if r is not None:
                    self.metrics["tokens_in"] = self.metrics.get("tokens_in", 0.0) + r.tokens_in
                    self.metrics["tokens_out"] = self.metrics.get("tokens_out", 0.0) + r.tokens_out

    def _unavailable(self, spec: AgentSpec, step: str, exc: Exception) -> None:
        log.warning("agent %s failed at %s: %r", spec.name, step, exc)
        self.emit(step, spec.name, "status", f"{AGENT_LABEL.get(spec.name, spec.name)} agent unavailable; "
                  "engine default used", detail=type(exc).__name__)

    def agent(self, spec: AgentSpec, step: str, message: str, tools: Sequence[Callable] = (),
              attachments: Sequence[Attachment] = (), key: str | None = None) -> AgentResult | None:
        try:
            res = self.deps.runner.run(spec, key or step, message, tools, attachments)
        except Exception as exc:
            self._unavailable(spec, step, exc)
            return None
        self.add_tokens(res)
        return res

    def agent_json(self, spec: AgentSpec, step: str, message: str, schema: type[BaseModel],
                   tools: Sequence[Callable] = (), attachments: Sequence[Attachment] = (),
                   key: str | None = None) -> BaseModel | None:
        try:
            parsed, res = run_json(self.deps.runner, spec, key or step, message, schema, tools, attachments)
        except Exception as exc:
            self._unavailable(spec, step, exc)
            return None
        self.add_tokens(res)
        return parsed

    def allowed(self, *models: DesignModel | None, extra: Iterable[str] = ()) -> set[str]:
        return allowed_ids_for(*models, extra=[*extra, *self.erp().ids()])


def _check_docs(docs: list[tuple[str, dict]]) -> None:
    for path, doc in docs:
        if problems := firestore_safe_problems(doc):
            raise ValueError(f"step doc {path} is not Firestore-safe: {problems[:3]}")


def _fence_and_lose(ctx: PhaseContext, step_id: str) -> None:
    ctx.lease_lost.set()
    ctx.events.fence()
    raise LeaseLost(step_id)


def run_step(ctx: PhaseContext, step_id: str, fn: Callable[[], StepOutput]) -> dict:
    if ctx.lease_lost.is_set():  # I-1(c)/M-6: fence here too, not only on the transactional paths below
        ctx.events.fence()
        raise LeaseLost(step_id)
    deps, store = ctx.deps, ctx.deps.store
    step_path = f"{ctx.run_path}/steps/{step_id}"
    started = deps.clock()
    state: dict[str, bool] = {}

    def begin(snap: dict[str, dict | None]):
        state.clear()  # Firestore may retry the transaction function
        run, step = snap[ctx.run_path], snap[step_path]
        if not holds_lease(run, deps.owner, ctx.attempt):
            state["lost"] = True
            return []
        if step and step.get("status") == "done":
            state["done"] = True
            return []
        rec = StepRecord(id=step_id, phase=ctx.phase, status="running", attempt=ctx.attempt, started_at=started)
        return [(step_path, rec.model_dump())]

    store.transact([ctx.run_path, step_path], begin)
    if state.get("lost"):
        _fence_and_lose(ctx, step_id)
    if state.get("done"):
        return ctx.outputs(step_id)

    # M-3: everything from here through the commit transaction is one failure domain. A non-JSON output
    # reaching pack_outputs, a flush error, or a commit-transaction error must all mark the step failed
    # (while the lease is still held) and re-raise, not leave it stuck "running" forever.
    try:
        out = fn()
        _check_docs(out.docs)
        docs = list(out.docs)
        if len(docs) > TXN_DOC_LIMIT:
            # M-4: no unleased bulk pre-write path. Oversized steps fail loudly, before anything is
            # written, instead of batch-writing part of the docs outside the lease-checked transaction.
            raise ValueError(f"step {step_id} returned {len(docs)} docs; the transactional limit is "
                             f"{TXN_DOC_LIMIT}")
        if ctx.lease_lost.is_set():  # I-1(b): a concurrent heartbeat already saw another owner take over
            raise LeaseLost(step_id)
        ctx.events.flush()
        out_path, out_doc = pack_outputs(deps.blobs, ctx.run_path, step_id, out.data)
        done = StepRecord(id=step_id, phase=ctx.phase, status="done", attempt=ctx.attempt, outputs_ref=out_path,
                          started_at=started, finished_at=deps.clock())

        def commit(snap: dict[str, dict | None]):
            if not holds_lease(snap[ctx.run_path], deps.owner, ctx.attempt):
                return []
            return [*docs, (out_path, out_doc), (step_path, done.model_dump())]

        wrote = store.transact([ctx.run_path], commit)
    except LeaseLost:
        _fence_and_lose(ctx, step_id)
    except ParkAtGate:
        raise
    except Exception:
        failed = StepRecord(id=step_id, phase=ctx.phase, status="failed", attempt=ctx.attempt, started_at=started,
                            finished_at=deps.clock())
        wrote_failed = store.transact([ctx.run_path], lambda snap: [(step_path, failed.model_dump())]
                                      if holds_lease(snap[ctx.run_path], deps.owner, ctx.attempt) else [])
        if not wrote_failed:
            # I-1(c)/M-6: nobody held the lease to mark the step failed either; this is a lease loss,
            # not a step failure, so fence and surface it as LeaseLost instead of the original exception.
            _fence_and_lose(ctx, step_id)
        raise

    if not wrote:
        _fence_and_lose(ctx, step_id)
    return json.loads(json.dumps(out.data))
