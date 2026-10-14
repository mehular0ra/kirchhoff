"""Event seq continuity. Events themselves are written by the P0 EventWriter: one writer per phase attempt
(spec §11: single writer assigns seq), shared by parallel steps, every event tagged with emit(..., step=...)."""
from kirchhoff.store import Store

SEQ_GAP = 10_000  # {seq:06d} doc ids stay valid up to 999,999


def next_seq(store: Store, run_path: str) -> int:
    """Resume and later phases continue seq from the highest value already written (spec v4.1 §6.2).

    I-1: event doc ids are `events/{seq:06d}`, shared across every attempt of a run. If the run has
    already moved to a newer lease attempt than the highest written event's attempt (a takeover already
    happened), a new writer must not pick up right after that event: a stale worker can still flush
    pending events it buffered before it noticed the takeover, and if its writer's `_seq` counter were
    also sitting right there, that late flush would land on the same doc ids the new attempt just wrote
    and silently overwrite them. Jumping the new attempt's range forward by SEQ_GAP makes that collision
    impossible without changing the Task-6 EventWriter API.
    """
    last = store.list_docs(f"{run_path}/events", order_by="seq", descending=True, limit=1)
    run = store.get_doc(run_path)
    current_attempt = ((run or {}).get("lease") or {}).get("attempt")
    if not last:
        # No event has ever been flushed yet. If a prior attempt nonetheless exists (current_attempt > 1,
        # e.g. a takeover won the lease before the stale worker's very first flush landed), that stale
        # worker's writer may already have assigned in-memory seq numbers starting at 1 that it just
        # hasn't flushed yet; gap now so its eventual late flush can never collide with this attempt's ids.
        return 1 + SEQ_GAP if current_attempt is not None and current_attempt != 1 else 1
    base = int(last[0].get("seq", 0)) + 1
    last_attempt = last[0].get("attempt", current_attempt)
    if current_attempt is not None and last_attempt != current_attempt:
        return base + SEQ_GAP
    return base
