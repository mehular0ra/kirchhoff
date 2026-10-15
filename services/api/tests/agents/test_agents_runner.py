import pytest
from pydantic import BaseModel

from kirchhoff.agents.runner import (AgentSpec, RecordingRunner, ReplayRunner, extract_json, run_json,
                                     with_retries)

SPEC = AgentSpec(name="layout", instruction="x")


class Choice(BaseModel):
    candidate_id: str
    reason: str


def place_racks(count: int = 0) -> dict:
    """Place racks."""
    return {"placed": count}


def test_replay_executes_tool_calls_and_returns_text():
    r = ReplayRunner({"layout:p2.place_racks": {"tool_calls": [{"name": "place_racks", "args": {"count": 3}}],
                                                "text": "Layout placed the racks.", "usage": {"in": 10, "out": 2}}})
    res = r.run(SPEC, "p2.place_racks", "go", tools=[place_racks])
    assert res.text == "Layout placed the racks."
    assert res.tool_calls[0].name == "place_racks" and res.tool_calls[0].result == {"placed": 3}
    assert (res.tokens_in, res.tokens_out) == (10, 2)
    assert r.calls == ["layout:p2.place_racks"]


def test_replay_missing_fixture_raises():
    with pytest.raises(KeyError):
        ReplayRunner({}).run(SPEC, "nope", "m")


def test_replay_can_simulate_failures():
    with pytest.raises(RuntimeError):
        ReplayRunner({"layout:k": {"raise": "boom"}}).run(SPEC, "k", "m")


def test_extract_json_from_fenced_and_wrapped_text():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! {"a": [1, 2]} hope this helps') == {"a": [1, 2]}
    with pytest.raises(ValueError):
        extract_json("no json here")


def test_run_json_parses_dict_replies():
    r = ReplayRunner({"layout:k": {"text": {"candidate_id": "c1", "reason": "cheaper"}}})
    parsed, _ = run_json(r, SPEC, "k", "m", Choice)
    assert parsed.candidate_id == "c1"


def test_run_json_repairs_once():
    r = ReplayRunner({"layout:k": {"text": "candidate c1 because cheaper", "usage": {"in": 5, "out": 5}},
                      "layout:k#repair": {"text": '{"candidate_id": "c1", "reason": "cheaper"}',
                                          "usage": {"in": 7, "out": 3}}})
    parsed, res = run_json(r, SPEC, "k", "m", Choice)
    assert parsed.reason == "cheaper" and (res.tokens_in, res.tokens_out) == (12, 8)


def test_run_json_gives_up_after_one_repair():
    r = ReplayRunner({"layout:k": {"text": "nope"}, "layout:k#repair": {"text": "still nope"}})
    with pytest.raises(ValueError):
        run_json(r, SPEC, "k", "m", Choice)


def test_recording_runner_writes_replayable_fixture(tmp_path):
    inner = ReplayRunner({"layout:p2.place_racks": {"tool_calls": [{"name": "place_racks", "args": {"count": 2}}],
                                                    "text": "done"}})
    RecordingRunner(inner, tmp_path).run(SPEC, "p2.place_racks", "go", tools=[place_racks])
    again = ReplayRunner(fixtures_dir=tmp_path).run(SPEC, "p2.place_racks", "go", tools=[place_racks])
    assert again.text == "done" and again.tool_calls[0].result == {"placed": 2}


class Coded(Exception):
    def __init__(self, code):
        super().__init__(f"code {code}")
        self.code = code


def test_with_retries_retries_retryable_errors_only():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise Coded(429)
        return "ok"

    assert with_retries(flaky, sleep=lambda s: None) == "ok" and len(calls) == 3
    with pytest.raises(ValueError):
        with_retries(lambda: (_ for _ in ()).throw(ValueError("x")), sleep=lambda s: None)
    with pytest.raises(Coded):
        with_retries(lambda: (_ for _ in ()).throw(Coded(503)), attempts=2, sleep=lambda s: None)


def test_the_repair_prompt_carries_a_whole_intake_sized_reply():
    """P2 final fix wave (Minor 6): the intake reply is about 6-10 KB with `contradictions` last; a 4,000
    character excerpt cut the repair off before them, so the repaired extraction lost the §4.2/App. B pair."""
    prompts: list[str] = []

    class Spy:
        def run(self, spec, key, message, tools=(), attachments=()):
            from kirchhoff.agents.runner import AgentResult

            prompts.append(message)
            if key.endswith("#repair"):
                return AgentResult('{"candidate_id": "c1", "reason": "ok"}')
            return AgentResult('{"candidate_id": 7, "padding": "' + "x" * 9_500 + '", "reason": "TAIL-MARKER"}')

    parsed, _ = run_json(Spy(), SPEC, "k", "msg", Choice)
    assert parsed.candidate_id == "c1"
    assert "TAIL-MARKER" in prompts[1]
