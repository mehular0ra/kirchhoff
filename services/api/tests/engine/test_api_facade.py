import inspect

from kirchhoff.contracts import DesignModel, Geometry
from kirchhoff.engine import api


def test_model_hash_is_stable_and_sensitive():
    m = DesignModel(topology="2N", racks=[], equipment=[], connections=[], cooling_nodes=[], pipes=[],
                    geometry=Geometry(hall=(60.0, 36.0), columns=[], keepouts=[], rooms={}, tiers={}),
                    loads={"rack_kw": 132.0})
    h = api.model_hash(m)
    assert len(h) == 64 and h == api.model_hash(m.model_copy(deep=True))
    assert h != api.model_hash(m.model_copy(update={"loads": {"rack_kw": 133.0}}))


def test_ledger_not_checked_lists_spec_items():
    items = api.ledger_not_checked()
    assert any("Earth-fault loop impedance" in i for i in items)
    assert any("Arc flash" in i for i in items) and any("35 °C" in i for i in items)
    assert any("R03" in i for i in items)


def test_facade_signatures():
    expected = {
        "load_scenario": ["name", "root"], "place_racks": ["scn"], "size_cooling": ["scn", "racks"],
        "power_options": ["scn", "racks"], "annotate_options": ["scn", "options", "erp"],
        "route": ["scn", "model"], "detect_clashes": ["model"], "check": ["scn", "model", "erp", "pr_lines"],
        "fix_candidates": ["scn", "model", "finding", "erp"], "apply_fix": ["model", "candidate"],
        "what_if": ["scn", "model", "param", "value", "revision_ref", "erp"],
        "derive_pr_lines": ["scn", "model", "erp"], "model_hash": ["model"], "ledger_not_checked": [],
    }
    for name, params in expected.items():
        if not hasattr(api, name):
            continue  # added by a later task; test_regression asserts the full set
        assert list(inspect.signature(getattr(api, name)).parameters) == params, name
