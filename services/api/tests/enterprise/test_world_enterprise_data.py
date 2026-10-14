import pytest
import yaml

from kirchhoff.enterprise.model import FICTIONAL_NOTICE, seed_hash
from kirchhoff.enterprise.world.enterprise_data import (MaterialsErp, build_enterprise_seed, build_materials,
                                                         hall_a_materials)


def _seed(cfg, scenarios_root):
    return build_enterprise_seed(cfg, build_materials(cfg, hall_a_materials(scenarios_root)))


def test_hall_a_materials_are_included_verbatim(world_cfg, scenarios_root):
    by_id = {m.id: m for m in _seed(world_cfg, scenarios_root).materials}
    assert all(by_id[m.id] == m for m in hall_a_materials(scenarios_root))


def test_world_counts_match_spec_13(world_cfg, scenarios_root):
    seed = _seed(world_cfg, scenarios_root)
    assert 55 <= len(seed.materials) <= 65
    assert len(seed.accounts) == 5 and len(seed.opportunities) == 9
    stages = {o.id: o.stage for o in seed.opportunities}
    assert stages["opp-hall-a"] == "Design approved" and stages["opp-hall-b"] == "Design in progress"
    assert {o.account for o in seed.opportunities} == set(seed.accounts)
    assert seed.notice == FICTIONAL_NOTICE == world_cfg.notice


def test_extras_cannot_change_engine_choices(world_cfg, scenarios_root):
    hall_a = hall_a_materials(scenarios_root)
    cat = yaml.safe_load((scenarios_root / "hall_a" / "catalogue.yaml").read_text(encoding="utf-8"))
    catalogue_ids = {i["id"] for v in cat.values() if isinstance(v, list) for i in v if isinstance(i, dict)}
    pairs = {(m.category, m.voltage) for m in hall_a}
    extras = [m for m in build_materials(world_cfg, hall_a) if m.id not in {h.id for h in hall_a}]
    assert len(extras) == 40
    assert not {m.id for m in extras} & catalogue_ids
    assert [m.id for m in extras if (m.category, m.voltage) in pairs] == []


def test_only_the_2_5_mva_transformer_misses_the_lead_time_limit(scenarios_root):
    assert [m.id for m in hall_a_materials(scenarios_root) if m.stock == 0 and m.lead_time_weeks > 26] == ["TX-2500"]


def test_seed_is_deterministic_and_depends_on_the_seed(world_cfg, scenarios_root):
    assert seed_hash(_seed(world_cfg, scenarios_root)) == seed_hash(_seed(world_cfg, scenarios_root))
    other = world_cfg.model_copy(update={"seed": world_cfg.seed + 1})
    assert seed_hash(_seed(other, scenarios_root)) != seed_hash(_seed(world_cfg, scenarios_root))


def test_historical_prs_are_numbered_in_order_and_reference_known_materials(world_cfg, scenarios_root):
    seed = _seed(world_cfg, scenarios_root)
    assert [p.id for p in seed.prs] == [f"PR-2026-{101 + i:04d}" for i in range(len(seed.prs))]
    assert [p.created_at for p in seed.prs] == sorted(p.created_at for p in seed.prs)
    known = {m.id for m in seed.materials}
    assert all(line.material_id in known for p in seed.prs for line in p.lines)


def test_full_erp_leaves_the_engine_golden_path_unchanged(world_cfg, scenarios_root):
    api = pytest.importorskip("kirchhoff.engine.api")
    bench = pytest.importorskip("kirchhoff.engine.benchmark")
    scn = api.load_scenario("hall_a", scenarios_root)
    hall_a = hall_a_materials(scenarios_root)
    small, full = MaterialsErp(hall_a), MaterialsErp(build_materials(world_cfg, hall_a))
    racks = api.place_racks(scn)

    def swaps(erp):
        return [(o.id, o.swaps) for o, _ in api.annotate_options(scn, api.power_options(scn, racks), erp)]

    assert swaps(small) == swaps(full)
    assert api.model_hash(bench.golden_fixed(scn, small)) == api.model_hash(bench.golden_fixed(scn, full))
