import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from kirchhoff.agents import copilot as copilot_mod
from kirchhoff.agents.copilot import NO_MATCH, OUT_OF_RANGE, VOICE_TOOLS, WHAT_IF_PARAMS
from kirchhoff.agents.runner import AgentResult, ReplayRunner
from kirchhoff.agents.specs import COPILOT_VOICE
from kirchhoff.agents.trust import fill_finding, fmt_number
from kirchhoff.contracts import Finding

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


def _ts_properties(blob: str) -> set[str]:
    return set(re.findall(r"(\w+):\s*Schema\.(?:string|number|enumString)\(", blob))


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


def test_voice_tool_args_match_ws3_live_tool_declarations():
    """Issue #36: voice no longer hands Python callables to the model (no automatic function calling), so the
    signature half of the parity check moves to VOICE_TOOLS, the table the server validates and runs: the
    same tool names with the same argument names as WS3's TOOL_DECLARATIONS, and the model is told exactly
    that vocabulary."""
    decls = _ts_declarations(WS3_LIVE_SPEC.read_text(encoding="utf-8"))
    assert {name: set(args) for name, args in VOICE_TOOLS.items()} == {n: _ts_properties(b) for n, b in decls.items()}
    for name, args in VOICE_TOOLS.items():
        assert name in COPILOT_VOICE.instruction
        for arg in args:
            assert arg in COPILOT_VOICE.instruction
    for param in WHAT_IF_PARAMS:
        assert param in COPILOT_VOICE.instruction


def test_voice_budget_is_one_attempt_just_under_twenty_seconds():
    """Issue #36 (option 3): 20 s server budget as the safety net, the model call's own timeout just under it
    (so the HTTP call gives up and frees its worker before the 504), and a single attempt: no with_retries
    back-off inside the budget (the measured 26 s outlier)."""
    assert copilot_mod.VOICE_TIMEOUT_S == 20.0
    assert copilot_mod.VOICE_TIMEOUT_S - 1.0 <= COPILOT_VOICE.timeout_s < copilot_mod.VOICE_TIMEOUT_S
    assert COPILOT_VOICE.attempts == 1
    assert COPILOT_VOICE.thinking == "low"  # Vertex rejects "minimal" for gemini-3.8-flash (400, 15 Oct)


class VoiceSpy(ReplayRunner):
    """Replays one recorded model reply for the voice call and records what voice offered the model."""

    def __init__(self, reply: dict):
        super().__init__({"copilot:voice": reply})
        self.offered: list[list] = []

    def run(self, spec, key, message, tools=(), attachments=()):
        self.offered.append(list(tools))
        return super().run(spec, key, message, tools, attachments)


def _intent(seeded, transcript, tool, args, **extra) -> VoiceSpy:
    spy = VoiceSpy({"text": {"transcript": transcript, "tool": tool, "args": args, **extra}})
    seeded.voice_runner = spy
    return spy


def _one_model_call(spy: VoiceSpy) -> None:
    assert spy.calls == ["copilot:voice"]  # one round trip: no second turn, no repair, no retry
    assert spy.offered == [[]]  # no automatic function calling: the model is offered no tools


def _voice(client, auth, files=CLIP, ref="seed:hall-a@r2"):
    return client.post("/api/voice", files=files, data={"revision_ref": ref}, headers=auth)


# --- the three demo questions (issue #30), replayed as the one {transcript, tool, args} reply ---

def test_voice_demo_what_if_runs_the_engine_and_answers_with_the_engine_summary(client, seeded, auth):
    spy = _intent(seeded, "What if racks go to 200 kW?", "what_if", {"param": "rack_kw", "value": 200})
    r = _voice(client, auth)
    assert r.status_code == 200
    body = r.json()
    _one_model_call(spy)
    assert body["transcript"] == "What if racks go to 200 kW?"  # the user's words (R13), its value verified
    assert body["answer"] == "With rack_kw at 200, these checks fail: R01, R02, R08."
    [res] = body["tool_results"]
    assert set(body) == {"transcript", "answer", "tool_results"} and set(res) == {"name", "args", "result"}
    assert res["name"] == "what_if" and res["args"] == {"param": "rack_kw", "value": 200.0}
    assert res["result"]["impact_chain"]


class NoCallRunner:
    """deps.runner for voice tests: voice's explain must not make a second model call (coordinator ruling 1)."""

    def __init__(self):
        self.calls = []

    def run(self, spec, key, message, tools=(), attachments=()):
        self.calls.append(key)
        raise AssertionError(f"unexpected model call {key}")


def test_voice_demo_explain_answers_with_the_findings_own_filled_explanation(client, seeded, auth):
    seeded.runner = no_call = NoCallRunner()
    spy = _intent(seeded, "Why did FA-01 fail?", "explain_finding", {"element_id": "FA-01"})
    body = _voice(client, auth, ref="seed:hall-a@r1").json()
    _one_model_call(spy)
    assert no_call.calls == []
    [res] = body["tool_results"]
    assert res["name"] == "explain_finding" and res["args"] == {"finding_id": "R05:FA-01"}
    assert res["result"]["text"] == "Voltage drop: 2.16% against a limit of 2%."
    assert body["answer"] == res["result"]["text"]
    assert body["transcript"] == "Why did FA-01 fail?"


def test_voice_demo_focus_shows_the_element(client, seeded, auth):
    spy = _intent(seeded, "Show me H-Z2.", "focus_element", {"element_id": "H-Z2"})
    body = _voice(client, auth).json()
    _one_model_call(spy)
    assert body == {"transcript": "Show me H-Z2.", "answer": "Showing H-Z2.",
                    "tool_results": [{"name": "focus_element", "args": {"element_id": "H-Z2"},
                                      "result": {"focused": "H-Z2"}}]}


def test_voice_explain_by_finding_id(client, seeded, auth):
    spy = _intent(seeded, "Explain R05 on FA-01.", "explain_finding", {"finding_id": "R05:FA-01"})
    body = _voice(client, auth, ref="seed:hall-a@r1").json()
    _one_model_call(spy)
    assert body["tool_results"][0]["args"] == {"finding_id": "R05:FA-01"}


def test_voice_explain_by_element_id_picks_its_failing_finding(client, seeded, auth):
    _intent(seeded, "Why is FA-01 red?", "explain_finding", {"element_id": "FA-01"})
    body = _voice(client, auth, ref="seed:hall-a@r1").json()
    assert body["tool_results"][0]["args"] == {"finding_id": "R05:FA-01"}


def test_voice_resolves_a_spoken_id_spelling_to_the_real_id_only(client, seeded, auth):
    """A transcription may drop the hyphen or the case ("hz2"); it resolves to the one real id it spells, and
    only that real id is echoed."""
    _intent(seeded, "Show me hz2.", "focus_element", {"element_id": "hz2"})
    body = _voice(client, auth).json()
    assert body["tool_results"] == [{"name": "focus_element", "args": {"element_id": "H-Z2"},
                                     "result": {"focused": "H-Z2"}}]
    assert body["answer"] == "Showing H-Z2."
    assert body["transcript"] == "Show me hz2."


def test_voice_a_turn_with_no_tool_keeps_the_transcript_and_answers_honestly(client, seeded, auth):
    spy = _intent(seeded, "Hello there.", "none", {})
    body = _voice(client, auth).json()
    _one_model_call(spy)
    assert body == {"transcript": "Hello there.", "answer": NO_MATCH, "tool_results": []}


# --- forged ids and values: no tool result, and nothing the model invented is echoed ---

FORGED = [
    ("focus_element", {"element_id": "the 7.77 percent feeder"}, "Show me the 7.77 percent feeder.", NO_MATCH),
    ("focus_element", {"element_id": "FA-77"}, "Show me FA-77.", NO_MATCH),
    ("focus_element", {"element_id": ["FA-01"]}, "Show me FA-77.", NO_MATCH),
    ("explain_finding", {"finding_id": "R05:FA-77"}, "Why did FA-77 fail?", NO_MATCH),
    ("explain_finding", {"element_id": "FA-77"}, "Why did FA-77 fail?", NO_MATCH),
    ("explain_finding", {}, "Why did it fail?", NO_MATCH),
    ("what_if", {"param": "rack_kw", "value": 777}, "What if racks go to 777 kW?", OUT_OF_RANGE),
    ("what_if", {"param": "rack_kw", "value": -7.77}, "What if racks go to -7.77 kW?", OUT_OF_RANGE),
    ("what_if", {"param": "rack_kw", "value": "7.77 kW"}, "What if racks go to 7.77 kW?", OUT_OF_RANGE),
    ("what_if", {"param": "rack_kw", "value": True}, "What if racks go up?", OUT_OF_RANGE),
    ("what_if", {"param": "rack_kw", "value": float("nan")}, "What if racks go to 777 kW?", OUT_OF_RANGE),
    ("what_if", {"param": "rack_kw"}, "What if racks go to 777 kW?", OUT_OF_RANGE),
    ("what_if", {"param": "voltage_pct", "value": 7.77}, "What if the voltage is 7.77%?", NO_MATCH),
    ("delete_project", {"project_id": "hall-a-777"}, "Delete project 777.", NO_MATCH),
]


@pytest.mark.parametrize("tool,args,transcript,answer", FORGED,
                         ids=[f"{t}-{i}" for i, (t, *_rest) in enumerate(FORGED)])
def test_voice_forged_tool_or_args_give_no_tool_result_and_echo_nothing(client, seeded, auth, tool, args,
                                                                        transcript, answer):
    """Issue #36: the server validates the model's {tool, args} with the same checks the tools applied (the
    what-if param enum and PARAM_BOUNDS, real finding ids, real element ids). Anything else gives no tool
    result and an honest code-authored answer, and nothing the model invented -- an id, a value or a tool
    name -- reaches the answer or the tool results. The transcript is the user's own words (R13)."""
    spy = _intent(seeded, transcript, tool, args)
    r = _voice(client, auth, ref="seed:hall-a@r1")
    assert r.status_code == 200
    body = r.json()
    _one_model_call(spy)
    assert body["tool_results"] == []
    assert body["answer"] == answer
    assert body["transcript"] == transcript
    dumped = json.dumps({"answer": body["answer"], "tool_results": body["tool_results"]})
    for leak in ("7.77", "777", "FA-77", "voltage_pct", "delete_project", "hall-a"):
        assert leak not in dumped, leak


@pytest.mark.parametrize("leak", ["FA-01 is at {value} against {limit}.", "FA-01 is at two point one six percent.",
                                  "FA-01 is at 7.77 percent."], ids=["placeholder", "number-words", "digits"])
def test_voice_never_shows_model_written_answer_text(client, seeded, auth, leak):
    """Issue #36: the model writes no answer any more; the answer is the code-authored engine_summary (R14).
    An `answer` field the model adds anyway is ignored, so a placeholder, a quantity in words or a stray digit
    can never be shown or spoken."""
    _intent(seeded, "How bad is FA-01?", "focus_element", {"element_id": "FA-01"},
            answer=f"Here is FA-01 on the canvas. {leak}")
    body = _voice(client, auth).json()
    assert body["answer"] == "Showing FA-01."
    assert "7.77" not in json.dumps(body) and "{value}" not in json.dumps(body)


def test_voice_transcript_is_the_users_own_words_unfiltered(client, seeded, auth):
    """R13: the transcript is the user's own words, shown as "You said" and exempt from the digit allowlist,
    so a number the user spoke is shown as spoken, even one the engine never ran with."""
    _intent(seeded, "What if racks go to 500 kW, about 7.77 percent more?", "what_if",
            {"param": "rack_kw", "value": 500})
    body = _voice(client, auth).json()
    assert body["transcript"] == "What if racks go to 500 kW, about 7.77 percent more?"
    assert body["answer"] == OUT_OF_RANGE and body["tool_results"] == []


def test_voice_a_malformed_reply_is_not_repaired_with_a_second_model_call(client, seeded, auth):
    spy = VoiceSpy({"text": "I think they asked about the racks."})
    seeded.voice_runner = spy
    body = _voice(client, auth).json()
    assert spy.calls == ["copilot:voice"]
    assert body == {"transcript": "", "answer": NO_MATCH, "tool_results": []}


def test_voice_focus_element_does_not_wait_on_a_concurrent_slow_erp_refresh(client, seeded, auth):
    """Fix round 2, Minor: deps.scenario() shared Deps._lock with deps.erp() (separate locks since the P2
    final fix wave; tests/runs/test_runs_deps.py covers that directly). Previously scn was fetched
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
    time.sleep(0.05)  # let the background thread actually enter deps.erp()'s locked refresh

    _intent(seeded, "Show me FA-01", "focus_element", {"element_id": "FA-01"})
    start = time.monotonic()
    try:
        body = _voice(client, auth).json()
        elapsed = time.monotonic() - start
        assert body["answer"] == "Showing FA-01."
        assert elapsed < 1.0
    finally:
        release.set()
        t.join(timeout=5)


# --- "why" looks back to where the check failed (coordinator ruling 2, the web co-pilot's UX-1 D1) ---

def _real(real_client, transcript, tool, args, ref="seed:hall-a@r2"):
    client, bundle = real_client
    deps = client.app.state.deps
    deps.runner = no_call = NoCallRunner()
    spy = _intent(deps, transcript, tool, args)
    body = client.post("/api/voice", files=CLIP, data={"revision_ref": ref},
                       headers={"Authorization": "Bearer test-token"}).json()
    _one_model_call(spy)
    assert no_call.calls == []
    return body, bundle


def _filled(f: Finding) -> str:
    return fill_finding(f.explanation, f.value, f.limit, f.unit)


def _d1_parts(bundle, element: str):
    """From the bundle's records only: the current revision, its parent, and the parent's failing finding."""
    r2 = next(r for r in bundle.revisions if r.id == "r2")
    r1 = next(r for r in bundle.revisions if r.id == r2.parent)
    failed = next(f for f in bundle.findings[r1.id] if f.element_id == element and f.status == "fail")
    return r1, r2, failed


@pytest.mark.parametrize("args", [{"element_id": "FA-01"}, {"finding_id": "R05:FA-01"}, {"element_id": "fa01"}],
                         ids=["by-element", "by-passing-finding-id", "spoken-spelling"])
def test_voice_why_on_r2_cites_where_fa01_failed_and_its_fix(real_client, args):
    """Seed hall-a r2: FA-01 passes every check, so "why did FA-01 fail?" answers from r1, where R05 failed,
    and the parallel-cable fix that r2 applied -- every value from the bundle's records (code-authored, R14)."""
    body, bundle = _real(real_client, "Why did FA-01 fail?", "explain_finding", args)
    r1, r2, failed = _d1_parts(bundle, "FA-01")
    fix = failed.fix
    assert failed.id == "R05:FA-01" and "parallel cable" in fix["label"]
    cost = f"+${fix['cost_delta']:,.0f}"
    dv = f"{round(fix['deltas']['dv_pct'], 2)}%"
    expected = (f"In {r1.id}: {_filled(failed)} Fixed in {r2.id}: {fix['label']} · Cost Δ {cost} · ΔV {dv}.")
    assert body["answer"] == expected
    assert f"{fmt_number(failed.value)}% against a limit of {fmt_number(failed.limit)}%" in body["answer"]
    assert cost in body["answer"]
    assert body["tool_results"] == [{"name": "explain_finding", "args": {"finding_id": failed.id},
                                     "result": {"text": expected}}]


def test_voice_why_on_r2_for_h_z2_cites_the_crossing_fix(real_client):
    body, bundle = _real(real_client, "Why did H-Z2 fail?", "explain_finding", {"element_id": "H-Z2"})
    r1, r2, failed = _d1_parts(bundle, "H-Z2")
    fix = failed.fix
    assert body["answer"].startswith(f"In {r1.id}: {_filled(failed)} Fixed in {r2.id}: ")
    assert "pipe_low" not in body["answer"] and f"+${fix['cost_delta']:,.0f}" in body["answer"]


def test_voice_why_on_the_failing_revision_explains_it_there(real_client):
    body, bundle = _real(real_client, "Why did FA-01 fail?", "explain_finding", {"element_id": "FA-01"},
                         ref="seed:hall-a@r1")
    failed = next(f for f in bundle.findings["r1"] if f.element_id == "FA-01" and f.status == "fail")
    assert body["answer"] == _filled(failed)
    assert body["tool_results"][0]["args"] == {"finding_id": failed.id}


def test_voice_why_falls_back_to_the_current_finding_when_it_never_failed(real_client):
    client, bundle = real_client
    never = sorted({f.element_id for f in bundle.findings["r2"] if f.element_id.startswith("FA-")}
                   - {f.element_id for fs in bundle.findings.values() for f in fs if f.status != "pass"})[0]
    body, _ = _real(real_client, f"Why is {never} fine?", "explain_finding", {"element_id": never})
    first = next(f for f in bundle.findings["r2"] if f.element_id == never)
    assert body["answer"] == _filled(first) and not body["answer"].startswith("In ")
    assert body["tool_results"][0]["args"] == {"finding_id": first.id}


def test_voice_why_follows_ws_revision_parents_in_the_store(real_client):
    client, bundle = real_client
    deps = client.app.state.deps
    revs = {r.id: r for r in bundle.revisions}
    for rid, parent in (("x-r1", None), ("x-r2", "x-r1")):
        rev = revs[rid.split("-")[1]]
        deps.store.set_doc(f"workspaces/u1/revisions/{rid}", {"id": rid, "parent": parent,
                                                               "model": rev.model.model_dump(mode="json")})
        for f in bundle.findings[rev.id]:
            deps.store.set_doc(f"workspaces/u1/revisions/{rid}/findings/{f.id}", f.model_dump(mode="json"))
    body, _ = _real(real_client, "Why did FA-01 fail?", "explain_finding", {"element_id": "FA-01"}, ref="ws:x-r2")
    _, _, failed = _d1_parts(bundle, "FA-01")
    assert body["answer"].startswith(f"In x-r1: {_filled(failed)} Fixed in x-r2: {failed.fix['label']} · Cost Δ +$")
    assert body["tool_results"][0]["args"] == {"finding_id": failed.id}


def test_voice_model_failure_falls_back_to_the_summary(client, seeded, auth):
    seeded.voice_runner = ReplayRunner({"copilot:voice": {"raise": "vertex down"}})
    body = _voice(client, auth).json()
    assert body == {"transcript": "", "answer": NO_MATCH, "tool_results": []}


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
    _intent(seeded, "hi", "none", {})
    files = {"audio": ("clip.webm", b"\x1aE\xdf\xa3fake-webm-bytes", "audio/webm;codecs=opus")}
    r = _voice(client, auth, files=files)
    assert r.status_code == 200


def test_voice_normalizes_x_wav_to_wav(client, seeded, auth):
    received = {}

    class SpyRunner:
        def run(self, spec, key, message, tools=(), attachments=()):
            received["mime"] = attachments[0].mime_type
            return AgentResult(text='{"transcript": "", "tool": "none", "args": {}}')

    seeded.voice_runner = SpyRunner()
    files = {"audio": ("clip.wav", b"RIFF....fake-wav-bytes", "audio/x-wav")}
    r = _voice(client, auth, files=files)
    assert r.status_code == 200
    assert received["mime"] == "audio/wav"


def test_voice_a_hung_model_times_out_at_the_budget_and_leaves_the_pool_free(client, seeded, auth, monkeypatch):
    """Issue #36: a hung model call gives 504 at about VOICE_TIMEOUT_S (one deadline from the request start),
    after exactly one model call, and the LLM pool is not left blocked: here the pool has one worker, the
    hung call is released by an Event right after the assertions (no sleeps), and the worker is proven free
    again."""
    release, returned = threading.Event(), threading.Event()
    calls: list[str] = []

    class HungRunner:
        def run(self, spec, key, message, tools=(), attachments=()):
            calls.append(key)
            try:
                release.wait(10)
                return AgentResult(text='{"transcript": "", "tool": "none", "args": {}}')
            finally:
                returned.set()

    pool = ThreadPoolExecutor(max_workers=1)
    monkeypatch.setattr(copilot_mod, "_LLM_POOL", pool)
    monkeypatch.setattr(copilot_mod, "VOICE_TIMEOUT_S", 0.3)
    seeded.voice_runner = HungRunner()
    try:
        start = time.monotonic()
        r = _voice(client, auth)
        elapsed = time.monotonic() - start
        assert r.status_code == 504
        assert r.json() == {"detail": "timeout"}
        assert 0.3 <= elapsed < 2.0
        assert calls == ["voice"]
    finally:
        release.set()
    assert returned.wait(5)
    assert pool.submit(lambda: "free").result(timeout=5) == "free"
    pool.shutdown(wait=True)


def test_voice_a_model_call_that_times_out_itself_is_a_504_not_a_fallback(client, seeded, auth, monkeypatch):
    """Issue #36: COPILOT_VOICE.timeout_s sits just under VOICE_TIMEOUT_S, so in production a hung Vertex call
    usually ends with the HTTP client's own timeout (httpx.ReadTimeout) a moment before the voice deadline. That
    is a timeout too: a 504, never the "could not match that" fallback. The single worker is free at once."""

    class ReadTimeout(Exception):  # the name httpx gives it
        pass

    class TimingOutRunner:
        def run(self, spec, key, message, tools=(), attachments=()):
            raise ReadTimeout("The read operation timed out")

    pool = ThreadPoolExecutor(max_workers=1)
    monkeypatch.setattr(copilot_mod, "_LLM_POOL", pool)
    seeded.voice_runner = TimingOutRunner()
    r = _voice(client, auth)
    assert r.status_code == 504
    assert r.json() == {"detail": "timeout"}
    _intent(seeded, "Show me FA-01", "focus_element", {"element_id": "FA-01"})
    assert _voice(client, auth).json()["answer"] == "Showing FA-01."
    pool.shutdown(wait=True)


def test_voice_maps_a_bad_revision_ref_not_as_a_generic_value_error(client, seeded, auth):
    r = _voice(client, auth, ref="not-a-ref")
    assert r.status_code == 422 and r.json() == {"detail": "bad_revision_ref"}


class DownEnterpriseForVoice:
    def list_materials(self):
        from kirchhoff.enterprise.client import EnterpriseUnavailable
        raise EnterpriseUnavailable("sandbox down")


def test_voice_returns_503_when_the_enterprise_sandbox_is_unavailable(client, seeded, auth):
    """The ERP is only fetched lazily for what_if, so this requires a what_if intent."""
    seeded.enterprise = DownEnterpriseForVoice()
    seeded._erp = None
    _intent(seeded, "What if racks go to 200 kW?", "what_if", {"param": "rack_kw", "value": 200})
    r = _voice(client, auth)
    assert r.status_code == 503 and r.json() == {"detail": "enterprise_unavailable"}


class ValueErrorEnterpriseForVoice:
    def list_materials(self):
        raise ValueError("422 from the sandbox: bad material query")  # mirrors HttpEnterpriseClient._call


def test_voice_falls_back_to_the_summary_on_an_erp_value_error_during_what_if(client, seeded, auth):
    """Fix round 2, Minor: an ERP-side ValueError (HttpEnterpriseClient on a sandbox 422, unrelated to
    EnterpriseUnavailable) surfacing from what_if's lazy erp() fetch is a tool failure like any other -- no
    tool result and the honest fallback answer, not a 500. The transcript (its value validated) is kept."""
    seeded.enterprise = ValueErrorEnterpriseForVoice()
    seeded._erp = None
    _intent(seeded, "What if racks go to 200 kW?", "what_if", {"param": "rack_kw", "value": 200})
    body = _voice(client, auth).json()
    assert body == {"transcript": "What if racks go to 200 kW?", "answer": NO_MATCH, "tool_results": []}


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
    _intent(seeded, "What if racks go to 200 kW?", "what_if", {"param": "rack_kw", "value": 200})
    with pytest.raises(ValidationError):
        _voice(client, auth)
