"""Event seq continuity. Events themselves are written by the P0 EventWriter: one writer per phase attempt
(spec §11: single writer assigns seq), shared by parallel steps, every event tagged with emit(..., step=...)."""
from kirchhoff.store import Store


def next_seq(store: Store, run_path: str) -> int:
    """Resume and later phases continue seq from the highest value already written (spec v4.1 §6.2)."""
    last = store.list_docs(f"{run_path}/events", order_by="seq", descending=True, limit=1)
    return int(last[0].get("seq", 0)) + 1 if last else 1
