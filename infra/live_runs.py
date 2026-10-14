"""Deploy guard (spec §6.2: deploys happen only when no lease is held). Exit 1 if any live run heartbeated within
60 s. Reads WS2's ops/live_runs document {runs: {"{uid}__{rid}": heartbeat_at}} (P2 ruling R6)."""
import sys
import time

LEASE_STALE_S = 60.0


def live_count(doc: dict | None, now: float) -> int:
    runs = (doc or {}).get("runs") or {}
    return sum(1 for hb in runs.values() if isinstance(hb, (int, float)) and now - float(hb) < LEASE_STALE_S)


def main() -> int:
    from google.cloud import firestore

    snap = firestore.Client(project="ordinal-mep").document("ops/live_runs").get()
    n = live_count(snap.to_dict() if snap.exists else None, time.time())
    print(f"live runs holding a lease: {n}")
    return 1 if n else 0


if __name__ == "__main__":
    sys.exit(main())
