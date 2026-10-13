# Kirchhoff P2 — Agents, API, Intake and Run Orchestration (WS2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the WS2 parts of Kirchhoff: the scenario documents (tender PDF, hall DXF and PDF plot, intake ground truth), Intake with verified citations, the four-phase durable run model (steps, leases, resume, gates, Ask/Auto), the Gemini agents on ADK 2.11, the co-pilot, voice, asset and export endpoints, and the full HTTP API that WS3 consumes.

**Architecture:** Each phase is a background worker thread that holds a Firestore lease and executes named **steps**. Each step reads its inputs from Firestore, calls the engine facade (`kirchhoff/engine/api.py`, built by WS1) and at most a few small agent calls, streams its events (~250 ms batches tagged `{step, attempt}`), and then commits its outputs and a `done {attempt}` marker in a Firestore transaction that first checks `lease.attempt`, so resume can skip finished steps and a stale worker can never commit. Agents run through an `AgentRunner` port. ADK `Workflow` + `LlmAgent` is used in production, a `google-genai` runner is the fallback and is also used for audio, and a record/replay runner is used in tests. All LLM text passes a digit allowlist, and every number shown comes from the engine or from pdfplumber verification.

**Tech Stack:** Python 3.12, FastAPI 0.141, pydantic 2.14, google-adk 2.11.0, google-genai, google-cloud-firestore, google-cloud-storage, pdfplumber 0.11.10, reportlab 5.0.1, ezdxf 1.4.4, pyyaml, pytest.

**Spec:** `docs/superpowers/specs/2026-10-13-kirchhoff-design.md` (v4.1). Binding inputs: `docs/superpowers/plans/2026-10-13-interfaces.md` (ownership, engine facade, HTTP API table, event vocabulary) and `docs/superpowers/plans/2026-10-13-p0-foundation.md` (contracts, `Store`, `EventWriter`, auth, `create_app`). Read spec §1, §6, §7, §11, §14, §16 and §17 before starting.

## Global Constraints

- GCP project `ordinal-mep`. Always pass `--project=ordinal-mep` to gcloud. Never run `gcloud config set project`.
- Every local process that calls Google APIs sets `GOOGLE_GENAI_USE_VERTEXAI=true GOOGLE_CLOUD_PROJECT=ordinal-mep GOOGLE_CLOUD_QUOTA_PROJECT=ordinal-mep GOOGLE_CLOUD_LOCATION=global`.
- Fresh code only: write everything from scratch during the hackathon. Open-source libraries are fine.
- Git: use the machine's global git identity. End every commit message with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Do not spawn subagents from inside a task.
- Every `/api` call returns in < 10 s. Phases run in background threads, and POSTs that start a phase return 202 in < 2 s.
- Clients never write Firestore. All mutations go through `/api`.
- All LLM text shown in the UI obeys the digit allowlist (spec §6.3). Use `kirchhoff.agents.trust.sanitize`.
- Every number shown comes from the engine (or from pdfplumber-verified tender quotes). Never type numbers into narration.
- ADK/Gemini model: `gemini-3.8-flash` only. Pro and flash-lite return 404.
- Retry Gemini calls with exponential backoff on 429/5xx (`kirchhoff.agents.runner.with_retries`).
- Firestore discipline (spec §11): events are batched about every 250 ms; `runs/{rid}` gets at most 1 update/s; event payloads are < 10 KB; models never go into Firestore (see ruling R7); one writer per phase assigns `seq`.
- WS2 creates or modifies only the files that `2026-10-13-interfaces.md` assigns to it, plus two small shared edits listed explicitly: `services/api/pyproject.toml` (one dependency) and removing the P0 hello route and its test.

## Rulings on spec ambiguities (binding for this plan; communicated to WS1/WS3/WS4)

| # | Ambiguity | Ruling |
|---|---|---|
| R1 | Exact `tender.yaml` shape | Defined in Task 1 (`TenderDoc`). The fixture `services/api/tests/intake/fixtures/tender.yaml` is the content. WS1's `scenarios/hall_a/tender.yaml` must match it clause for clause; a drift test enforces this. |
| R2 | `geometry.yaml` keys used for the drawing | WS2 reads only `hall`, `grid`, `keepouts`, `rooms`, `rows`, `cdu_gallery` (Task 2 `HallGeometry`). Extra keys are ignored. |
| R3 | "done marker" vs frozen `StepRecord` (no `done` field) | The done marker is `steps/{stepId}.status == "done"`. Step outputs live at `runs/{rid}/outputs/{stepId}` as `{"step", "json": "<JSON string>"}`, or as `{"step", "blob", "sha256"}` when > 400 KB. `outputs_ref` holds that path. |
| R4 | Event streaming and step commit (spec v4.1 §6.2) | Events stream about every 250 ms, tagged `{step, attempt}`. Step start and step commit are each one Firestore **transaction** that first checks `lease.owner == owner and lease.attempt == attempt`, so a stale worker can neither start nor commit a step. The commit writes outputs, any revision/finding docs and `steps/{id} = {status: "done", attempt}`. `seq` is unique per run and each phase or resume continues from the highest `seq` already written. Every event belongs to a step that has a step doc (gates are steps `pN.gate`). **UI rule:** show an event iff `steps/{event.step}.attempt == event.attempt`. |
| R5 | Lease attempt numbering | `attempt` is monotonic across the whole run. Release keeps `{owner: null, attempt, heartbeat_at: 0}`. Resume is allowed when status is `running` with a stale lease (> 60 s), or when status is `failed`. |
| R6 | Global cap of 3 live runs across workspaces | The doc `ops/live_runs` holds `{runs: {"{uid}__{rid}": heartbeat_at}}` and is updated in the same transaction as the lease. |
| R7 | Firestore rejects arrays nested in arrays, but `Geometry.columns`/`keepouts` are lists of tuples | A `DesignModel` is never written to Firestore. Revision docs carry `model: null` and `model_url: "revisions/{rev}/model.json"` (GCS at `workspaces/{uid}/revisions/{rev}/model.json`), served by `GET /api/files/revisions/{rev}/model.json`. |
| R8 | Revision ids | Revision ids are `{rid}-r{n}`. The what-if ref is `ws:{rid}-r{n}`. |
| R9 | Plan-gate question semantics | `OpenQuestion.options = [<main-body value>, "compare_all"]`, and `default_resolution` is the main-body value (`"2N"`). P2 always enumerates every topology; the resolution only filters the Auto option pick. |
| R10 | Auto option pick when no option qualifies | The run parks at the option gate even in Auto mode, with a message. |
| R11 | Fix iteration granularity and owners | One iteration fixes every failing finding and produces one new revision. Power decides R01–R07, R04b and R13; Cooling decides R08–R11 and R14; R12 and R15 take the cheapest engine candidate without an LLM. |
| R12 | Requirement card text | `Requirement.text` is the verified verbatim quote. Unverified extractions are kept with `verified=false`, `value=null`, and text sanitized to a template. The lane shows "N/M quotes verified". |
| R13 | Voice text and the allowlist (spec v4.1 §6.5) | `/api/voice` returns `transcript` (the user's own words, shown as "You said", exempt) and `answer`. The answer is sanitized with an engine-generated summary as its template; the UI shows it and speaks it with browser TTS, so push-to-talk audio is filtered too. For Gemini Live, WS3 copies `LIVE_SYSTEM_INSTRUCTION` from `kirchhoff/agents/specs.py` ("speak only numbers returned by tools") and filters the on-screen model transcript. Every revision ledger carries the `not_checked` entry "Spoken Gemini Live audio is not digit-filtered; on-screen transcripts are." |
| R14 | Code-authored text | Template text filled from engine or verification records (counts, values, hashes) may contain digits. The allowlist governs LLM text only. |
| R15 | Tender/drawing upload | There is no upload route. P1 reads the files baked into the image under `scenarios/hall_a/out/`. Hall B uses Hall A's documents. The UI "drop" is presentational. |
| R16 | Audit trail | The audit trail is the `ledger` events (agent `system`) plus `approvals/*`. A P4 R12 failure is written to `revisions/{rev}/findings/R12:submitted-prs`. |
| R17 | Review rejected | Rejection ends the run (`status: done`, no P4). The visitor starts a new run. |
| R18 | Error shapes | 429 `{"detail":"visitor_rate_limit"}`, 429 `{"detail":"global_cap","offer":"replay"}`, 409 `{"detail":"wrong_state"}`, 409 `{"detail":"gate_expired"}`, 409 `{"detail":"open_findings"}`, 409 `{"detail":"run_in_progress"}`, 504 `{"detail":"timeout"}`. |
| R19 | `load_scenario(name, root)` | `root` is the `scenarios/` directory (`root / name / "tender.yaml"`). |
| R20 | `power_options` models and cooling | Models may have empty `cooling_nodes`. WS2 merges `size_cooling` output into each option model before `annotate_options` and `route`. |
| R21 | `p2.power_recheck` (spec v4.1) has no dedicated facade function | The step calls `engine.check(scn, model, erp)` on each annotated (still unrouted) option model and reports R01/R04/R04b. **WS1:** `check` must return `n/a` rather than raise for route-dependent rules on an unrouted model. |
| R22 | Revision identity vs golden capture (spec v4.1 §11) | `Revision.hash` is always `engine.model_hash(model)`, so WS4's `capture.py` gets identical hashes when it recomputes them. Approvals reference the revision through `Approval.revision`. |

---

## File Structure

```
services/api/
  kirchhoff/intake/__init__.py
  kirchhoff/intake/textnorm.py        normalize(); PDF_TEXT_KW (pdfplumber tolerances)
  kirchhoff/intake/tender_schema.py   TenderClause, TenderDoc, load_tender  (tender.yaml contract)
  kirchhoff/intake/render.py          render_tender_pdf; HallGeometry, load_geometry, render_drawing
  kirchhoff/intake/drawing.py         DrawingRead, DxfSummary, parse_dxf_geometry, compare_drawing
  kirchhoff/intake/verify.py          PdfText, QuoteCheck, value_in_quote, verify_quote
  kirchhoff/intake/score.py           GroundTruth, load_ground_truth, score_intake
  kirchhoff/intake/extract.py         TenderExtraction schemas, prompts, extract_tender, read_drawing
  kirchhoff/intake/brief.py           canonical_topology, build_brief
  kirchhoff/agents/__init__.py
  kirchhoff/agents/trust.py           digit allowlist: sanitize, is_clean, fill, fmt_value, allowed_ids_for
  kirchhoff/agents/runner.py          AgentSpec, AgentResult, AgentRunner, ReplayRunner, RecordingRunner, run_json, with_retries
  kirchhoff/agents/adk_runner.py      AdkRunner (ADK 2.11 Workflow + LlmAgent)
  kirchhoff/agents/genai_runner.py    GenaiRunner (google-genai; fallback + audio)
  kirchhoff/agents/specs.py           one AgentSpec per agent with instructions
  kirchhoff/agents/ports.py           EnterpriseClient protocol, ErpSnapshot, CRM constants
  kirchhoff/agents/copilot.py         load_revision, explain_finding, answer_voice
  kirchhoff/agents/asset.py           run_asset_pack
  kirchhoff/agents/docs_export.py     Exporter, StubExporter, BlobExporter, calc_report_pdf, boq_csv
  kirchhoff/runs/__init__.py
  kirchhoff/runs/compat.py            FixCandidate/ClashReport (re-export WS1's; fallback until it lands)
  kirchhoff/runs/storeops.py          transact, delete_tree, firestore_safe_problems
  kirchhoff/runs/leases.py            acquire_lease, heartbeat, release_lease, CapReached
  kirchhoff/runs/events.py            PhaseEventWriter, next_seq
  kirchhoff/runs/blobs.py             BlobStore, MemoryBlobStore, GcsBlobStore
  kirchhoff/runs/outputs.py           pack_outputs, load_outputs
  kirchhoff/runs/deps.py              Deps (all injectable dependencies), InputFiles
  kirchhoff/runs/steps.py             PhaseContext, run_step, StepOutput, PhaseOutcome, ParkAtGate, LeaseLost
  kirchhoff/runs/orchestrator.py      start_phase, resume_run, resume_from_gate, worker, heartbeats
  kirchhoff/runs/policy.py            choose_option, OWNER, lead_limit_weeks, PLAN_TEMPLATE
  kirchhoff/runs/revisions.py         build_revision, load_revision_model, diff_elements, latest_revision, gather_ledger
  kirchhoff/runs/phase1.py .. phase4.py
  kirchhoff/runs/fakes.py             FakeEngine, FakeEnterprise, FAKE_REPLIES, build_fake_scenarios, build_fake_deps
  kirchhoff/api/app.py                (modify) wire Deps + routers; optional enterprise proxy
  kirchhoff/api/deps.py               build_production_deps, LazyModule
  kirchhoff/api/workspace_routes.py   POST /api/workspace, /api/workspace/reset
  kirchhoff/api/runs_routes.py        POST /api/runs, gates, resume
  kirchhoff/api/copilot_routes.py     POST /api/what-if, /api/explain, /api/voice
  kirchhoff/api/asset_routes.py       POST /api/asset/{pack}
  kirchhoff/api/files_routes.py       GET /api/files/{path}
  tests/intake/fixtures/tender.yaml, tests/intake/fixtures/geometry.yaml
  tests/intake/test_intake_*.py, tests/agents/test_agents_*.py, tests/runs/test_runs_*.py, tests/api/test_api_*.py
  tests/agents/conftest.py, tests/runs/conftest.py, tests/api/conftest.py
scenarios/hall_a/
  render_tender_pdf.py  render_drawing.py  ground_truth.yaml
  out/tender-hall-a.pdf  out/hall-a.dxf  out/hall-a-plan.pdf      (generated, committed)
```

Test files use unique prefixes (`test_intake_*`, `test_runs_*`, …) because the test directories have no `__init__.py`.

**Schedule mapping:** Mon 13 → Tasks 1–3. Tue 14 → Tasks 4–11. Wed 15 → Tasks 12–13, then the full P1–P4 live run. Thu 16 → Tasks 14–18.

---

### Task 1: Tender schema, fixture and tender PDF renderer (Mon 13)

**Files:**
- Create: `services/api/kirchhoff/intake/__init__.py`, `services/api/kirchhoff/intake/textnorm.py`, `services/api/kirchhoff/intake/tender_schema.py`, `services/api/kirchhoff/intake/render.py`
- Create: `services/api/tests/intake/fixtures/tender.yaml`, `services/api/tests/intake/test_intake_render_tender.py`
- Create: `scenarios/hall_a/render_tender_pdf.py`; generated `scenarios/hall_a/out/tender-hall-a.pdf`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces:
  - `normalize(s: str) -> str` (NFKC, straight quotes, single spaces) and `PDF_TEXT_KW = {"x_tolerance": 1.5, "y_tolerance": 3}`. Every pdfplumber text call in WS2 passes these keyword arguments, because Helvetica 10 pt spaces are narrower than pdfplumber's default tolerance of 3.
  - `TenderClause(id, title, section: "main"|"appendix", page: int, text: str, limits: dict[str, float|int|str|list[str]])` and `TenderDoc(doc_id, title, client, reference, issued, clauses)` with `.clause(cid)` and `.limit(key)`. `load_tender(path) -> TenderDoc`.
  - `render_tender_pdf(tender: TenderDoc, out: Path) -> Path`. Each clause is placed on its declared page and the output is byte-for-byte deterministic.
  - **Contract for WS1 (R1):** `scenarios/hall_a/tender.yaml` must equal the fixture below (ids, pages, text, limits). Clause ids match `^(§\d+(\.\d+)*|App\. [A-Z])$`. Text is Latin-1 only (Helvetica): write "not exceed", not "≤"; "temperature rise", not "ΔT".

- [ ] **Step 1: Write the fixture tender**

`services/api/tests/intake/fixtures/tender.yaml`:
```yaml
doc_id: tender-hall-a
title: "Deccan AI Campus - AI Data Halls A and B: Electrical and Liquid Cooling Design-Build"
client: "Deccan Compute Pvt Ltd (fictional)"
reference: "DC-HYD-T-2026-014"
issued: "2026-09-29"
clauses:
  - id: "§1.1"
    title: "Scope of works"
    section: main
    page: 1
    text: >-
      The Contractor shall design, supply, install, test and commission the critical power
      distribution and the direct liquid cooling systems for each AI data hall of the Deccan AI
      Campus, including low-voltage switchboards, UPS systems, busways, coolant distribution units
      and pipework.
    limits: {}
  - id: "§1.2"
    title: "Site and hall"
    section: main
    page: 1
    text: >-
      The campus is located near Hyderabad, Telangana. Each hall is a single-storey space of 60 m
      by 36 m on a 12 m structural column grid, with low-voltage rooms outside the east and north walls.
    limits: {hall_length_m: 60, hall_width_m: 36, column_grid_m: 12}
  - id: "§2.1"
    title: "Form of contract"
    section: main
    page: 2
    text: >-
      The works shall be let as a single design-build package for each hall, awarded on a lump-sum basis.
    limits: {}
  - id: "§2.3"
    title: "Programme"
    section: main
    page: 2
    text: >-
      All major electrical and mechanical equipment shall be delivered to site within 26 weeks from the
      date of award. Equipment with a longer lead time shall not be proposed.
    limits: {max_lead_time_weeks: 26}
  - id: "§3.1"
    title: "IT load"
    section: main
    page: 3
    text: >-
      Each hall shall accommodate 48 racks in six rows. The design IT load is 132 kW per rack.
    limits: {racks: 48, rows: 6, rack_kw: 132}
  - id: "§3.2"
    title: "Heat rejection"
    section: main
    page: 3
    text: >-
      For design purposes, 80% of the rack heat shall be rejected to liquid and 20% to air.
    limits: {liquid_fraction_pct: 80, air_fraction_pct: 20}
  - id: "§4.1"
    title: "Supply"
    section: main
    page: 4
    text: >-
      The site is supplied at 33 kV from independent utility incomers A and B. Low-voltage distribution
      shall be 415 V, three phase, 50 Hz.
    limits: {mv_kv: 33, lv_v: 415, frequency_hz: 50}
  - id: "§4.2"
    title: "Redundancy"
    section: main
    page: 4
    text: >-
      The critical power system shall be 2N from the transformers to the rack power distribution units,
      with no single point of failure.
    limits: {redundancy: "2N"}
  - id: "§4.3"
    title: "Transformer loading"
    section: main
    page: 4
    text: >-
      Transformer loading shall not exceed 80% of rating in normal operation and shall not exceed 100% of
      rating under any single failure.
    limits: {tx_loading_normal_max_pct: 80, tx_loading_n1_max_pct: 100}
  - id: "§4.5"
    title: "UPS autonomy"
    section: main
    page: 4
    text: >-
      Each UPS system shall provide a battery autonomy of not less than 5 minutes at full design load.
    limits: {ups_autonomy_min_minutes: 5}
  - id: "§4.6"
    title: "Voltage drop"
    section: main
    page: 4
    text: >-
      The voltage drop from the UPS output board to the furthest busway tap-off shall not exceed 2.0% at
      the worst-case design current.
    limits: {dv_max_pct: 2.0}
  - id: "§5.1"
    title: "Standards"
    section: main
    page: 5
    text: >-
      The design shall follow IEC 60364, IEC 61439, IEC 60076 and ISO/IEC 22237, using the values stated
      in this tender where they differ.
    limits: {}
  - id: "§6.1"
    title: "Facility water"
    section: main
    page: 6
    text: >-
      The facility water supply temperature to the coolant distribution units shall be 30 °C, with a
      design temperature rise of 10 K across the racks.
    limits: {supply_temp_c: 30, delta_t_k: 10}
  - id: "§6.2"
    title: "Coolant distribution units"
    section: main
    page: 6
    text: >-
      Coolant distribution units shall be provided with N+1 redundancy in each hydraulic zone. The index
      circuit pressure drop shall be within the available external head of the units.
    limits: {cdu_redundancy: "N+1"}
  - id: "§6.3.4"
    title: "Containment"
    section: main
    page: 6
    text: >-
      No liquid-carrying pipework shall be routed above electrical busways, feeders or switchgear.
    limits: {liquid_above_electrical: "forbidden"}
  - id: "§6.4"
    title: "Velocity"
    section: main
    page: 6
    text: >-
      The coolant velocity in any pipe shall not exceed 2.5 m/s.
    limits: {pipe_velocity_max_mps: 2.5}
  - id: "§6.5"
    title: "Continuity of cooling"
    section: main
    page: 6
    text: >-
      Coolant distribution unit pumps shall be supplied from two independent UPS-backed power systems so
      that cooling continues on the loss of either system.
    limits: {cdu_pump_supplies: 2}
  - id: "App. B"
    title: "Alternative arrangements"
    section: appendix
    page: 7
    text: >-
      Block redundant or distributed redundant configurations of the critical power system are acceptable.
    limits: {redundancy_alternatives: ["BLOCK", "DR"]}
```

- [ ] **Step 2: Write the failing tests**

`services/api/tests/intake/test_intake_render_tender.py`:
```python
from pathlib import Path

import pdfplumber
import pytest
from pydantic import ValidationError

from kirchhoff.intake.render import render_tender_pdf
from kirchhoff.intake.tender_schema import TenderClause, load_tender
from kirchhoff.intake.textnorm import PDF_TEXT_KW, normalize

FIX = Path(__file__).parent / "fixtures"
REPO_TENDER = Path(__file__).resolve().parents[4] / "scenarios" / "hall_a" / "tender.yaml"


def test_fixture_has_contradiction_and_lead_time_limit():
    t = load_tender(FIX / "tender.yaml")
    assert t.clause("§4.2").limits["redundancy"] == "2N"
    assert t.clause("App. B").section == "appendix"
    assert t.limit("max_lead_time_weeks") == 26
    assert t.limit("dv_max_pct") == 2.0


def test_non_latin1_text_is_rejected():
    with pytest.raises(ValidationError):
        TenderClause(id="§9.9", title="x", section="main", page=1, text="ΔV ≤ 2%")


def test_appendix_id_must_match_section():
    with pytest.raises(ValidationError):
        TenderClause(id="App. C", title="x", section="main", page=1, text="ok")


def test_each_clause_renders_on_its_declared_page(tmp_path: Path):
    tender = load_tender(FIX / "tender.yaml")
    pdf = render_tender_pdf(tender, tmp_path / "tender.pdf")
    with pdfplumber.open(pdf) as doc:
        assert len(doc.pages) == max(c.page for c in tender.clauses)
        for c in tender.clauses:
            text = normalize(doc.pages[c.page - 1].extract_text(**PDF_TEXT_KW) or "")
            assert c.id in text, c.id
            assert normalize(c.text) in text, c.id


def test_render_is_deterministic(tmp_path: Path):
    tender = load_tender(FIX / "tender.yaml")
    a = render_tender_pdf(tender, tmp_path / "a.pdf").read_bytes()
    b = render_tender_pdf(tender, tmp_path / "b.pdf").read_bytes()
    assert a == b


@pytest.mark.skipif(not REPO_TENDER.exists(), reason="WS1 has not written scenarios/hall_a/tender.yaml yet")
def test_repo_tender_matches_fixture():
    def key(t):
        return [(c.id, c.page, c.section, normalize(c.text), c.limits) for c in t.clauses]
    assert key(load_tender(REPO_TENDER)) == key(load_tender(FIX / "tender.yaml"))
```

- [ ] **Step 3: Run to verify failure**

Run: `cd services/api && uv run pytest tests/intake/test_intake_render_tender.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'kirchhoff.intake'`

- [ ] **Step 4: Implement**

`services/api/kirchhoff/intake/__init__.py`:
```python
"""Tender intake: rendering the scenario documents, verified extraction, drawing cross-check, scoring."""
```

`services/api/kirchhoff/intake/textnorm.py`:
```python
import unicodedata

# Helvetica 10 pt word spaces (~2.8 pt) are narrower than pdfplumber's default x_tolerance of 3.
PDF_TEXT_KW = {"x_tolerance": 1.5, "y_tolerance": 3}

_TRANSLATE = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"',
                            "–": "-", "—": "-", " ": " "})


def normalize(s: str | None) -> str:
    """Canonical form for quote matching: NFKC, straight quotes, single spaces."""
    s = unicodedata.normalize("NFKC", s or "").translate(_TRANSLATE)
    return " ".join(s.split())
```

`services/api/kirchhoff/intake/tender_schema.py`:
```python
import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

CLAUSE_ID_RE = re.compile(r"^(§\d+(?:\.\d+)*|App\. [A-Z])$")
LimitValue = float | int | str | list[str]


class TenderClause(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    title: str
    section: Literal["main", "appendix"]
    page: int
    text: str
    limits: dict[str, LimitValue] = {}

    @field_validator("id")
    @classmethod
    def _id_format(cls, v: str) -> str:
        if not CLAUSE_ID_RE.match(v):
            raise ValueError(f"clause id {v!r} must look like '§4.6' or 'App. B'")
        return v

    @field_validator("title", "text")
    @classmethod
    def _latin1(cls, v: str) -> str:
        try:
            v.encode("latin-1")
        except UnicodeEncodeError as exc:
            raise ValueError(f"text must be Latin-1 (Helvetica): {exc.object[exc.start:exc.end]!r}") from exc
        return v

    @model_validator(mode="after")
    def _section_matches_id(self) -> "TenderClause":
        if (self.section == "appendix") != self.id.startswith("App. "):
            raise ValueError(f"clause {self.id}: appendix ids start with 'App. ' and only they")
        return self


class TenderDoc(BaseModel):
    model_config = ConfigDict(extra="ignore")
    doc_id: str
    title: str
    client: str
    reference: str
    issued: str
    clauses: list[TenderClause]

    @model_validator(mode="after")
    def _ordering(self) -> "TenderDoc":
        ids = [c.id for c in self.clauses]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate clause ids")
        pages = [c.page for c in self.clauses]
        if pages != sorted(pages) or pages[0] != 1:
            raise ValueError("clauses must be in page order starting on page 1")
        return self

    def clause(self, cid: str) -> TenderClause:
        return next(c for c in self.clauses if c.id == cid)

    def limit(self, key: str) -> LimitValue:
        return next(c.limits[key] for c in self.clauses if key in c.limits)


def load_tender(path: Path | str) -> TenderDoc:
    return TenderDoc.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))
```

`services/api/kirchhoff/intake/render.py`:
```python
"""Renders the scenario documents (tender PDF here; hall drawing added in Task 2). No LLM."""
from pathlib import Path
from xml.sax.saxutils import escape

from .tender_schema import TenderDoc


def render_tender_pdf(tender: TenderDoc, out: Path) -> Path:
    from reportlab import rl_config

    rl_config.invariant = 1  # deterministic bytes (no timestamps / random ids)
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    title_s = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=16, leading=20, spaceAfter=6)
    meta_s = ParagraphStyle("m", fontName="Helvetica", fontSize=9.5, leading=13, textColor="#444444")
    head_s = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=11, leading=14, spaceBefore=10,
                            spaceAfter=3, alignment=TA_LEFT)
    body_s = ParagraphStyle("b", fontName="Helvetica", fontSize=10, leading=14, alignment=TA_LEFT)

    story = [
        Paragraph(escape(tender.title), title_s),
        Paragraph(escape(f"Client: {tender.client}"), meta_s),
        Paragraph(escape(f"Tender reference: {tender.reference} · Issued {tender.issued}"), meta_s),
        Paragraph("Fictional tender authored for the Kirchhoff demo. Illustrative values, not for construction.",
                  meta_s),
        Spacer(1, 8 * mm),
    ]
    page = 1
    for c in tender.clauses:
        while page < c.page:
            story.append(PageBreak())
            page += 1
        story.append(Paragraph(escape(f"{c.id}  {c.title}"), head_s))
        story.append(Paragraph(escape(c.text), body_s))

    def footer(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawString(22 * mm, 12 * mm, f"{tender.reference} · {tender.client} · Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(out), pagesize=A4, title=tender.title, author=tender.client,
                            leftMargin=22 * mm, rightMargin=22 * mm, topMargin=22 * mm, bottomMargin=22 * mm)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return out
```

`scenarios/hall_a/render_tender_pdf.py`:
```python
"""Render the Hall A tender PDF from tender.yaml.

Run from the repo root:
  cd services/api && uv run python ../../scenarios/hall_a/render_tender_pdf.py [--tender PATH]
"""
import argparse
from pathlib import Path

from kirchhoff.intake.render import render_tender_pdf
from kirchhoff.intake.tender_schema import load_tender

HERE = Path(__file__).resolve().parent

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tender", type=Path, default=HERE / "tender.yaml")
    ap.add_argument("--out", type=Path, default=HERE / "out" / "tender-hall-a.pdf")
    args = ap.parse_args()
    print(render_tender_pdf(load_tender(args.tender), args.out))
```

- [ ] **Step 5: Run tests**

Run: `cd services/api && uv run pytest tests/intake/test_intake_render_tender.py -q`
Expected: `5 passed, 1 skipped` (the skip turns into a pass once WS1's `tender.yaml` exists and matches).

- [ ] **Step 6: Generate the committed PDF**

Run: `cd services/api && uv run python ../../scenarios/hall_a/render_tender_pdf.py --tender tests/intake/fixtures/tender.yaml`
Expected: prints `.../scenarios/hall_a/out/tender-hall-a.pdf`. Once WS1's `tender.yaml` exists, re-run without `--tender`; the bytes must not change.

- [ ] **Step 7: Commit**

```bash
git add services/api/kirchhoff/intake services/api/tests/intake scenarios/hall_a/render_tender_pdf.py scenarios/hall_a/out/tender-hall-a.pdf
git commit -m "feat(intake): tender.yaml schema, fixture and deterministic tender PDF renderer

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---
