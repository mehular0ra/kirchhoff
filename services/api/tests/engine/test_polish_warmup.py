"""P1 engine polish (2026-10-13), items 3-4: warm the signed seed's short-circuit key, and give warm_up
its own lock. See .superpowers/sdd/2026-10-13-p1-engine/polish-brief.md."""
import threading
import time

from kirchhoff.engine import api


# ------------------------------------------------------------- Item 3: warm the seed key ----

def test_warm_up_primes_the_signed_seed_key(scn, erp, racks):
    from kirchhoff.engine.benchmark import golden_fixed
    from kirchhoff.engine.shortcircuit import _CACHE, _key

    seed = golden_fixed(scn, erp)
    seed_key = _key(scn, seed)

    _CACHE.clear()
    api._WARMED_UP = False
    api.warm_up()
    assert seed_key in _CACHE, "warm_up did not pre-cache the signed seed model's short-circuit key"


def test_first_what_if_on_seed_model_is_fast_after_warm_up(scn, erp, racks):
    from kirchhoff.engine.benchmark import golden_fixed
    from kirchhoff.engine.shortcircuit import _CACHE

    seed = golden_fixed(scn, erp)
    _CACHE.clear()
    api._WARMED_UP = False
    api.warm_up()

    t0 = time.perf_counter()
    api.what_if(scn, seed, "rack_kw", 150.0, "seed:hall-a@r2", erp)
    took_ms = 1000 * (time.perf_counter() - t0)
    assert took_ms < 20, f"first what_if on the seed model took {took_ms:.1f} ms after warm_up"


# ------------------------------------------------------------- Item 4: warm_up's own lock ----

def test_concurrent_warm_up_callers_do_not_redo_the_work(monkeypatch):
    """A single, uncontended warm_up() call already invokes short_circuit several times (golden_fixed's own
    fix loop re-runs the rule pack). The lock's job is only to stop THREE concurrent callers from each
    redoing that same work: with the lock, three callers cost exactly what one call costs; without it,
    they would cost roughly three times as much."""
    from kirchhoff.engine import shortcircuit

    real_short_circuit = shortcircuit.short_circuit

    # Baseline: how many short_circuit calls one, uncontended warm_up() makes.
    baseline: list[int] = []
    monkeypatch.setattr(shortcircuit, "short_circuit", lambda scn, model: (baseline.append(1),
                                                                           real_short_circuit(scn, model))[1])
    api._WARMED_UP = False
    api.warm_up()
    single_call_count = len(baseline)
    assert single_call_count > 0

    # Now race three concurrent callers against a fresh _WARMED_UP, with each short_circuit call gated so
    # all three threads have a chance to reach warm_up's body before any of them finishes the work.
    api._WARMED_UP = False
    calls: list[int] = []
    gate = threading.Event()

    def slow_short_circuit(scn, model):
        calls.append(1)
        gate.wait(timeout=5.0)
        return real_short_circuit(scn, model)

    monkeypatch.setattr(shortcircuit, "short_circuit", slow_short_circuit)

    threads = [threading.Thread(target=api.warm_up) for _ in range(3)]
    for t in threads:
        t.start()
    time.sleep(0.2)  # let the other two threads block on _WARM_LOCK while the first does its work
    gate.set()
    for t in threads:
        t.join()

    assert len(calls) == single_call_count, (
        f"3 concurrent warm_up() callers made {len(calls)} short_circuit calls; a single call makes "
        f"{single_call_count}, so the lock did not stop the other callers from redoing the work")
    assert api._WARMED_UP is True
