import dataclasses
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from kirchhoff.agents import asset as asset_mod
from kirchhoff.api import asset_routes


def test_grid_pack_returns_engine_result_and_agent_choice(client, deps, auth):
    r = client.post("/api/asset/grid", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert [o["id"] for o in body["options"]] == ["ACSR-Panther", "ACSR-Zebra", "ACSR-Moose"]
    assert body["findings"][0]["rule_id"] == "G01"
    assert body["choice"] == {"option": "ACSR-Zebra", "reason": "Zebra meets the ampacity need with the lowest losses.",
                              "source": "agent"}


def test_solar_reason_with_free_numbers_is_replaced(client, deps, auth):
    deps.runner.replies["asset:solar"] = {"text": {"option": "STR-26", "reason": "It stays under 1,500 V."}}
    body = client.post("/api/asset/solar", headers=auth).json()
    assert body["choice"] == {"option": "STR-26", "reason": "Recommended STR-26 on the engine's ranking.",
                              "source": "agent"}


def test_invalid_agent_option_keeps_the_engine_recommendation(client, deps, auth):
    deps.runner.replies["asset:grid"] = {"text": {"option": "ACSR-Unobtainium", "reason": "best"}}
    body = client.post("/api/asset/grid", headers=auth).json()
    assert body["choice"] == {"option": "ACSR-Zebra", "reason": "Kept the engine recommendation ACSR-Zebra.",
                              "source": "engine"}


def test_unknown_pack_and_timeout(client, deps, auth, monkeypatch):
    assert client.post("/api/asset/wind", headers=auth).status_code == 404

    def slow(scn_dir):
        time.sleep(0.3)
        return {"options": [], "recommended": None, "findings": [], "geometry": {}}

    deps.asset_engines["grid"] = slow
    monkeypatch.setattr(asset_routes, "ASSET_TIMEOUT_S", 0.05)
    r = client.post("/api/asset/grid", headers=auth)
    assert r.status_code == 504 and r.json() == {"detail": "timeout"}


def test_a_reason_with_raw_digits_and_an_invented_option_id_never_reaches_the_client(client, deps, auth):
    """Issue #13 (spec 6.3): the agent picks an engine option id and nothing else. Digits in its reason, and an option
    id the engine never offered, are replaced by the template sentence."""
    deps.runner.replies["asset:grid"] = {"text": {
        "option": "ACSR-Zebra", "reason": "ACSR-Unobtainium-9 would cut losses by 12%, but Zebra is fine."}}
    body = client.post("/api/asset/grid", headers=auth).json()
    assert body["choice"] == {"option": "ACSR-Zebra", "reason": "Recommended ACSR-Zebra on the engine's ranking.",
                              "source": "agent"}
    assert "Unobtainium" not in str(body["choice"]) and "12" not in str(body["choice"])


def test_an_option_id_in_the_reason_is_fine_when_the_engine_offered_it(client, deps, auth):
    deps.runner.replies["asset:solar"] = {"text": {"option": "STR-28", "reason": "STR-28 clears the inverter window."}}
    assert client.post("/api/asset/solar", headers=auth).json()["choice"] == {
        "option": "STR-28", "reason": "STR-28 clears the inverter window.", "source": "agent"}


def test_the_agent_may_name_an_option_in_any_case_but_the_engine_id_is_returned(client, deps, auth):
    deps.runner.replies["asset:grid"] = {"text": {"option": " acsr-moose ", "reason": "Lowest losses."}}
    assert client.post("/api/asset/grid", headers=auth).json()["choice"] == {
        "option": "ACSR-Moose", "reason": "Lowest losses.", "source": "agent"}


@pytest.mark.parametrize("reply", [{"raise": "vertex down"}, {"text": "not json at all"},
                                   {"text": {"reason": "no option field"}}], ids=["raises", "not-json", "no-option"])
def test_an_agent_failure_never_fails_the_pack(client, deps, auth, reply):
    deps.runner.replies["asset:grid"] = reply
    r = client.post("/api/asset/grid", headers=auth)
    assert r.status_code == 200
    assert r.json()["choice"] == {"option": "ACSR-Zebra", "reason": "Kept the engine recommendation ACSR-Zebra.",
                                  "source": "engine"}


def test_a_slow_agent_is_cut_off_and_the_engine_choice_is_kept(client, deps, auth, monkeypatch):
    monkeypatch.setattr(asset_mod, "ASSET", dataclasses.replace(asset_mod.ASSET, timeout_s=0.05))
    real_run = deps.runner.run

    def slow(*args, **kwargs):
        time.sleep(0.5)
        return real_run(*args, **kwargs)

    monkeypatch.setattr(deps.runner, "run", slow)
    started = time.perf_counter()
    r = client.post("/api/asset/grid", headers=auth)
    assert r.status_code == 200 and r.json()["choice"]["source"] == "engine"
    assert time.perf_counter() - started < 0.45  # answered at the agent timeout, not after the slow call


def test_the_agent_call_runs_on_the_llm_pool_not_the_engine_pool(client, deps, auth, monkeypatch):
    """Both calls on the engine pool could deadlock it under load (the engine call waits for the LLM call)."""
    seen = []

    class SpyPool(ThreadPoolExecutor):
        def submit(self, fn, *args, **kwargs):
            seen.append(fn)
            return super().submit(fn, *args, **kwargs)

    monkeypatch.setattr(asset_mod, "_LLM_POOL", SpyPool(max_workers=2))
    assert client.post("/api/asset/solar", headers=auth).status_code == 200
    assert len(seen) == 1


def test_the_pack_needs_a_signed_in_visitor(client):
    assert client.post("/api/asset/grid").status_code == 401


@pytest.fixture
def real_asset(tmp_path, monkeypatch):
    """Real grid and solar engines wired as in production (`_asset_engines`), real scenario files, replayed agent. The
    route budget is raised: these tests are about the result, and a cold pandapower import alone can take 18 s on a
    loaded machine (the budget itself is covered by the timeout tests)."""
    from fastapi.testclient import TestClient

    from kirchhoff.api.app import create_app
    from kirchhoff.api.deps import _asset_engines
    from kirchhoff.engine.scenario import scenarios_root
    from kirchhoff.runs.fakes import CheckedStore, build_fake_deps

    monkeypatch.setattr(asset_routes, "ASSET_TIMEOUT_S", 120.0)
    deps = build_fake_deps(CheckedStore(), scenarios_root(), seed_dir=tmp_path, asset_engines=_asset_engines())
    return TestClient(create_app(deps=deps, verify_token=lambda token: "u1")), deps


@pytest.mark.parametrize("pack, reply_option, engine_choice", [("solar", "STR-30", "STR-28"),
                                                                ("grid", "acsr-dog", "ACSR-ZEBRA")])
def test_the_agent_cannot_pick_an_option_the_engine_says_fails(real_asset, auth, pack, reply_option, engine_choice):
    """Review of #19: STR-30 fails Voc at minimum temperature and ACSR-DOG fails ampacity. Picking one would put
    "Recommended" next to a "Fail" tag while the Checker shows another option's findings."""
    client, deps = real_asset
    deps.runner.replies[f"asset:{pack}"] = {"text": {"option": reply_option, "reason": "Looks like the cheapest."}}
    body = client.post(f"/api/asset/{pack}", headers=auth).json()
    assert body["choice"] == {"option": engine_choice, "reason": f"Kept the engine recommendation {engine_choice}.",
                              "source": "engine"}
    assert next(o for o in body["options"] if o["id"].casefold() == reply_option.casefold())["passes"] is False


def test_a_passing_option_is_still_picked_and_a_failing_id_stays_in_the_reason_allowlist(real_asset, auth):
    client, deps = real_asset
    deps.runner.replies["asset:solar"] = {"text": {"option": "STR-26", "reason": "STR-26 is safer than STR-30."}}
    assert client.post("/api/asset/solar", headers=auth).json()["choice"] == {
        "option": "STR-26", "reason": "STR-26 is safer than STR-30.", "source": "agent"}


TEMPLATE = "Recommended ACSR-Zebra on the engine's ranking."


@pytest.mark.parametrize("reason, shown", [
    ("Zebra keeps the regulation at {value} against {limit}.", TEMPLATE),
    ("It cuts the losses by twelve percent.", TEMPLATE),
    ("Twenty-five percent cheaper.", TEMPLATE),
    ("Zebra is fine. {unit} is not.", "Zebra is fine. " + TEMPLATE)],  # only the offending sentence is replaced
    ids=["slots", "number-word", "tens", "mixed"])
def test_a_reason_with_a_slot_or_a_number_in_words_is_replaced(client, deps, auth, reason, shown):
    """Review of #19: nothing fills a {slot} in an asset reason, and a number spelled out is still a number the engine
    did not produce (spec 6.3). Passes placeholders=False to sanitize explicitly (the P2 wave's default)."""
    deps.runner.replies["asset:grid"] = {"text": {"option": "ACSR-Zebra", "reason": reason}}
    assert client.post("/api/asset/grid", headers=auth).json()["choice"] == {
        "option": "ACSR-Zebra", "reason": shown, "source": "agent"}


def test_a_slow_engine_plus_a_slow_agent_is_still_an_answer_not_a_504(client, deps, auth, monkeypatch):
    """Review of #19: the agent's 5 s timeout is bounded by what is left of the route budget, so a finished engine
    result is never thrown away because the agent used the time the route still needed."""
    fast = deps.asset_engines["grid"]

    def slow_engine(scn_dir):
        time.sleep(0.3)
        return fast(scn_dir)

    deps.asset_engines["grid"] = slow_engine
    monkeypatch.setattr(asset_routes, "ASSET_TIMEOUT_S", 1.0)
    real_run = deps.runner.run

    def slow_agent(*args, **kwargs):
        time.sleep(3.0)
        return real_run(*args, **kwargs)

    monkeypatch.setattr(deps.runner, "run", slow_agent)
    started = time.perf_counter()
    r = client.post("/api/asset/grid", headers=auth)
    assert r.status_code == 200 and r.json()["choice"]["source"] == "engine"
    assert time.perf_counter() - started < 1.0  # answered inside the route budget


def test_an_engine_exception_is_a_502_not_an_unhandled_500(client, deps, auth):
    def broken(scn_dir):
        raise RuntimeError("pandapower exploded")

    deps.asset_engines["solar"] = broken
    r = client.post("/api/asset/solar", headers=auth)
    assert r.status_code == 502 and r.json() == {"detail": "engine_failed"}


@pytest.mark.parametrize("pack, rule_prefix", [("grid", "G"), ("solar", "S")])
def test_the_real_engines_serialise_and_the_agent_choice_is_checked_against_real_ids(real_asset, auth, pack,
                                                                                    rule_prefix):
    """The whole result must be valid JSON for the web page, and the choice must be one of the engine's own option ids
    (the engine spells grid ids in capitals, the replayed agent in mixed case)."""
    client, _ = real_asset
    r = client.post(f"/api/asset/{pack}", headers=auth)
    assert r.status_code == 200
    body = r.json()
    ids = [o["id"] for o in body["options"]]
    assert ids and body["choice"]["option"] in ids and body["choice"]["source"] == "agent"
    assert body["recommended"] in ids and body["geometry"]
    assert body["findings"] and all(f["rule_id"].startswith(rule_prefix) for f in body["findings"])
