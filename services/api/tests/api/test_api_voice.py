from pathlib import Path

from kirchhoff.agents.copilot import WHAT_IF_PARAMS
from kirchhoff.agents.runner import ReplayRunner

CLIP = {"audio": ("clip.webm", b"\x1aE\xdf\xa3fake-webm-bytes", "audio/webm")}
WS3_LIVE_SPEC = (Path(__file__).resolve().parents[4] / "apps" / "web" / "src" / "workspace" / "copilot" / "voice"
                 / "liveVoiceSpec.ts")


def test_voice_tools_match_ws3_live_tool_declarations():
    """Parity check (brief): voice's tool names/params must match WS3's Live TOOL_DECLARATIONS exactly."""
    src = WS3_LIVE_SPEC.read_text(encoding="utf-8")
    assert "name: 'what_if'" in src
    assert "param: Schema.enumString({ enum: ['rack_kw', 'liquid_fraction', 'dv_limit_pct', 'tx_loading_cap_pct'] })" \
        in src
    assert "value: Schema.number()" in src
    assert WHAT_IF_PARAMS == ("rack_kw", "liquid_fraction", "dv_limit_pct", "tx_loading_cap_pct")
    assert "name: 'explain_finding'" in src
    assert "properties: { finding_id: Schema.string(), element_id: Schema.string() }" in src
    assert "optionalProperties: ['finding_id', 'element_id']" in src
    assert "name: 'focus_element'" in src
    assert "parameters: Schema.object({ properties: { element_id: Schema.string() } })" in src


def _voice(client, auth, files=CLIP, ref="seed:hall-a@r2"):
    return client.post("/api/voice", files=files, data={"revision_ref": ref}, headers=auth)


def test_voice_runs_what_if_and_filters_the_answer(client, seeded, auth):
    seeded.voice_runner = ReplayRunner({"copilot:voice": {
        "tool_calls": [{"name": "what_if", "args": {"param": "rack_kw", "value": 200}}],
        "text": {"transcript": "What if racks go to 200 kW?", "answer": "At 200 kW per rack R01, R02 and R08 fail."}}})
    r = _voice(client, auth)
    assert r.status_code == 200
    body = r.json()
    assert body["transcript"] == "What if racks go to 200 kW?"  # the user's words (R13)
    assert body["answer"] == "With rack_kw at 200, these checks fail: R01, R02, R08."
    assert body["tool_results"][0]["name"] == "what_if" and body["tool_results"][0]["result"]["impact_chain"]


def test_voice_keeps_a_clean_answer_and_reports_focus(client, seeded, auth):
    seeded.voice_runner = ReplayRunner({"copilot:voice": {
        "tool_calls": [{"name": "focus_element", "args": {"element_id": "FA-01"}}],
        "text": {"transcript": "Show me FA-01", "answer": "Here is FA-01 on the canvas."}}})
    body = _voice(client, auth).json()
    assert body["answer"] == "Here is FA-01 on the canvas."
    assert body["tool_results"] == [{"name": "focus_element", "args": {"element_id": "FA-01"},
                                     "result": {"focused": "FA-01"}}]


def test_voice_explain_tool_uses_the_explanation_path(client, seeded, auth):
    seeded.voice_runner = ReplayRunner({"copilot:voice": {
        "tool_calls": [{"name": "explain_finding", "args": {"finding_id": "R05:FA-01"}}],
        "text": {"transcript": "Why did FA-01 fail?", "answer": "It is too long."}}})
    body = _voice(client, auth, ref="seed:hall-a@r1").json()
    assert body["tool_results"][0]["result"]["text"].startswith("FA-01 has a voltage drop of 2.16%")
    assert body["tool_results"][0]["args"] == {"finding_id": "R05:FA-01"}
    assert body["answer"] == "It is too long."


def test_voice_explain_by_element_id_picks_its_failing_finding(client, seeded, auth):
    seeded.voice_runner = ReplayRunner({"copilot:voice": {
        "tool_calls": [{"name": "explain_finding", "args": {"element_id": "FA-01"}}],
        "text": {"transcript": "Why is FA-01 red?", "answer": "It is too long."}}})
    body = _voice(client, auth, ref="seed:hall-a@r1").json()
    assert body["tool_results"][0]["args"] == {"finding_id": "R05:FA-01"}


def test_voice_scrubs_a_raw_digit_the_model_speaks(client, seeded, auth):
    """Trust path (spec §6.3): any digit the model speaks that is not an engine record/allowlisted id must
    never reach `answer` -- it is replaced by the engine_summary template built from the tool result."""
    seeded.voice_runner = ReplayRunner({"copilot:voice": {
        "tool_calls": [{"name": "what_if", "args": {"param": "rack_kw", "value": 200}}],
        "text": {"transcript": "What if racks go to 200 kW?",
                 "answer": "The voltage drop comes out to about 7.77 percent, which is unsafe."}}})
    body = _voice(client, auth).json()
    assert "7.77" not in body["answer"]
    assert body["answer"] == "With rack_kw at 200, these checks fail: R01, R02, R08."


def test_voice_model_failure_falls_back_to_the_summary(client, seeded, auth):
    seeded.voice_runner = ReplayRunner({"copilot:voice": {"raise": "vertex down"}})
    body = _voice(client, auth).json()
    assert body == {"transcript": "", "answer": "I could not match that to a design question; try a what-if chip.",
                    "tool_results": []}


def test_voice_rejects_bad_uploads(client, seeded, auth):
    big = {"audio": ("clip.webm", b"0" * 2_000_001, "audio/webm")}
    assert _voice(client, auth, files=big).status_code == 413
    assert _voice(client, auth, files={"audio": ("a.txt", b"hello", "text/plain")}).status_code == 415
    assert client.post("/api/voice", data={"revision_ref": "seed:hall-a@r2"}, headers=auth).status_code == 422
    assert _voice(client, auth, ref="seed:hall-a@r9").status_code == 404
