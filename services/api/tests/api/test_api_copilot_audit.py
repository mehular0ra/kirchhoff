"""An opt-in record of the co-pilot's API calls, for debugging a conversation afterwards (KIRCHHOFF_LOG_DIR).

Until now the API logged nothing about what the co-pilot was asked or what the engine answered (only a warning when a model
call fell back), so "why did it say that?" could not be answered from the logs. With KIRCHHOFF_LOG_DIR set, every
/api/what-if, /api/explain and /api/voice call appends one JSON line to <dir>/copilot.jsonl: when, which route, a short
hash of the caller (never the uid or the token), the status, how long it took, and what was asked and answered.
Unset, nothing is written: that is the deployed default.
"""
import hashlib
import json

import pytest

from kirchhoff.agents.runner import ReplayRunner
from kirchhoff.api import copilot_log

CLIP = {"audio": ("clip.webm", b"\x1aE\xdf\xa3fake-webm-bytes", "audio/webm")}


@pytest.fixture
def audit(tmp_path, monkeypatch):
    monkeypatch.setenv("KIRCHHOFF_LOG_DIR", str(tmp_path))
    copilot_log.configure()
    yield lambda: [json.loads(line) for line in (tmp_path / "copilot.jsonl").read_text(encoding="utf-8").splitlines()]
    copilot_log.reset()


def _what_if(client, auth, value=200, ref="seed:hall-a@r2"):
    return client.post("/api/what-if", json={"revision_ref": ref, "param": "rack_kw", "value": value}, headers=auth)


def test_a_what_if_is_recorded_with_what_was_asked_and_what_failed(client, seeded, auth, audit):
    r = _what_if(client, auth)
    assert r.status_code == 200
    [line] = audit()
    assert line["route"] == "what_if" and line["status"] == 200
    assert line["revision_ref"] == "seed:hall-a@r2" and line["param"] == "rack_kw" and line["value"] == 200
    assert {"R01", "R02", "R08"} <= set(line["failing"]) and line["impact_chains"] > 0
    assert line["n_findings"] == len(r.json()["findings"])
    assert line["ts"].endswith("Z") and line["ms"] >= 0


def test_a_refused_what_if_is_recorded_with_its_status_and_reason(client, seeded, auth, audit):
    assert _what_if(client, auth, value=99999).status_code == 422
    [line] = audit()
    assert line["status"] == 422 and line["error"] == "invalid_value" and line["value"] == 99999


def test_an_explain_is_recorded_with_the_text_it_returned(client, seeded, auth, audit):
    r = client.post("/api/explain", json={"revision_ref": "seed:hall-a@r1", "finding_id": "R05:FA-01"}, headers=auth)
    assert r.status_code == 200
    [line] = audit()
    assert line["route"] == "explain" and line["finding_id"] == "R05:FA-01" and line["status"] == 200
    assert line["text"] == r.json()["text"]


def test_a_voice_question_is_recorded_with_the_words_heard_the_tool_chosen_and_the_answer(client, seeded, auth, audit):
    seeded.voice_runner = ReplayRunner({"copilot:voice": {"text": {"transcript": "What if racks go to 200 kW?", "tool": "what_if",
                                                                   "args": {"param": "rack_kw", "value": 200}}}})
    r = client.post("/api/voice", files=CLIP, data={"revision_ref": "seed:hall-a@r2"}, headers=auth)
    assert r.status_code == 200
    [line] = audit()
    assert line["route"] == "voice" and line["status"] == 200
    assert line["transcript"] == "What if racks go to 200 kW?"
    assert line["tools"] == ["what_if"] and line["answer"] == r.json()["answer"]
    assert line["audio_bytes"] > 0


def test_a_failure_inside_the_route_is_recorded_as_500_and_still_raised(client, seeded, auth, audit, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("engine bug")

    monkeypatch.setattr(seeded.engine, "what_if", boom)
    with pytest.raises(RuntimeError):
        _what_if(client, auth)
    [line] = audit()
    assert line["status"] == 500 and "engine bug" in line["error"]


def test_the_record_never_holds_the_caller_or_the_token(client, seeded, auth, audit, tmp_path):
    _what_if(client, auth)
    raw = (tmp_path / "copilot.jsonl").read_text(encoding="utf-8")
    line = json.loads(raw)
    assert line["user"] == hashlib.sha256(b"u1").hexdigest()[:8] and "u1" not in {v for v in line.values() if isinstance(v, str) and v != line["user"]}
    assert "test-token" not in raw and "Bearer" not in raw


def test_each_call_is_one_line_and_lines_accumulate(client, seeded, auth, audit):
    _what_if(client, auth, 150)
    _what_if(client, auth, 200)
    assert [line["value"] for line in audit()] == [150, 200]


def test_with_no_log_dir_nothing_is_written(client, seeded, auth, tmp_path, monkeypatch):
    monkeypatch.delenv("KIRCHHOFF_LOG_DIR", raising=False)
    copilot_log.reset()
    copilot_log.configure()
    assert copilot_log._handler is None  # nothing is attached, so nothing can be written anywhere
    assert _what_if(client, auth).status_code == 200
    assert list(tmp_path.glob("copilot.jsonl*")) == []
