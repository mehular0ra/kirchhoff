"""Phase workers (spec §6.2): lease + heartbeat, steps, gates, Ask/Auto, resume, 24 h gate expiry."""
import importlib
import logging
import threading
from collections.abc import Callable

from kirchhoff.contracts import StepRecord
from kirchhoff.store.events import EventWriter

from .deps import Deps
from .events import next_seq
from .leases import acquire_lease, heartbeat, holds_lease, lease_is_live, release_lease, run_path
from .steps import LeaseLost, ParkAtGate, PhaseContext, PhaseOutcome, StepOutput, run_step

log = logging.getLogger("kirchhoff.runs")
GATE_TTL_S = 86400
NEXT_PHASE = {"p1": "p2", "p2": "p3", "p3": "p4", "p4": None}
PHASE_BEFORE_GATE = {"plan": "p1", "option": "p2", "review": "p3"}
AUTO_GATES = {"plan", "option"}
ADDITIVE_METRICS = {"tokens_in", "tokens_out"}
GATE_TITLES = {"plan": "Plan ready for approval", "option": "Options ready for selection",
               "review": "Revision ready for review"}
AUTO_TITLES = {"plan": "Plan approved automatically (Auto mode)",
               "option": "Option chosen automatically (Auto mode)"}
# Controller ruling (Task 8 concurrency reviews): if the heartbeat thread cannot confirm, within this
# many seconds, that it still holds the lease (either because heartbeat() explicitly says it was lost,
# or because Firestore heartbeats keep failing and we simply can't tell any more), the worker must stop
# trusting its own lease and self-fence rather than keep committing on faith.
HEARTBEAT_STALE_S = 45.0


class LeaseBusy(Exception):
    """The run is held by a live worker."""


class WrongState(Exception):
    """The run is not parked at the requested gate."""


class GateExpired(Exception):
    """The run waited at its gate for more than 24 h."""


def phase_fn(deps: Deps, phase: str) -> Callable[[PhaseContext], PhaseOutcome]:
    if deps.phases is not None:
        return deps.phases[phase]
    module = importlib.import_module(f"kirchhoff.runs.phase{phase[1]}")  # imported per phase, on demand
    return getattr(module, f"run_{phase}")


def start_phase(deps: Deps, uid: str, rid: str, phase: str, run_patch: dict | None = None,
               expect: Callable[[dict], bool] | None = None) -> int:
    patch = {**(run_patch or {}), "status": "running", "phase": phase, "gate": None}
    attempt = acquire_lease(deps.store, uid, rid, deps.owner, deps.clock(), patch, expect)
    if attempt is None:
        raise LeaseBusy(rid)
    deps.spawn(lambda: _worker(deps, uid, rid, phase, attempt))
    return attempt


def _gate_expired(run: dict, gate: str, now: float) -> bool:
    entered = float((run.get("metrics") or {}).get("gate_entered_at", now))
    return now - entered > GATE_TTL_S


def _expire(deps: Deps, uid: str, rid: str) -> bool:
    """Marks an `at_gate` run expired. Minor 1/4 (fix round 1): the write is itself transactional and
    conditional -- it only lands if the run is still actually `at_gate` AND nobody holds its lease --
    so a concurrently-resumed run (a worker already claimed it, or another caller already expired or
    advanced it) is never clobbered back to "expired" out from under its new holder. Also sets
    `finished_at` and, since no worker is running at this point (nothing to race with), emits a
    `status` event recording the expiry; a failure to emit that event is logged and swallowed, not
    allowed to undo (or hide) the expiry itself."""
    rp = run_path(uid, rid)
    now = deps.clock()

    def fn(snap: dict[str, dict | None]):
        run = snap[rp]
        if run is None or run.get("status") != "at_gate" or (run.get("lease") or {}).get("owner"):
            return []
        return [(rp, {**run, "status": "expired", "gate": None, "finished_at": now})]

    wrote = deps.store.transact([rp], fn)
    if not wrote:
        return False
    new_run = wrote[0][1]
    attempt = int((new_run.get("lease") or {}).get("attempt") or 1)
    try:
        w = EventWriter(deps.store, rp, phase=new_run.get("phase") or "p1", step="gate.expired", attempt=attempt,
                        start_seq=next_seq(deps.store, rp, attempt), flush_interval_s=0)
        w.emit("system", "status", "The run's gate wait exceeded 24 h; the run has expired.", step="gate.expired")
        w.close()
    except Exception:
        log.exception("could not record the gate-expiry event for %s/%s", uid, rid)
    return True


def ensure_gate(deps: Deps, uid: str, rid: str, gate: str, _retried: bool = False) -> dict:
    run = deps.store.get_doc(run_path(uid, rid))
    if run is None:
        raise KeyError(rid)
    if run.get("status") != "at_gate" or run.get("gate") != gate:
        raise WrongState(gate)
    if not _gate_expired(run, gate, deps.clock()):
        return run
    if _expire(deps, uid, rid):
        raise GateExpired(gate)
    if _retried:
        raise GateExpired(gate)  # pathological: still can't land the write; report expired anyway
    # Minor 1/4 (fix round 1, E2): the expiry write didn't land because the run already moved on --
    # e.g. a concurrent resume_from_gate's acquire_lease committed first and now legitimately holds the
    # lease. Re-reading and re-running the same checks (bounded to one retry) reports the precise,
    # CURRENT reason (almost always WrongState, since the run is "running" again) instead of a stale
    # "expired" verdict for a run a worker has already taken over.
    return ensure_gate(deps, uid, rid, gate, _retried=True)


def resume_from_gate(deps: Deps, uid: str, rid: str, gate: str, run_patch: dict | None = None) -> int:
    run = ensure_gate(deps, uid, rid, gate)
    now = deps.clock()
    metrics = dict(run.get("metrics") or {})
    entered = float(metrics.pop("gate_entered_at", now))
    metrics["gate_wait_s"] = float(metrics.get("gate_wait_s", 0.0)) + (now - entered)

    def expect(current: dict) -> bool:
        # Minor 1 (fix round 1): re-checked INSIDE the acquire_lease transaction, closing the gap
        # between ensure_gate's own read above and this claim (E1/E2) -- if the run moved on (another
        # caller already resumed/expired it) between the two, this aborts with no write at all.
        return (current.get("status") == "at_gate" and current.get("gate") == gate
                and not _gate_expired(current, gate, now))

    try:
        return start_phase(deps, uid, rid, NEXT_PHASE[PHASE_BEFORE_GATE[gate]],
                           {**(run_patch or {}), "metrics": metrics}, expect)
    except LeaseBusy:
        # The transactional claim lost the race (E1/E2): re-run ensure_gate's own checks so the precise,
        # *current* reason (WrongState or GateExpired) surfaces instead of a generic LeaseBusy.
        ensure_gate(deps, uid, rid, gate)
        raise  # ensure_gate didn't raise either: a genuine concurrent resume_from_gate call won the race


def resume_run(deps: Deps, uid: str, rid: str) -> bool:
    run = deps.store.get_doc(run_path(uid, rid))
    if run is None:
        raise KeyError(rid)
    now = deps.clock()
    if run.get("status") == "at_gate":
        # Minor 4 (fix round 1): give an abandoned gate the same 24 h visibility resume_from_gate/
        # ensure_gate already give it -- a run nobody ever came back to must not sit "at_gate" forever.
        if _gate_expired(run, run.get("gate") or "", now):
            _expire(deps, uid, rid)
        return False
    stale = run.get("status") == "running" and not lease_is_live(run.get("lease"), now)
    if not (stale or run.get("status") == "failed"):
        return False
    phase = run.get("phase") or "p1"
    attempt = acquire_lease(deps.store, uid, rid, deps.owner, now, {"status": "running"})
    if attempt is None:
        return False
    deps.spawn(lambda: _worker(deps, uid, rid, phase, attempt))
    return True


def _merge_metrics(base: dict, ctx_metrics: dict, outcome_metrics: dict, active_s: float) -> dict:
    out = dict(base)
    for k, v in ctx_metrics.items():
        out[k] = float(out.get(k, 0.0)) + float(v) if k in ADDITIVE_METRICS else float(v)
    out.update({k: float(v) for k, v in outcome_metrics.items()})
    out["active_s"] = float(active_s)
    return out


def _patch_if_holder(deps: Deps, uid: str, rid: str, attempt: int, patch: dict) -> None:
    rp = run_path(uid, rid)
    writes = deps.store.transact([rp], lambda snap: [(rp, {**snap[rp], **patch})]
                                 if holds_lease(snap[rp], deps.owner, attempt) else [])
    if not writes:
        raise LeaseLost(rid)


def _gate_step(ctx: PhaseContext, outcome: PhaseOutcome, auto: bool) -> StepOutput:
    title = AUTO_TITLES[outcome.gate] if auto else GATE_TITLES[outcome.gate]
    ctx.emit(f"{ctx.phase}.gate.{outcome.gate}", "orchestrator", "gate", title, outcome.message,
             payload={"gate": outcome.gate, "auto": auto})
    return StepOutput(data={"gate": outcome.gate, "auto": auto})


class _WriterBox:
    """Lets the heartbeat thread fence whichever `EventWriter` the worker currently owns, even though
    a new writer is created for every phase a worker advances through in Auto mode. `set()` is called
    by the worker thread each time it starts a new phase; `fence()` is called by the heartbeat thread,
    under the same lock, so it always fences the writer that is actually live at that moment (or does
    nothing if none has been set yet)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: EventWriter | None = None

    def set(self, events: EventWriter) -> None:
        with self._lock:
            self._events = events

    def fence(self) -> None:
        with self._lock:
            events = self._events
        if events is not None:
            events.fence()


def _heartbeat_tick(deps: Deps, uid: str, rid: str, attempt: int, last_ok: float) -> tuple[bool, float]:
    """One heartbeat attempt. Returns `(is_lost, new_last_ok)`. `is_lost` is True when `heartbeat()`
    explicitly confirms the lease is gone, OR when the last *confirmed* heartbeat is older than
    `HEARTBEAT_STALE_S` -- e.g. because Firestore heartbeats keep raising and the worker can no longer
    prove it still holds the lease. A single failing heartbeat within the grace period does not, on its
    own, declare the lease lost: it may just be a transient Firestore hiccup."""
    now = deps.clock()
    try:
        ok = heartbeat(deps.store, uid, rid, deps.owner, attempt, now)
    except Exception:
        log.exception("heartbeat failed for %s/%s", uid, rid)
        ok = None  # neither confirmed held nor confirmed lost
    if ok:
        last_ok = now
    stale = deps.clock() - last_ok > HEARTBEAT_STALE_S
    return (ok is False) or stale, last_ok


def _heartbeat_loop(deps: Deps, uid: str, rid: str, attempt: int, lost: threading.Event,
                    stop: threading.Event, box: "_WriterBox") -> None:
    last_ok = deps.clock()
    while not stop.wait(deps.heartbeat_s):
        is_lost, last_ok = _heartbeat_tick(deps, uid, rid, attempt, last_ok)
        if is_lost:
            # Self-fence immediately, from this thread: don't wait for the worker to notice on its
            # next emit() -- it may be deep inside a long step with nothing pending to notice with.
            lost.set()
            box.fence()
            return


def _worker(deps: Deps, uid: str, rid: str, phase: str, attempt: int) -> None:
    rp = run_path(uid, rid)
    lost, stop, box = threading.Event(), threading.Event(), _WriterBox()
    threading.Thread(target=_heartbeat_loop, args=(deps, uid, rid, attempt, lost, stop, box), daemon=True).start()
    current: str | None = phase
    try:
        while current:
            run = deps.store.get_doc(rp) or {}
            metrics = dict(run.get("metrics") or {})
            events = EventWriter(deps.store, rp, phase=current, step=f"{current}.start", attempt=attempt,
                                 start_seq=next_seq(deps.store, rp, attempt))
            box.set(events)  # the heartbeat thread fences this writer if it loses the lease
            ctx = PhaseContext(deps, uid, rid, current, attempt, events, lost, float(metrics.get("active_s", 0.0)))
            try:
                try:
                    outcome = phase_fn(deps, current)(ctx)
                except ParkAtGate as park:
                    outcome = PhaseOutcome(gate=park.gate, forced=True, message=park.message)
                auto = run.get("autonomy") == "auto" and outcome.gate in AUTO_GATES and not outcome.forced
                if outcome.gate:
                    run_step(ctx, f"{current}.gate.{outcome.gate}", lambda: _gate_step(ctx, outcome, auto))
            except LeaseLost:
                events.fence()  # a stale worker writes no further events (fenced flush/close are no-ops)
                raise
            finally:
                events.close()
            metrics = _merge_metrics(metrics, ctx.metrics, outcome.metrics, ctx.active_s())
            if outcome.gate is None:
                release_lease(deps.store, uid, rid, deps.owner, attempt,
                              {**outcome.run_patch, "status": "done", "phase": current, "gate": None,
                               "finished_at": deps.clock(), "metrics": metrics})
                return
            if auto:
                nxt = NEXT_PHASE[current]
                _patch_if_holder(deps, uid, rid, attempt, {**outcome.run_patch, "phase": nxt, "metrics": metrics})
                current = nxt
                continue
            metrics["gate_entered_at"] = deps.clock()
            release_lease(deps.store, uid, rid, deps.owner, attempt,
                          {**outcome.run_patch, "status": "at_gate", "phase": current, "gate": outcome.gate,
                           "metrics": metrics})
            return
    except LeaseLost:
        log.info("run %s/%s: lease lost; another worker continues", uid, rid)
    except Exception as exc:
        log.exception("run %s/%s failed in %s", uid, rid, current)
        _record_failure(deps, uid, rid, current or phase, attempt, exc)
        try:
            # Minor 3 (fix round 1): a store error here (e.g. a transient Firestore outage) must not
            # escape as an uncaught exception on the worker thread -- that would just silently strand
            # the run "running" forever with nobody left to notice, instead of (best-effort) leaving it
            # for resume_run's stale-lease path to pick up later.
            release_lease(deps.store, uid, rid, deps.owner, attempt, {"status": "failed", "phase": current or phase})
        except Exception:
            log.exception("could not release the lease after a failure for %s/%s", uid, rid)
    finally:
        stop.set()


def _record_failure(deps: Deps, uid: str, rid: str, phase: str, attempt: int, exc: Exception) -> None:
    rp = run_path(uid, rid)
    try:
        if not holds_lease(deps.store.get_doc(rp), deps.owner, attempt):
            return  # a newer attempt already took over; this attempt must not emit anything more
        step, now = f"{phase}.failed", deps.clock()
        deps.store.set_doc(f"{rp}/steps/{step}", StepRecord(id=step, phase=phase, status="failed", attempt=attempt,
                                                             started_at=now, finished_at=now).model_dump())
        w = EventWriter(deps.store, rp, phase=phase, step=step, attempt=attempt,
                        start_seq=next_seq(deps.store, rp, attempt), flush_interval_s=0)
        w.emit("system", "status", "Run stopped by an error; resume to retry", detail=type(exc).__name__, step=step)
        w.close()
    except Exception:
        log.exception("could not record failure for %s/%s", uid, rid)
