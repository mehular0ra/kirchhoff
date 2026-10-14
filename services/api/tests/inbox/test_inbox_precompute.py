import copy
import json

from kirchhoff.agents.runner import ReplayRunner
from kirchhoff.enterprise.world.config import load_world_config
from kirchhoff.enterprise.world.inbox import build_inbox
from kirchhoff.inbox.precompute import main, precompute
from kirchhoff.runs.fakes import FAKE_OPPORTUNITIES, FAKE_REPLIES

VERDICTS = {"em-hall-b": "pursue", "em-konkan-rfi": None, "em-narmada-400kv": "decline",
            "em-suryodaya-solar": "clarify", "em-tapti-brochure": None, "em-vindhya-boq": "clarify"}


def _capture(seed, scenarios, erp, replies=None):
    return precompute(seed, runner=ReplayRunner(replies or FAKE_REPLIES), scenarios_dir=scenarios,
                      opportunities=FAKE_OPPORTUNITIES, erp=erp)


def test_precompute_covers_every_seeded_email_deterministically(inbox_seed, scenarios, erp):
    capture = _capture(inbox_seed, scenarios, erp)
    assert capture["version"] == 1 and capture["model"] == "gemini-3.8-flash" and capture["as_of"] == inbox_seed.as_of
    assert {k: v["fit"]["verdict"] for k, v in capture["results"].items()} == VERDICTS
    assert all(v["source"] == "precomputed" and v["triaged_at"] == inbox_seed.as_of
               for v in capture["results"].values())
    assert _capture(inbox_seed, scenarios, erp) == capture


def test_the_capture_folds_into_the_ws4_inbox_build(inbox_seed, scenarios, erp):
    capture = _capture(inbox_seed, scenarios, erp)
    build = build_inbox(load_world_config(scenarios / "demo_world" / "world.yaml"), scenarios, capture["results"])
    assert {e.id: e.triage["fit"]["verdict"] for e in build.seed.emails} == VERDICTS


def test_the_capture_carries_only_sanitized_text(inbox_seed, scenarios, erp):
    """Review carry-in 1: what the real agent says reaches the static bundle only after trust.sanitize."""
    reply = copy.deepcopy(FAKE_REPLIES["inbox:triage:em-hall-b"])
    reply["text"]["summary"] = "Hall B needs 6 transformers of 2.5 MVA."
    capture = _capture(inbox_seed, scenarios, erp, {**FAKE_REPLIES, "inbox:triage:em-hall-b": reply})
    assert capture["results"]["em-hall-b"]["summary"] == "Bid from Deccan Compute."
    assert capture["results"]["em-hall-b"]["fit"]["verdict"] == "pursue"  # the sentence changed, the verdict did not


def test_cli_with_the_replay_backend_writes_the_capture(tmp_path, capsys):
    out = tmp_path / "inbox-triage.json"
    assert main(["--backend", "replay", "--out", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert sorted(data["results"]) == sorted(VERDICTS)
    assert "em-hall-b: pursue (7/7 quotes verified)" in capsys.readouterr().out
