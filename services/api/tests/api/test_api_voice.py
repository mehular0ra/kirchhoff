import inspect
import re
import threading
import time
from pathlib import Path

import pytest

from kirchhoff.agents import copilot as copilot_mod
from kirchhoff.agents.copilot import WHAT_IF_PARAMS
from kirchhoff.agents.runner import AgentResult, ReplayRunner
from kirchhoff.api import copilot_routes

CLIP = {"audio": ("clip.webm", b"\x1aE\xdf\xa3fake-webm-bytes", "audio/webm")}
WS3_LIVE_SPEC = (Path(__file__).resolve().parents[4] / "apps" / "web" / "src" / "workspace" / "copilot" / "voice"
                 / "liveVoiceSpec.ts")


def _ts_declarations(src: str) -> dict[str, str]:
    """Maps each declared tool's name -> its full declaration body (whitespace-normalized), so the parity
    check can assert on `properties` AND `optionalProperties`, tolerant of formatting drift (quote style,
    line wraps) instead of matching one long exact substring."""
    decls = {}
    for m in re.finditer(r"\{\s*name:\s*['\"](\w+)['\"](.*?)\n  \},", src, re.S):
        decls[m.group(1)] = re.sub(r"\s+", " ", m.group(2)).strip()
    return decls


def _ts_enum_values(blob: str, key: str) -> set[str]:
    m = re.search(rf"{key}:.*?enum:\s*\[(.*?)\]", blob, re.S)
    assert m, f"no enum found for {key!r} in {blob!r}"
    return set(re.findall(r"['\"]([^'\"]+)['\"]", m.group(1)))


def test_voice_tools_match_ws3_live_tool_declarations():
    """Parity check (brief): voice's tool names/params must match WS3's Live TOOL_DECLARATIONS exactly.
    Fix round 2: the enum SET must be equal (not just each WHAT_IF_PARAMS value present, which would miss an
    extra TS-side param), and the `optionalProperties` declaration is checked again (restored)."""
    src = WS3_LIVE_SPEC.read_text(encoding="utf-8")
    decls = _ts_declarations(src)
    assert set(decls) == {"what_if", "explain_finding", "focus_element"}
    assert _ts_enum_values(decls["what_if"], "param") == set(WHAT_IF_PARAMS)
    assert "value: Schema.number()" in decls["what_if"]
    assert WHAT_IF_PARAMS == ("rack_kw", "liquid_fraction", "dv_limit_pct", "tx_loading_cap_pct")
    assert "finding_id: Schema.string()" in decls["explain_finding"]
    assert "element_id: Schema.string()" in decls["explain_finding"]
    assert "optionalProperties: ['finding_id', 'element_id']" in decls["explain_finding"]
    assert "element_id: Schema.string()" in decls["focus_element"]


class SignatureSpyRunner:
    """Records the tool callables voice offers the model, so the test can assert on their real Python
    signatures (name, params) instead of only on the TS side of the parity check."""

    def __init__(self):
        self.tools = []

    def run(self, spec, key, message, tools=(), attachments=()):
        self.tools = list(tools)
        return AgentResult(text='{"transcript": "", "answer": ""}')


def test_voice_tool_signatures_match_ws3_live_tool_declarations(client, seeded, auth):
    spy = SignatureSpyRunner()
    seeded.voice_runner = spy
    _voice(client, auth)
    sigs = {t.__name__: str(inspect.signature(t)) for t in spy.tools}
    assert set(sigs) == {"what_if", "explain_finding", "focus_element"}
    assert sigs["what_if"].startswith("(param: typing.Literal[") or sigs["what_if"].startswith("(param: Literal[")
    for param in WHAT_IF_PARAMS:
        assert param in sigs["what_if"]
    assert "value: float" in sigs["what_if"]
    assert sigs["explain_finding"] == "(finding_id: str = '', element_id: str = '') -> dict"
    assert sigs["focus_element"] == "(element_id: str) -> dict"


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


def test_voice_focus_element_does_not_wait_on_a_concurrent_slow_erp_refresh(client, seeded, auth):
    """Fix round 2, Minor: deps.scenario() shares Deps._lock with deps.erp(). Previously scn was fetched
    eagerly at the top of answer_voice for every call, so a focus_element-only voice call (which needs
    neither the scenario nor the ERP) could wait behind another request's slow ERP refresh holding that
    lock -- the reviewer measured a 1s-budget call waiting 2.91s this way. scn is now lazy, fetched only
    inside what_if (its only use)."""
    release = threading.Event()

    class SlowEnterprise:
        def list_materials(self):
            release.wait(5)
            return []

    seeded.enterprise = SlowEnterprise()
    seeded._erp = None
    held = threading.Event()

    def hold_lock():
        held.set()
        seeded.erp()

    t = threading.Thread(target=hold_lock, daemon=True)
    t.start()
    held.wait(2)
    time.sleep(0.05)  # let the background thread actually enter deps.erp()'s `with self._lock:` block

    seeded.voice_runner = ReplayRunner({"copilot:voice": {
        "tool_calls": [{"name": "focus_element", "args": {"element_id": "FA-01"}}],
        "text": {"transcript": "Show me FA-01", "answer": "Here is FA-01 on the canvas."}}})
    start = time.monotonic()
    try:
        body = _voice(client, auth).json()
        elapsed = time.monotonic() - start
        assert body["answer"] == "Here is FA-01 on the canvas."
        assert elapsed < 1.0
    finally:
        release.set()
        t.join(timeout=5)


def test_voice_focus_element_rejects_an_unknown_id_and_keeps_digits_out(client, seeded, auth):
    """Fix round 1, Critical: an id the model invented (carrying its own narration, with digits) must not be
    trusted into tool_results or the engine_summary template. Reproduced by the reviewer: `focus_element`
    called with `element_id="the 7.77 percent feeder"` leaked "Showing the 7.77 percent feeder." verbatim."""
    seeded.voice_runner = ReplayRunner({"copilot:voice": {
        "tool_calls": [{"name": "focus_element", "args": {"element_id": "the 7.77 percent feeder"}}],
        "text": {"transcript": "Show me the worst feeder", "answer": "Showing the 7.77 percent feeder."}}})
    body = _voice(client, auth).json()
    assert body["tool_results"] == []
    assert "7.77" not in body["answer"]
    assert body["answer"] == "I could not match that to a design question; try a what-if chip."


def test_voice_explain_tool_uses_the_explanation_path(client, seeded, auth):
    seeded.voice_runner = ReplayRunner({"copilot:voice": {
        "tool_calls": [{"name": "explain_finding", "args": {"finding_id": "R05:FA-01"}}],
        "text": {"transcript": "Why did FA-01 fail?", "answer": "It is too long."}}})
    body = _voice(client, auth, ref="seed:hall-a@r1").json()
    assert body["tool_results"][0]["result"]["text"].startswith("FA-01 has a voltage drop of 2.16%")
    assert body["tool_results"][0]["args"] == {"finding_id": "R05:FA-01"}
    assert body["answer"] == "It is too long."


class RaisingRunner:
    def run(self, spec, key, message, tools=(), attachments=()):
        raise RuntimeError("vertex down")


def test_voice_explain_finding_logs_the_real_cause_when_the_runner_raises(client, seeded, auth, caplog):
    """Fix round 2, Minor: explain_text's deadline branch (used when already on an _LLM_POOL worker, as
    voice's explain_finding is) runs the LLM call on a plain thread; if that thread's target raises, the
    exception does not propagate to whoever joins it, so `box` stays empty. Previously `wait()` then did
    `return box[0]`, raising an unrelated IndexError that masked the real cause in the fallback log message
    -- the user-facing fallback text is the same template either way, so only the logged cause tells them
    apart."""
    seeded.runner = RaisingRunner()
    seeded.voice_runner = ReplayRunner({"copilot:voice": {
        "tool_calls": [{"name": "explain_finding", "args": {"finding_id": "R05:FA-01"}}],
        "text": {"transcript": "Why did FA-01 fail?", "answer": "It is too long."}}})
    with caplog.at_level("WARNING", logger="kirchhoff.copilot"):
        body = _voice(client, auth, ref="seed:hall-a@r1").json()
    assert body["tool_results"][0]["result"]["text"] == "Voltage drop: 2.16% against a limit of 2%."
    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "vertex down" in messages
    assert "IndexError" not in messages


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


def test_voice_rejects_an_oversize_declared_content_length_before_parsing(client, seeded, auth):
    """Fix round 1, Important #1a: a declared Content-Length over budget is rejected immediately, without
    ever calling request.form() -- defends the Cloud Run temp filesystem (RAM) against an unbounded parse."""
    r = client.post("/api/voice", files=CLIP, data={"revision_ref": "seed:hall-a@r2"},
                    headers={**auth, "content-length": str(10_000_000)})
    assert r.status_code == 413
    assert r.json() == {"detail": "audio_too_large"}


def test_voice_requires_a_content_length_header(client, seeded, auth):
    """Fix round 2, Important #1: a request with no declared Content-Length at all (e.g. a chunked upload)
    is rejected outright, before the body is ever read -- a browser always sends Content-Length for a
    FormData body, so this only turns away an unusual client, never a real one."""
    boundary = "voicetestboundary"
    body = ((f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="audio"; filename="clip.webm"\r\n'
            "Content-Type: audio/webm\r\n\r\n").encode()
           + b"\x1aE\xdf\xa3fake-webm-bytes"
           + f"\r\n--{boundary}--\r\n".encode())

    def chunks():
        yield body

    r = client.post("/api/voice", content=chunks(),
                    headers={**auth, "content-type": f"multipart/form-data; boundary={boundary}"})
    assert r.status_code == 411
    assert r.json() == {"detail": "length_required"}


def test_voice_bounds_a_hidden_oversize_field_not_just_the_audio_field(client, seeded, auth):
    """Fix round 2, Important #1: Starlette's `max_part_size` does not bound FILE parts (only non-file form
    fields -- see `formparsers.py`'s `on_part_data`), so bounding only `audio`'s own final read gave no real
    protection against a client that lies about a small Content-Length and smuggles megabytes into an
    unrelated field: the reviewer measured 6 MB spooled this way. Proof this is the real fix (not the
    pre-existing `len(data) > VOICE_MAX_BYTES` check on `audio` alone, which this request would sail past,
    since `audio` itself is tiny): a small, valid `audio` field plus a 3 MB unrelated `junk` field, with a
    lying small Content-Length, is still rejected -- the raw stream is now bounded during parsing itself
    (`_bounded_stream`), independent of which field the bytes are attributed to."""
    files = {"audio": CLIP["audio"], "junk": ("junk.bin", b"0" * 3_000_000, "application/octet-stream")}
    r = client.post("/api/voice", files=files, data={"revision_ref": "seed:hall-a@r2"},
                    headers={**auth, "content-length": "100"})
    assert r.status_code == 413
    assert r.json() == {"detail": "audio_too_large"}


def test_voice_rejects_an_unparsable_content_length(client, seeded, auth):
    r = client.post("/api/voice", files=CLIP, data={"revision_ref": "seed:hall-a@r2"},
                    headers={**auth, "content-length": "not-a-number"})
    assert r.status_code == 411
    assert r.json() == {"detail": "length_required"}


def test_voice_rejects_revision_ref_sent_as_a_file_part(client, seeded, auth):
    """Fix round 2, Minor: a revision_ref sent as a file part (an UploadFile, not a str) must be rejected
    cleanly, not crash with a 500 inside load_revision's regex matching."""
    files = {"audio": CLIP["audio"], "revision_ref": ("ref.txt", b"seed:hall-a@r2", "text/plain")}
    r = client.post("/api/voice", files=files, headers=auth)
    assert r.status_code == 422
    assert r.json() == {"detail": "bad_revision_ref"}


def test_voice_strips_codec_parameters_from_the_content_type(client, seeded, auth):
    seeded.voice_runner = ReplayRunner({"copilot:voice": {
        "tool_calls": [], "text": {"transcript": "hi", "answer": "Here is FA-01 on the canvas."}}})
    files = {"audio": ("clip.webm", b"\x1aE\xdf\xa3fake-webm-bytes", "audio/webm;codecs=opus")}
    r = _voice(client, auth, files=files)
    assert r.status_code == 200


def test_voice_normalizes_x_wav_to_wav(client, seeded, auth):
    received = {}

    class SpyRunner:
        def run(self, spec, key, message, tools=(), attachments=()):
            received["mime"] = attachments[0].mime_type
            return AgentResult(text='{"transcript": "", "answer": ""}')

    seeded.voice_runner = SpyRunner()
    files = {"audio": ("clip.wav", b"RIFF....fake-wav-bytes", "audio/x-wav")}
    r = _voice(client, auth, files=files)
    assert r.status_code == 200
    assert received["mime"] == "audio/wav"


def test_voice_times_out(client, seeded, auth, monkeypatch):
    """Fix round 2, Minor: event-based, not a fixed time.sleep(5.0) -- the LLM-pool worker running
    HungRunner is released right after the assertions instead of staying busy regardless."""
    release = threading.Event()

    class HungRunner:
        def run(self, spec, key, message, tools=(), attachments=()):
            release.wait(10)
            return AgentResult(text='{"transcript": "", "answer": ""}')

    monkeypatch.setattr(copilot_mod, "VOICE_TIMEOUT_S", 0.2)
    seeded.voice_runner = HungRunner()
    try:
        r = _voice(client, auth)
        assert r.status_code == 504
        assert r.json() == {"detail": "timeout"}
    finally:
        release.set()


def test_voice_maps_a_bad_revision_ref_not_as_a_generic_value_error(client, seeded, auth):
    r = _voice(client, auth, ref="not-a-ref")
    assert r.status_code == 422 and r.json() == {"detail": "bad_revision_ref"}


class DownEnterpriseForVoice:
    def list_materials(self):
        from kirchhoff.enterprise.client import EnterpriseUnavailable
        raise EnterpriseUnavailable("sandbox down")


def test_voice_returns_503_when_the_enterprise_sandbox_is_unavailable(client, seeded, auth):
    """The ERP is only fetched lazily inside what_if, so this requires a what_if tool call."""
    seeded.enterprise = DownEnterpriseForVoice()
    seeded._erp = None
    seeded.voice_runner = ReplayRunner({"copilot:voice": {
        "tool_calls": [{"name": "what_if", "args": {"param": "rack_kw", "value": 200}}],
        "text": {"transcript": "What if racks go to 200 kW?", "answer": "ok"}}})
    r = _voice(client, auth)
    assert r.status_code == 503 and r.json() == {"detail": "enterprise_unavailable"}


class ValueErrorEnterpriseForVoice:
    def list_materials(self):
        raise ValueError("422 from the sandbox: bad material query")  # mirrors HttpEnterpriseClient._call


def test_voice_falls_back_to_the_summary_on_an_erp_value_error_during_what_if(client, seeded, auth):
    """Fix round 2, Minor: an ERP-side ValueError (HttpEnterpriseClient on a sandbox 422, unrelated to
    EnterpriseUnavailable) surfacing from inside what_if's lazy erp() fetch is a model/tool failure like any
    other -- it falls back to the engine_summary (NO_MATCH, since no tool result was recorded), not a 500."""
    seeded.enterprise = ValueErrorEnterpriseForVoice()
    seeded._erp = None
    seeded.voice_runner = ReplayRunner({"copilot:voice": {
        "tool_calls": [{"name": "what_if", "args": {"param": "rack_kw", "value": 200}}],
        "text": {"transcript": "What if racks go to 200 kW?", "answer": "ok"}}})
    body = _voice(client, auth).json()
    assert body == {"transcript": "", "answer": "I could not match that to a design question; try a what-if chip.",
                    "tool_results": []}


class ValidationErrorEngineForVoice:
    def what_if(self, *args, **kwargs):
        from kirchhoff.contracts import Finding
        Finding.model_validate({})  # missing required fields: raises pydantic.ValidationError


def test_voice_does_not_mask_a_validation_error_as_a_fallback(client, seeded, auth):
    """Fix round 2, Minor: a pydantic ValidationError (a server bug -- a malformed engine/erp record) must
    propagate, not be swallowed into the ordinary "could not match that" fallback the way a genuine
    model/tool failure is, matching how /api/what-if treats it."""
    from pydantic import ValidationError

    seeded.engine = ValidationErrorEngineForVoice()
    seeded.voice_runner = ReplayRunner({"copilot:voice": {
        "tool_calls": [{"name": "what_if", "args": {"param": "rack_kw", "value": 200}}],
        "text": {"transcript": "What if racks go to 200 kW?", "answer": "ok"}}})
    with pytest.raises(ValidationError):
        _voice(client, auth)
