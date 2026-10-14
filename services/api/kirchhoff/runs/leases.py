"""Run leases (spec §6.2) and the global live-run cap (spec §11). All writes go through Store.transact."""
from collections.abc import Callable

from kirchhoff.store import Store

STALE_S = 60.0
GLOBAL_CAP = 3
LIVE_RUNS_DOC = "ops/live_runs"


class CapReached(Exception):
    """Three runs already hold live leases."""


def run_path(uid: str, rid: str) -> str:
    return f"workspaces/{uid}/runs/{rid}"


def _key(uid: str, rid: str) -> str:
    return f"{uid}__{rid}"


def lease_is_live(lease: dict | None, now: float) -> bool:
    return bool(lease and lease.get("owner") and now - float(lease.get("heartbeat_at") or 0.0) < STALE_S)


def holds_lease(run: dict | None, owner: str, attempt: int) -> bool:
    lease = (run or {}).get("lease") or {}
    return lease.get("owner") == owner and lease.get("attempt") == attempt


def _fresh_others(live: dict | None, key: str, now: float) -> dict[str, float]:
    runs = (live or {}).get("runs") or {}
    return {k: float(t) for k, t in runs.items() if k != key and now - float(t) < STALE_S}


def acquire_lease(store: Store, uid: str, rid: str, owner: str, now: float, run_patch: dict | None = None,
                  expect: Callable[[dict], bool] | None = None) -> int | None:
    """Returns the new attempt, or `None` if the run is missing, its lease is live, or `expect` (when
    given) returns False. Raises `CapReached` (nothing written, including to `LIVE_RUNS_DOC`) when the
    global cap is already held by other runs. `run_patch`, if given, is a *shallow* merge into the run
    doc (top-level keys only -- it replaces a key's whole value, it does not deep-merge nested dicts).

    Minor 1 (fix round 1): `expect` lets a caller claim the lease only if the run doc still looks the
    way it expected when it decided to claim it (e.g. `resume_from_gate` wants to confirm it is still
    at the gate it checked, and not yet expired) -- evaluated *inside* this transaction, on the actual
    snapshot being committed against, closing the check-then-act gap between a caller's own read and
    its subsequent acquire_lease call (E1/E2)."""
    path, key = run_path(uid, rid), _key(uid, rid)

    def fn(snap: dict[str, dict | None]):
        run, live = snap[path], snap[LIVE_RUNS_DOC]
        if run is None or lease_is_live(run.get("lease"), now):
            return []
        if expect is not None and not expect(run):
            return []
        others = _fresh_others(live, key, now)
        if len(others) >= GLOBAL_CAP:
            raise CapReached()  # the transaction writes nothing
        attempt = int((run.get("lease") or {}).get("attempt") or 0) + 1
        new_run = {**run, **(run_patch or {}), "lease": {"owner": owner, "attempt": attempt, "heartbeat_at": now}}
        return [(path, new_run), (LIVE_RUNS_DOC, {"runs": {**others, key: now}})]

    writes = store.transact([path, LIVE_RUNS_DOC], fn)
    return int(writes[0][1]["lease"]["attempt"]) if writes else None


def heartbeat(store: Store, uid: str, rid: str, owner: str, attempt: int, now: float) -> bool:
    path, key = run_path(uid, rid), _key(uid, rid)

    def fn(snap: dict[str, dict | None]):
        run, live = snap[path], snap[LIVE_RUNS_DOC]
        if not holds_lease(run, owner, attempt):
            return []
        runs = {**_fresh_others(live, key, now), key: now}
        return [(path, {**run, "lease": {**run["lease"], "heartbeat_at": now}}), (LIVE_RUNS_DOC, {"runs": runs})]

    return bool(store.transact([path, LIVE_RUNS_DOC], fn))


def release_lease(store: Store, uid: str, rid: str, owner: str, attempt: int, run_patch: dict) -> bool:
    """Returns True iff `owner`/`attempt` held the lease and the release was written. `run_patch`
    is a *shallow* merge into the run doc, same as `acquire_lease`. The lease itself is always set
    to `{"owner": None, "attempt": attempt, "heartbeat_at": 0.0}`, overriding any `lease` key in
    `run_patch`."""
    path, key = run_path(uid, rid), _key(uid, rid)

    def fn(snap: dict[str, dict | None]):
        run, live = snap[path], snap[LIVE_RUNS_DOC]
        if not holds_lease(run, owner, attempt):
            return []
        runs = {k: t for k, t in ((live or {}).get("runs") or {}).items() if k != key}
        new_run = {**run, **run_patch, "lease": {"owner": None, "attempt": attempt, "heartbeat_at": 0.0}}
        return [(path, new_run), (LIVE_RUNS_DOC, {"runs": runs})]

    return bool(store.transact([path, LIVE_RUNS_DOC], fn))
