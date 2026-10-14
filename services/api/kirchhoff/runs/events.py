"""Event seq continuity. Events themselves are written by the P0 EventWriter: one writer per phase attempt
(spec §11: single writer assigns seq), shared by parallel steps, every event tagged with emit(..., step=...)."""
from kirchhoff.store import Store

SEQ_GAP = 10_000  # {seq:06d} doc ids stay valid up to 999,999


def next_seq(store: Store, run_path: str, attempt: int | None = None) -> int:
    """Resume and later phases continue seq from the highest value already written (spec v4.1 §6.2).

    I-1/P2-R5: event doc ids are `events/{seq:06d}`, shared across every attempt of a run. If the run
    has already moved to a newer lease attempt than the highest written event's attempt (a takeover
    already happened), a new writer must not pick up right after that event: a stale worker can still
    flush pending events it buffered before it noticed the takeover, and if its writer's `_seq` counter
    were also sitting right there, that late flush would land on the same doc ids the new attempt just
    wrote and silently overwrite them.

    A *fixed* gap is not enough: a stale writer at attempt N (N >= 2) that has flushed nothing yet in
    its own attempt computes its start seq from the same last-flushed event (written by some earlier
    attempt) that a later attempt N+1 also sees, if N also flushed nothing before N+1 took over -- both
    would land on the identical `base + SEQ_GAP`. The gap must instead be proportional to how many
    attempts have elapsed since that last-flushed event (or since attempt 1, if none was ever flushed),
    so every attempt gets its own disjoint SEQ_GAP-wide window regardless of how many intermediate
    attempts wrote nothing durable at all. `attempt` should be passed explicitly by the caller (it
    already knows which attempt it is creating a writer for); when omitted, it falls back to the run
    doc's current lease attempt for callers that don't have it to hand.
    """
    last = store.list_docs(f"{run_path}/events", order_by="seq", descending=True, limit=1)
    current_attempt = attempt
    if current_attempt is None:
        run = store.get_doc(run_path)
        current_attempt = ((run or {}).get("lease") or {}).get("attempt")
    if not last:
        # No event has ever been flushed yet. Gap proportionally to how many attempts (including this
        # one) have come and gone since attempt 1, so two never-flushed attempts (e.g. 2 and 3) don't
        # both land on the same start seq.
        if current_attempt is None:
            return 1
        return 1 + SEQ_GAP * max(0, current_attempt - 1)
    base = int(last[0].get("seq", 0)) + 1
    last_attempt = last[0].get("attempt", current_attempt)
    if current_attempt is None:
        return base
    return base + SEQ_GAP * max(0, current_attempt - last_attempt)
