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
- WS2 creates or modifies only the files that `2026-10-13-interfaces.md` assigns to it (incl. `services/api/kirchhoff/store/**`, which WS2 owns after the P0 fix wave), plus these shared edits listed explicitly: `services/api/pyproject.toml` (one dependency), removing the P0 hello route and its test (never `GET /api/whoami`, which is permanent), and the EventWriter hardening in Task 6 (announced to all workstreams).
- Store and event APIs are the P0 fix-wave ones (interfaces doc, "Conventions"): `Store.transact(read_paths, fn) -> list[Write]` (`fn` gets `{path: doc | None}` and returns `[(path, data | None)]`; an empty list writes nothing), `Store.delete_tree(path)`, `Store.list_docs(collection, order_by=, descending=, limit=)`, deep-merge `update_doc`, `kirchhoff.store.validate.firestore_safe_problems`, and `EventWriter.emit(agent, kind, title, detail="", payload=None, step=None)` plus `fence()`. Never subclass `EventWriter`, never touch private attributes of `EventWriter`, `MemoryStore` or `FirestoreStore`, and never rely on `set_step` across threads: every event passes `step=` explicitly.

## Rulings on spec ambiguities (binding for this plan; communicated to WS1/WS3/WS4)

| # | Ambiguity | Ruling |
|---|---|---|
| R1 | Exact `tender.yaml` shape | WS1's file (P1 engine plan, Task 1) is the schema: `doc_id, title, client, site, reference, notice, clauses[{id, title, page, text, quote, limits}]`. Section is derived from the id (`App. ` = appendix). The WS2 fixture is a verbatim copy and a drift test enforces equality. The renderer puts each clause on its `page` and reproduces `text`, and therefore `quote`, verbatim. |
| R2 | Drawing inputs and grid labels | WS2 reads WS1's `geometry.yaml` keys `hall`, `columns`, `keepouts[].rect`, `rooms.*.rect`, `gallery`, `rows[].{id,x}` and `racks.{per_row,w,d,y_south,y_north}`. WS1 authors no grid labels, so the renderer generates them: `1…n` west to east and `A…` south to north. |
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
| R20 | `power_options` models and cooling | WS1 confirms that `power_options` models already contain `cooling_nodes`. WS2 merges `size_cooling` output only when a model's list is empty (a guard for fakes), and calls `route` once per option. |
| R21 | `p2.power_recheck` (spec v4.1) | The step calls the facade's `power_recheck(scn, model) -> list[Finding]` (R01, R04 and R04b; WS1 P1 plan Task 8) on each swapped option, and reports `ikss_ka_before`/`ikss_ka_after` from the swap records (`{line, from, to, qty, reason, ikss_ka_before, ikss_ka_after, ...}`). |
| R22 | Revision identity vs golden capture (spec v4.1 §11) | `Revision.hash` is always `engine.model_hash(model)`, so WS4's `capture.py` gets identical hashes when it recomputes them. Approvals reference the revision through `Approval.revision`. |
| R23 | Fix-choice criteria (coordinator ruling) | **Cooling** prefers the candidate with the fewest changed pipe segments (`metrics.changed_pipes`, least disruption to coordinated routes) and breaks ties by cost, which selects `H-Z2:local-drop` (+$420) over `H-Z2:reroute` (−$910), matching the storyboard. **Power** prefers the largest ΔV margin per dollar, `(dv_limit_pct − dv_pct) / max(cost_delta, 1)`. Each criterion appears in the agent instruction (`FIX_CRITERIA`), is stored as `finding.fix.criterion`, is named in the fix reason, and drives the deterministic fallback when the agent fails. |
| R24 | `what_if` payload | The engine returns only `fail`/`warn` findings plus the impact chain. Co-pilot summaries count only `fail`. |
| R25 | Store and event APIs (P0 fix wave, reconciliation 13 Oct) | `Store.transact/delete_tree/list_docs(order_by, descending, limit)`, `kirchhoff.store.validate.firestore_safe_problems`, plain `EventWriter.emit(..., step=...)` and `fence()` on lease loss. No `storeops.py`, no `PhaseEventWriter`, no private attributes. WS2 owns `kirchhoff/store/**` and hardens `EventWriter` in Task 6 (RLock + atomic `set_step`, trailing-flush backoff, close flag). |
| R26 | Artifact refs (WS3 ruling R7) | `brief` → Firestore path `workspaces/{uid}/runs/{rid}/outputs/p1.intake` (doc `{step, json}`; the UI parses `json` and reads `brief`); `options` → the run doc path (options live on `runs/{rid}.options`, the payload also carries `recommended`); `revision` → `workspaces/{uid}/revisions/{rev}` (ref tail = revision id) plus `changed`; `export` → storage path `exports/{rev}/{file}` served by `/api/files`, emitted only once the file exists (pending stubs emit a `status` event). |
| R27 | Finding events (WS3 ruling R8) | Each `p3.check.{n}` step emits the revision artifact first, then one `finding` event per failure with payload `{finding_id, rule_id, element_id, status, rev}`; P4's R12 finding also carries `rev`. |
| R28 | `/api/files` from the browser | `?redirect=0` returns `{url, expires_in}` so the browser fetches the signed URL without auth headers (no CORS preflight); the bare route still 302s. Unsigned local blob stores serve bytes inline. |
| R29 | Voice response shape (WS3 ruling R9) | `tool_results: [{name, args, result}]`; `explain_finding` accepts `finding_id` or `element_id` (same parameters as WS3's Live declarations). |
| R30 | Placeholder units | WS1's explanation templates already carry units after `{value}`/`{limit}`; `fill_finding` appends the unit only when the text does not already have it (WS3's `fillPlaceholders` uses the same rule). |
| R31 | Fix deltas | `fix.deltas` / `rejected_fix.deltas` = candidate metrics + `cost_delta` (the UI lists `deltas`); `cost_delta` also stays top-level. |
| R32 | Tender chip boxes | The engine cites (page, verbatim quote) without a box; `with_citation_boxes` adds pdfplumber's `bbox` to every finding's `tender_refs` before the revision is written. |
| R33 | Asset packs | `POST /api/asset/{pack}` returns `{options, recommended, findings, geometry, choice: {option, reason, source}}` and writes nothing to Firestore (no run, no events). The static grid/solar bundles' `evaluate_grid`/`evaluate_solar` `tool_result` events are WS4's (generated from this same dict). |
| R34 | Plan-gate answers | An answer must be one of `OpenQuestion.options` (`[main-body value, "compare_all"]`), else 422 `invalid_answer`; the UI offers only those options (no free text). |

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
  kirchhoff/store/events.py           (modify, Task 6) EventWriter hardening: RLock, atomic set_step, flush backoff, close flag
  kirchhoff/runs/leases.py            acquire_lease, heartbeat, release_lease, CapReached (on Store.transact)
  kirchhoff/runs/events.py            next_seq (events are written by the P0 EventWriter with emit(..., step=...))
  kirchhoff/runs/blobs.py             BlobStore, MemoryBlobStore, GcsBlobStore
  kirchhoff/runs/outputs.py           pack_outputs, load_outputs
  kirchhoff/runs/deps.py              Deps (all injectable dependencies), InputFiles
  kirchhoff/runs/steps.py             PhaseContext, run_step, StepOutput, PhaseOutcome, ParkAtGate, LeaseLost
  kirchhoff/runs/orchestrator.py      start_phase, resume_run, resume_from_gate, worker, heartbeats
  kirchhoff/runs/policy.py            choose_option, OWNER, lead_limit_weeks, PLAN_TEMPLATE
  kirchhoff/runs/revisions.py         build_revision, load_revision_model, diff_elements, latest_revision, gather_ledger
  kirchhoff/runs/phase1.py .. phase4.py
  kirchhoff/runs/fakes.py             FakeEngine, FakeEnterprise, FAKE_REPLIES, build_fake_scenarios, build_fake_deps, CheckedStore
  kirchhoff/api/app.py                (modify) wire Deps + routers; optional enterprise proxy
  kirchhoff/api/deps.py               build_production_deps, LazyModule
  kirchhoff/api/errors.py             err(status, detail, **extra) -> JSONResponse
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

**Schedule mapping:** Mon 13 (tonight) → Tasks 1–3. Tue 14 → Tasks 4–11, then Task 12 (API). Wed 15 → Tasks 12–14, then the full P1–P4 live run (Task 14 Step 6). Thu 16 → Tasks 15–18. Golden-path freeze: Thu 22:00 IST.

---

### Task 1: Tender schema (WS1's `tender.yaml`), fixture and tender PDF renderer (Mon 13)

**Files:**
- Create: `services/api/kirchhoff/intake/__init__.py`, `services/api/kirchhoff/intake/textnorm.py`, `services/api/kirchhoff/intake/tender_schema.py`, `services/api/kirchhoff/intake/render.py`
- Create: `services/api/tests/intake/fixtures/tender.yaml`, `services/api/tests/intake/test_intake_render_tender.py`
- Create: `scenarios/hall_a/render_tender_pdf.py`; generated `scenarios/hall_a/out/tender-hall-a.pdf`

**Interfaces:**
- Consumes: the `scenarios/hall_a/tender.yaml` schema from the WS1 plan (`2026-10-13-p1-engine.md`, Task 1): `doc_id, title, client, site, reference, notice, clauses: [{id, title, page, text, quote, limits}]`. `quote` is a verbatim substring of `text`.
- Produces:
  - `normalize(s: str) -> str` (NFKC, straight quotes, single spaces) and `PDF_TEXT_KW = {"x_tolerance": 1.5, "y_tolerance": 3}`. Every pdfplumber text call in WS2 passes these, because Helvetica 10 pt spaces are narrower than pdfplumber's default tolerance of 3.
  - `TenderClause(id, title, page, text, quote, limits)` with property `.section -> "main" | "appendix"` (`App. ` prefix). Validators: the id matches `^(§\d+(\.\d+)*|App\. [A-Z])$`; text is Latin-1 (Helvetica); `quote` is in `text`.
  - `TenderDoc(doc_id, title, client, site, reference, notice, clauses)` with `.clause(cid)`, `.limit(key)` and `load_tender(path)`. Extra keys are ignored.
  - `render_tender_pdf(tender, out) -> Path`. Each clause goes on its declared `page`, its `text` (and therefore its `quote`) is reproduced verbatim, and the bytes are deterministic.
  - The fixture is a verbatim copy of WS1's `tender.yaml`. `test_repo_tender_matches_fixture` fails on drift once WS1's file exists; WS1's file is authoritative, so on drift re-copy it into the fixture and update `ground_truth.yaml` and `FAKE_REPLIES`.

- [ ] **Step 1: Copy WS1's tender into the fixture**

`services/api/tests/intake/fixtures/tender.yaml` (verbatim from the WS1 plan; if `scenarios/hall_a/tender.yaml` already exists, `cp` it instead):
```yaml
# Hall A tender (fictional, authored for the Kirchhoff demo).
# Single source for the rendered tender PDF (WS2 renders each clause on `page`) and for engine limits.
# `quote` is a verbatim substring of `text` that contains the clause's key value (used for citations).
doc_id: tender-hall-a
title: "Deccan AI Campus, Hall A: electrical and liquid-cooling design-build, technical requirements"
client: "Deccan Compute (fictional)"
site: "AI campus near Hyderabad (fictional)"
reference: "DC-HA-TS-001 Rev 0"
notice: "Fictional tender authored for the Kirchhoff demo. IEC-based, illustrative, not for construction."
clauses:
  - id: "§1.1"
    title: "Scope of works"
    page: 1
    text: >-
      The contractor shall design, supply, install and commission the electrical power distribution and the
      direct liquid cooling for Data Hall A, from the 33 kV main switchboard to the rack power inlets and the
      rack coolant manifolds.
    quote: "from the 33 kV main switchboard to the rack power inlets"
    limits: {}
  - id: "§2.3"
    title: "Programme"
    page: 2
    text: >-
      All major electrical and mechanical equipment shall be on site no later than 26 weeks from contract
      award. Equipment that cannot be delivered within this period shall not be specified.
    quote: "no later than 26 weeks from contract award"
    limits: {max_lead_time_weeks: 26}
  - id: "§3.1"
    title: "IT load"
    page: 3
    text: >-
      The hall shall accommodate 48 racks in 6 rows of 8, each rack rated 132 kW. For design purposes 80% of
      rack heat is rejected to liquid and 20% to air.
    quote: "each rack rated 132 kW"
    limits: {racks: 48, rows: 6, racks_per_row: 8, rack_kw: 132, liquid_fraction: 0.8}
  - id: "§3.2"
    title: "Auxiliary load"
    page: 3
    text: >-
      Auxiliary load on the LV system, including CDU pumps, fan walls and controls, shall be taken as 0.30 MW
      in total. CDU pumps are UPS-backed; other auxiliary loads are not.
    quote: "shall be taken as 0.30 MW in total"
    limits: {aux_mw: 0.30}
  - id: "§3.3"
    title: "Electrical supply"
    page: 3
    text: >-
      Supply is at 33 kV, 50 Hz, from a main switchboard with two incomers and an automatic bus-coupler; the
      source fault level is 1,000 MVA with R/X 0.1. Distribution is at 415 V with a design power factor of 0.95.
    quote: "the source fault level is 1,000 MVA"
    limits: {mv_kv: 33, lv_v: 415, freq_hz: 50, source_sk_mva: 1000, source_rx: 0.1, pf: 0.95}
  - id: "§4.2"
    title: "Redundancy"
    page: 4
    text: "The critical power distribution shall be 2N, with each rack fed from two independent systems."
    quote: "shall be 2N"
    limits: {}
  - id: "§4.3"
    title: "Transformer loading"
    page: 4
    text: >-
      Transformer loading shall not exceed 80% of rating in normal operation and 100% of rating under any
      single failure.
    quote: "shall not exceed 80% of rating in normal operation"
    limits: {tx_normal_max_pct: 80, tx_n1_max_pct: 100}
  - id: "§4.4"
    title: "Short-circuit ratings"
    page: 4
    text: >-
      Switchgear and busways shall be rated for the maximum prospective short-circuit current at their point
      of installation.
    quote: "rated for the maximum prospective short-circuit current"
    limits: {}
  - id: "§4.5"
    title: "UPS"
    page: 4
    text: >-
      Each UPS system shall carry its worst single-failure load with a battery autonomy of not less than
      5 minutes.
    quote: "not less than 5 minutes"
    limits: {ups_autonomy_min: 5}
  - id: "§4.6"
    title: "Voltage drop"
    page: 4
    text: >-
      The voltage drop from the UPS output board to the furthest busway tap-off shall not exceed 2.0% at the
      worst-case design current.
    quote: "shall not exceed 2.0%"
    limits: {dv_max_pct: 2.0}
  - id: "§5.1"
    title: "Containment tiers"
    page: 5
    text: >-
      Overhead services shall run on three tiers: low-level pipework at 2.6 m, busways at 3.2 m and
      mechanical mains at 3.8 m above finished floor.
    quote: "mechanical mains at 3.8 m"
    limits: {tier_pipe_low_m: 2.6, tier_busway_m: 3.2, tier_pipe_high_m: 3.8}
  - id: "§6.1"
    title: "Coolant"
    page: 6
    text: >-
      Coolant supply temperature shall be 30 °C with a design temperature rise of 10 K across each rack.
    quote: "design temperature rise of 10 K"
    limits: {supply_temp_c: 30, delta_t_k: 10}
  - id: "§6.2"
    title: "CDU redundancy and pressure"
    page: 6
    text: >-
      CDUs shall be provided N+1 per hydraulic zone. The index-circuit pressure drop shall be within the CDU
      available external head.
    quote: "CDUs shall be provided N+1 per hydraulic zone"
    limits: {cdu_spare_per_zone: 1}
  - id: "§6.3.4"
    title: "Liquid above electrical"
    page: 6
    text: >-
      No liquid-carrying pipework shall be routed above electrical busways or feeders. Pipework shall keep a
      clearance of at least 300 mm from structural columns.
    quote: "No liquid-carrying pipework shall be routed above electrical busways"
    limits: {column_clearance_mm: 300}
  - id: "§6.4"
    title: "Velocity"
    page: 6
    text: "Coolant velocity in any pipe shall not exceed 2.5 m/s."
    quote: "shall not exceed 2.5 m/s"
    limits: {pipe_velocity_max_ms: 2.5}
  - id: "§6.5"
    title: "Continuous cooling"
    page: 6
    text: "CDU pumps shall be fed from two independent UPS-backed supplies to maintain continuous cooling."
    quote: "two independent UPS-backed supplies"
    limits: {}
  - id: "App. B"
    title: "Appendix B: acceptable alternatives"
    page: 7
    text: "Block or distributed redundancy acceptable, subject to the loading limits of §4.3."
    quote: "Block or distributed redundancy acceptable"
    limits: {}
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
    assert "2N" in t.clause("§4.2").text and t.clause("§4.2").section == "main"
    assert t.clause("App. B").section == "appendix"
    assert t.limit("max_lead_time_weeks") == 26 and t.limit("dv_max_pct") == 2.0


def test_non_latin1_text_is_rejected():
    with pytest.raises(ValidationError):
        TenderClause(id="§9.9", title="x", page=1, text="ΔV ≤ 2%", quote="2%")


def test_quote_must_be_verbatim_in_text():
    with pytest.raises(ValidationError):
        TenderClause(id="§9.9", title="x", page=1, text="shall not exceed 2.0%", quote="shall not exceed 2.5%")


def test_bad_clause_id_is_rejected():
    with pytest.raises(ValidationError):
        TenderClause(id="4.6", title="x", page=1, text="shall not exceed 2.0%", quote="2.0%")


def test_each_clause_and_quote_render_on_the_declared_page(tmp_path: Path):
    tender = load_tender(FIX / "tender.yaml")
    pdf = render_tender_pdf(tender, tmp_path / "tender.pdf")
    with pdfplumber.open(pdf) as doc:
        assert len(doc.pages) == max(c.page for c in tender.clauses)
        for c in tender.clauses:
            text = normalize(doc.pages[c.page - 1].extract_text(**PDF_TEXT_KW) or "")
            assert c.id in text, c.id
            assert normalize(c.text) in text and normalize(c.quote) in text, c.id


def test_render_is_deterministic(tmp_path: Path):
    tender = load_tender(FIX / "tender.yaml")
    a = render_tender_pdf(tender, tmp_path / "a.pdf").read_bytes()
    b = render_tender_pdf(tender, tmp_path / "b.pdf").read_bytes()
    assert a == b


@pytest.mark.skipif(not REPO_TENDER.exists(), reason="WS1 has not written scenarios/hall_a/tender.yaml yet")
def test_repo_tender_matches_fixture():
    def key(t):
        return [t.doc_id] + [(c.id, c.page, normalize(c.text), c.quote, c.limits) for c in t.clauses]
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
"""Reader for WS1's scenarios/hall_a/tender.yaml (P1 engine plan, Task 1)."""
import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from .textnorm import normalize

CLAUSE_ID_RE = re.compile(r"^(§\d+(?:\.\d+)*|App\. [A-Z])$")
LimitValue = float | int | str | list[str]


class TenderClause(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    title: str
    page: int
    text: str
    quote: str
    limits: dict[str, LimitValue] = {}

    @property
    def section(self) -> str:
        return "appendix" if self.id.startswith("App. ") else "main"

    @field_validator("id")
    @classmethod
    def _id_format(cls, v: str) -> str:
        if not CLAUSE_ID_RE.match(v):
            raise ValueError(f"clause id {v!r} must look like '§4.6' or 'App. B'")
        return v

    @field_validator("title", "text", "quote")
    @classmethod
    def _latin1(cls, v: str) -> str:
        try:
            v.encode("latin-1")
        except UnicodeEncodeError as exc:
            raise ValueError(f"text must be Latin-1 (Helvetica): {exc.object[exc.start:exc.end]!r}") from exc
        return v

    @model_validator(mode="after")
    def _quote_in_text(self) -> "TenderClause":
        if normalize(self.quote) not in normalize(self.text):
            raise ValueError(f"clause {self.id}: quote is not a verbatim substring of text")
        return self


class TenderDoc(BaseModel):
    model_config = ConfigDict(extra="ignore")
    doc_id: str
    title: str
    client: str
    site: str = ""
    reference: str
    notice: str = ""
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

import yaml
from pydantic import BaseModel, ConfigDict

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

    story = [Paragraph(escape(tender.title), title_s), Paragraph(escape(f"Client: {tender.client}"), meta_s)]
    if tender.site:
        story.append(Paragraph(escape(f"Site: {tender.site}"), meta_s))
    story.append(Paragraph(escape(f"Reference: {tender.reference}"), meta_s))
    story.append(Paragraph(escape(tender.notice or "Fictional tender authored for the Kirchhoff demo."), meta_s))
    story.append(Spacer(1, 8 * mm))
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
Expected: `6 passed, 1 skipped` (the skip turns into a pass once WS1's `tender.yaml` exists and matches).

- [ ] **Step 6: Generate the committed PDF**

Run: `cd services/api && uv run python ../../scenarios/hall_a/render_tender_pdf.py --tender tests/intake/fixtures/tender.yaml`
Expected: prints `.../scenarios/hall_a/out/tender-hall-a.pdf`. Once WS1's `tender.yaml` exists, re-run without `--tender`; the bytes must not change.

- [ ] **Step 7: Commit**

```bash
git add services/api/kirchhoff/intake services/api/tests/intake scenarios/hall_a/render_tender_pdf.py scenarios/hall_a/out/tender-hall-a.pdf
git commit -m "feat(intake): tender.yaml reader, fixture and deterministic tender PDF renderer

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Hall drawing (DXF + PDF plot), DXF parser and drawing cross-check (Mon 13)

**Files:**
- Modify: `services/api/kirchhoff/intake/render.py` (append the drawing renderer)
- Create: `services/api/kirchhoff/intake/drawing.py`
- Create: `services/api/tests/intake/fixtures/geometry.yaml`, `services/api/tests/intake/test_intake_drawing.py`
- Create: `scenarios/hall_a/render_drawing.py`; generated `scenarios/hall_a/out/hall-a.dxf`, `scenarios/hall_a/out/hall-a-plan.pdf`

**Interfaces:**
- Consumes: `normalize`, `PDF_TEXT_KW` (Task 1); the `scenarios/hall_a/geometry.yaml` schema from the WS1 plan (Task 1). This task reads `hall: [x0, y0, x1, y1]`, `columns: {xs, ys}`, `keepouts: [{id, name, rect}]`, `rooms: {A: {rect, ...}}`, `gallery: [x0, y0, x1, y1]`, `rows: [{id, x, zone}]` and `racks: {per_row, w, d, y_south, y_north}`; other keys are ignored.
- Produces:
  - `HallGeometry` (pydantic) with `.labels_x()` (`"1"…`, west to east) and `.labels_y()` (`"A"…`, south to north); `load_geometry(path) -> HallGeometry`. Grid labels are generated by the renderer because WS1 does not author them (R2).
  - `render_drawing(geom, dxf_out: Path, pdf_out: Path) -> tuple[Path, Path]`. The DXF is in millimetres with layers `HALL, COLUMNS, GRID, GRID_X, GRID_Y, KEEPOUT, ROOMS, RACKS, CDU, DIMS`. The PDF plot is A3 landscape with grid bubbles and overall dimension text in mm.
  - `DrawingRead(grid_x: list[str], grid_y: list[str], overall_mm: list[float])`, which is what Gemini returns in Task 9.
  - `DxfSummary(grid_x, grid_y, overall_mm: tuple[float, float])`; `parse_dxf_geometry(path) -> DxfSummary`.
  - `compare_drawing(read, dxf, tol_mm=50.0) -> dict` returning `{"agrees", "differences", "grid_x", "grid_y", "overall_mm"}` (stored as `DesignBrief.drawing_check`).

- [ ] **Step 1: Copy WS1's geometry into the fixture**

`services/api/tests/intake/fixtures/geometry.yaml` (verbatim from the WS1 plan; if `scenarios/hall_a/geometry.yaml` already exists, `cp` it instead):
```yaml
# Hall A pinned geometry (spec §9.1, v4.1). Metres; x east, y north; origin at the hall's south-west corner.
# Tiers: pipe_low 2.6, busway 3.2, pipe_high 3.8. Header polylines are authored so that exactly one
# header segment (H-Z2) crosses above an electrical run (feeder FB-03, at about y 24); locked by tests.
label: "IEC-based, illustrative, not for construction"
hall: [0.0, 0.0, 60.0, 36.0]
columns: {xs: [0, 12, 24, 36, 48, 60], ys: [0, 12, 24, 36]}
keepouts:
  - {id: KO-1, name: "Fire-suppression room", rect: [10.0, 10.0, 18.0, 26.0]}
rooms:
  A: {rect: [60.0, 0.0, 72.0, 10.0], exit: [66.0, 4.0], corridor: south}
  B: {rect: [24.0, 36.0, 36.0, 46.0], exit: [30.0, 40.0], corridor: north}
gallery: [0.0, 28.0, 60.0, 33.0]
tiers: {pipe_low: 2.6, busway: 3.2, pipe_high: 3.8}
rows:
  - {id: R1, x: 6.0, zone: Z1}
  - {id: R2, x: 22.0, zone: Z1}
  - {id: R3, x: 28.0, zone: Z2}
  - {id: R4, x: 34.0, zone: Z2}
  - {id: R5, x: 40.0, zone: Z3}
  - {id: R6, x: 46.0, zone: Z3}
racks: {per_row: 8, w: 0.6, d: 1.2, y_south: 15.6, y_north: 20.4}
busways: {offset_a: -0.3, offset_b: 0.3, taps: 8}
corridors:
  south: {y_outer: 2.0, pitch: 0.4, row_end_y: 15.6}
  north: {y_outer: 35.0, pitch: -0.4, row_end_y: 20.4}
feeder_vertical_allowance_m: 6.4   # 2 x 3.2 m vertical (spec §9.1)
zones:
  Z1: {rows: [R1, R2], bay: [7.0, 28.0, 21.0, 33.0]}
  Z2: {rows: [R3, R4], bay: [28.6, 28.0, 33.4, 33.0]}
  Z3: {rows: [R5, R6], bay: [40.6, 28.0, 45.4, 33.0]}
cdu_y: 31.0
manifold_y: 21.0
pipes:
  headers:   # zone main headers on pipe_high; first point is the CDU outlet riser
    H-Z1: [[8.0, 30.5, 1.2], [8.0, 30.5, 3.8], [20.0, 30.5, 3.8], [20.0, 21.0, 3.8]]
    H-Z2: [[31.0, 30.5, 1.2], [31.0, 30.5, 3.8], [31.0, 24.0, 3.8], [26.0, 24.0, 3.8], [26.0, 21.0, 3.8]]
    H-Z3: [[43.0, 30.5, 1.2], [43.0, 30.5, 3.8], [43.0, 21.0, 3.8]]
  branches:  # row branches on pipe_low; first point is the take-off on the header
    BR-R1: [[8.0, 30.5, 3.8], [8.0, 30.5, 2.6], [6.0, 30.5, 2.6], [6.0, 15.6, 2.6]]
    BR-R2: [[20.0, 21.0, 3.8], [20.0, 21.0, 2.6], [22.0, 21.0, 2.6], [22.0, 15.6, 2.6]]
    BR-R3: [[26.0, 21.0, 3.8], [26.0, 21.0, 2.6], [28.0, 21.0, 2.6], [28.0, 15.6, 2.6]]
    BR-R4: [[31.0, 24.0, 3.8], [31.0, 24.0, 2.6], [34.0, 24.0, 2.6], [34.0, 15.6, 2.6]]
    BR-R5: [[43.0, 21.0, 3.8], [43.0, 21.0, 2.6], [40.0, 21.0, 2.6], [40.0, 15.6, 2.6]]
    BR-R6: [[43.0, 21.0, 3.8], [43.0, 21.0, 2.6], [46.0, 21.0, 2.6], [46.0, 15.6, 2.6]]
reroutes:    # authored alternative routes offered as R11 "reroute" fix candidates
  H-Z2:
    H-Z2: [[31.0, 30.5, 1.2], [31.0, 30.5, 3.8], [31.0, 21.0, 3.8]]
    BR-R3: [[31.0, 21.0, 3.8], [31.0, 21.0, 2.6], [28.0, 21.0, 2.6], [28.0, 15.6, 2.6]]
```

- [ ] **Step 2: Write the failing tests**

`services/api/tests/intake/test_intake_drawing.py`:
```python
from pathlib import Path

import pdfplumber
import pytest

from kirchhoff.intake.drawing import DrawingRead, compare_drawing, parse_dxf_geometry
from kirchhoff.intake.render import load_geometry, render_drawing

FIX = Path(__file__).parent / "fixtures"
REPO_GEOMETRY = Path(__file__).resolve().parents[4] / "scenarios" / "hall_a" / "geometry.yaml"


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    out = tmp_path_factory.mktemp("drawing")
    return render_drawing(load_geometry(FIX / "geometry.yaml"), out / "hall.dxf", out / "plan.pdf")


def test_dxf_round_trip_reads_grid_and_overall_size(rendered):
    s = parse_dxf_geometry(rendered[0])
    assert s.grid_x == ["1", "2", "3", "4", "5", "6"]
    assert s.grid_y == ["A", "B", "C", "D"]
    assert s.overall_mm == (60000.0, 36000.0)


def test_pdf_plot_shows_labels_and_overall_dimensions(rendered):
    with pdfplumber.open(rendered[1]) as doc:
        assert len(doc.pages) == 1
        chars = "".join(ch["text"] for ch in doc.pages[0].chars)
    for token in ["60000", "36000", "GA-E-101", "GALLERY", "R6"]:  # no spaces: char joins may drop them
        assert token in chars, token


def test_compare_agrees_when_reading_matches(rendered):
    read = DrawingRead(grid_x=["1", "2", "3", "4", "5", "6"], grid_y=["A", "B", "C", "D"],
                       overall_mm=[60000, 36000])
    result = compare_drawing(read, parse_dxf_geometry(rendered[0]))
    assert result["agrees"] is True and result["differences"] == []


def test_compare_reports_differences(rendered):
    read = DrawingRead(grid_x=["1", "2", "3", "4", "5"], grid_y=["A", "B", "C", "D"], overall_mm=[60000, 30000])
    result = compare_drawing(read, parse_dxf_geometry(rendered[0]))
    assert result["agrees"] is False
    assert any("grid x" in d for d in result["differences"])
    assert any("width" in d for d in result["differences"])


@pytest.mark.skipif(not REPO_GEOMETRY.exists(), reason="WS1 has not written scenarios/hall_a/geometry.yaml yet")
def test_repo_geometry_matches_fixture():
    assert load_geometry(REPO_GEOMETRY) == load_geometry(FIX / "geometry.yaml")
```

- [ ] **Step 3: Run to verify failure**

Run: `cd services/api && uv run pytest tests/intake/test_intake_drawing.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'kirchhoff.intake.drawing'`

- [ ] **Step 4: Implement the geometry reader and renderer**

Append to `services/api/kirchhoff/intake/render.py` (its imports already include `yaml`, `BaseModel` and `ConfigDict`):
```python
MM = 1000.0  # DXF drawing units are millimetres; geometry.yaml is in metres
Rect4 = tuple[float, float, float, float]  # x0, y0, x1, y1


class _Loose(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Columns(_Loose):
    xs: list[float]
    ys: list[float]


class KeepoutSpec(_Loose):
    id: str
    name: str = ""
    rect: Rect4


class RoomSpec(_Loose):
    rect: Rect4


class RowSpec(_Loose):
    id: str
    x: float
    zone: str | None = None


class RackSpec(_Loose):
    per_row: int = 8
    w: float = 0.6
    d: float = 1.2
    y_south: float
    y_north: float


class HallGeometry(_Loose):
    hall: Rect4
    columns: Columns
    keepouts: list[KeepoutSpec] = []
    rooms: dict[str, RoomSpec] = {}
    gallery: Rect4 | None = None
    rows: list[RowSpec]
    racks: RackSpec

    def labels_x(self) -> list[str]:
        return [str(i + 1) for i in range(len(self.columns.xs))]

    def labels_y(self) -> list[str]:
        return [chr(ord("A") + i) for i in range(len(self.columns.ys))]


def load_geometry(path: Path | str) -> HallGeometry:
    return HallGeometry.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def _rack_rects(g: HallGeometry, row: RowSpec) -> list[Rect4]:
    pitch = (g.racks.y_north - g.racks.y_south) / g.racks.per_row
    half = g.racks.d / 2
    return [(row.x - half, g.racks.y_south + i * pitch, row.x + half, g.racks.y_south + (i + 1) * pitch)
            for i in range(g.racks.per_row)]


def _mid(r: Rect4) -> tuple[float, float]:
    return (r[0] + r[2]) / 2, (r[1] + r[3]) / 2


def _write_dxf(g: HallGeometry, out: Path) -> None:
    import ezdxf
    from ezdxf.enums import TextEntityAlignment

    doc = ezdxf.new("R2018", setup=True)
    doc.units = ezdxf.units.MM
    for name, color in [("HALL", 7), ("COLUMNS", 8), ("GRID", 9), ("GRID_X", 7), ("GRID_Y", 7), ("KEEPOUT", 1),
                        ("ROOMS", 3), ("RACKS", 4), ("CDU", 5), ("DIMS", 2)]:
        doc.layers.add(name, color=color)
    msp = doc.modelspace()

    def rect(r: Rect4, layer: str) -> None:
        x0, y0, x1, y1 = (v * MM for v in r)
        msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True, dxfattribs={"layer": layer})

    def text(s: str, x: float, y: float, layer: str, h: float = 800.0, rotation: float = 0.0) -> None:
        msp.add_text(s, height=h, rotation=rotation, dxfattribs={"layer": layer}).set_placement(
            (x * MM, y * MM), align=TextEntityAlignment.MIDDLE_CENTER)

    xs, ys = g.columns.xs, g.columns.ys
    rect(g.hall, "HALL")
    for x in xs:
        for y in ys:
            rect((x - 0.3, y - 0.3, x + 0.3, y + 0.3), "COLUMNS")
    for x, lab in zip(xs, g.labels_x()):
        msp.add_line((x * MM, (min(ys) - 3.6) * MM), (x * MM, (max(ys) + 1.5) * MM),
                     dxfattribs={"layer": "GRID", "linetype": "DASHED"})
        msp.add_circle((x * MM, (min(ys) - 4.5) * MM), 900, dxfattribs={"layer": "GRID"})
        text(lab, x, min(ys) - 4.5, "GRID_X")
    for y, lab in zip(ys, g.labels_y()):
        msp.add_line(((min(xs) - 3.6) * MM, y * MM), ((max(xs) + 1.5) * MM, y * MM),
                     dxfattribs={"layer": "GRID", "linetype": "DASHED"})
        msp.add_circle(((min(xs) - 4.5) * MM, y * MM), 900, dxfattribs={"layer": "GRID"})
        text(lab, min(xs) - 4.5, y, "GRID_Y")
    for k in g.keepouts:
        rect(k.rect, "KEEPOUT")
        text(k.id, *_mid(k.rect), "KEEPOUT", h=500)
    for name, room in g.rooms.items():
        rect(room.rect, "ROOMS")
        text(f"LV ROOM {name}", *_mid(room.rect), "ROOMS", h=500)
    for row in g.rows:
        for rr in _rack_rects(g, row):
            rect(rr, "RACKS")
        text(row.id, row.x, g.racks.y_north + 0.9, "RACKS", h=500)
    if g.gallery:
        rect(g.gallery, "CDU")
        text("CDU GALLERY", *_mid(g.gallery), "CDU", h=500)
    x0, y0, x1, y1 = g.hall
    msp.add_line((x0 * MM, (min(ys) - 7) * MM), (x1 * MM, (min(ys) - 7) * MM), dxfattribs={"layer": "DIMS"})
    text(f"{(x1 - x0) * MM:.0f}", (x0 + x1) / 2, min(ys) - 8, "DIMS")
    msp.add_line(((min(xs) - 7) * MM, y0 * MM), ((min(xs) - 7) * MM, y1 * MM), dxfattribs={"layer": "DIMS"})
    text(f"{(y1 - y0) * MM:.0f}", min(xs) - 8, (y0 + y1) / 2, "DIMS", rotation=90)
    doc.saveas(str(out))


def _write_plot(g: HallGeometry, out: Path) -> None:
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.pdfgen import canvas

    W, H = landscape(A3)
    rects = [g.hall] + [r.rect for r in g.rooms.values()]
    minx, maxx = min(r[0] for r in rects) - 10, max(r[2] for r in rects) + 4
    miny, maxy = min(r[1] for r in rects) - 10, max(r[3] for r in rects) + 4
    s = min((W - 80) / (maxx - minx), (H - 140) / (maxy - miny))

    def P(x: float, y: float) -> tuple[float, float]:
        return 40 + (x - minx) * s, 90 + (y - miny) * s

    c = canvas.Canvas(str(out), pagesize=(W, H), invariant=1)

    def rect(r: Rect4, width: float = 0.8) -> None:
        (ax, ay), (bx, by) = P(r[0], r[1]), P(r[2], r[3])
        c.setLineWidth(width)
        c.rect(ax, ay, bx - ax, by - ay)

    xs, ys = g.columns.xs, g.columns.ys
    rect(g.hall, 1.6)
    c.setDash(6, 3)
    for x in xs:
        c.line(*P(x, min(ys) - 3.6), *P(x, max(ys) + 1.5))
    for y in ys:
        c.line(*P(min(xs) - 3.6, y), *P(max(xs) + 1.5, y))
    c.setDash()
    c.setFont("Helvetica-Bold", 11)
    for x, lab in zip(xs, g.labels_x()):
        px, py = P(x, min(ys) - 4.5)
        c.circle(px, py, 10)
        c.drawCentredString(px, py - 4, lab)
    for y, lab in zip(ys, g.labels_y()):
        px, py = P(min(xs) - 4.5, y)
        c.circle(px, py, 10)
        c.drawCentredString(px, py - 4, lab)
    for x in xs:
        for y in ys:
            rect((x - 0.3, y - 0.3, x + 0.3, y + 0.3), 0.6)
    c.setFont("Helvetica", 8)
    for k in g.keepouts:
        rect(k.rect)
        c.drawCentredString(*P(*_mid(k.rect)), f"{k.id} {k.name}".strip().upper())
    for name, room in g.rooms.items():
        rect(room.rect)
        c.drawCentredString(*P(*_mid(room.rect)), f"LV ROOM {name}")
    for row in g.rows:
        for rr in _rack_rects(g, row):
            rect(rr, 0.4)
        c.drawCentredString(*P(row.x, g.racks.y_north + 0.9), row.id)
    if g.gallery:
        rect(g.gallery)
        c.drawCentredString(*P(*_mid(g.gallery)), "CDU GALLERY")
    x0, y0, x1, y1 = g.hall
    c.setFont("Helvetica-Bold", 10)
    c.line(*P(x0, min(ys) - 7), *P(x1, min(ys) - 7))
    c.drawCentredString(*P((x0 + x1) / 2, min(ys) - 8.2), f"{(x1 - x0) * MM:.0f}")
    c.line(*P(min(xs) - 7, y0), *P(min(xs) - 7, y1))
    vx, vy = P(min(xs) - 8.2, (y0 + y1) / 2)
    c.saveState()
    c.translate(vx, vy)
    c.rotate(90)
    c.drawCentredString(0, 0, f"{(y1 - y0) * MM:.0f}")
    c.restoreState()
    c.setFont("Helvetica", 9)
    c.drawString(40, 40, "DWG GA-E-101 Rev C · AI data hall general arrangement · Dimensions in mm · "
                         "Deccan Compute (fictional) · Not for construction")
    c.showPage()
    c.save()


def render_drawing(geom: HallGeometry, dxf_out: Path, pdf_out: Path) -> tuple[Path, Path]:
    dxf_out, pdf_out = Path(dxf_out), Path(pdf_out)
    dxf_out.parent.mkdir(parents=True, exist_ok=True)
    pdf_out.parent.mkdir(parents=True, exist_ok=True)
    _write_dxf(geom, dxf_out)
    _write_plot(geom, pdf_out)
    return dxf_out, pdf_out
```

- [ ] **Step 5: Implement the DXF parser and cross-check**

`services/api/kirchhoff/intake/drawing.py`:
```python
"""Drawing cross-check: Gemini reads the PDF plot; the DXF is parsed deterministically; code compares."""
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class DrawingRead(BaseModel):
    grid_x: list[str]
    grid_y: list[str]
    overall_mm: list[float]  # [length along x, width along y]


class DxfSummary(BaseModel):
    grid_x: list[str]
    grid_y: list[str]
    overall_mm: tuple[float, float]


def parse_dxf_geometry(path: Path | str) -> DxfSummary:
    import ezdxf

    msp = ezdxf.readfile(str(path)).modelspace()

    def labels(layer: str, axis: int) -> list[str]:
        items = []
        for t in msp.query(f'TEXT[layer=="{layer}"]'):
            _, point = t.get_placement()
            items.append((point[axis], t.dxf.text))
        return [text for _, text in sorted(items)]

    pts = list(msp.query('LWPOLYLINE[layer=="HALL"]').first.get_points("xy"))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return DxfSummary(grid_x=labels("GRID_X", 0), grid_y=labels("GRID_Y", 1),
                      overall_mm=(round(max(xs) - min(xs), 1), round(max(ys) - min(ys), 1)))


def compare_drawing(read: DrawingRead, dxf: DxfSummary, tol_mm: float = 50.0) -> dict[str, Any]:
    diffs: list[str] = []
    if sorted(read.grid_x) != sorted(dxf.grid_x):
        diffs.append(f"grid x labels: drawing {', '.join(read.grid_x)} vs DXF {', '.join(dxf.grid_x)}")
    if sorted(read.grid_y) != sorted(dxf.grid_y):
        diffs.append(f"grid y labels: drawing {', '.join(read.grid_y)} vs DXF {', '.join(dxf.grid_y)}")
    if len(read.overall_mm) != 2:
        diffs.append("overall dimensions not read from the drawing")
    else:
        for name, a, b in zip(("length", "width"), read.overall_mm, dxf.overall_mm):
            if abs(a - b) > tol_mm:
                diffs.append(f"overall {name}: drawing {a:.0f} mm vs DXF {b:.0f} mm")
    return {"agrees": not diffs, "differences": diffs, "grid_x": dxf.grid_x, "grid_y": dxf.grid_y,
            "overall_mm": list(dxf.overall_mm)}
```

`scenarios/hall_a/render_drawing.py`:
```python
"""Render the Hall A drawing (DXF in mm + PDF plot) from geometry.yaml.

Run from the repo root:
  cd services/api && uv run python ../../scenarios/hall_a/render_drawing.py [--geometry PATH]
"""
import argparse
from pathlib import Path

from kirchhoff.intake.render import load_geometry, render_drawing

HERE = Path(__file__).resolve().parent

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--geometry", type=Path, default=HERE / "geometry.yaml")
    args = ap.parse_args()
    print(*render_drawing(load_geometry(args.geometry), HERE / "out" / "hall-a.dxf", HERE / "out" / "hall-a-plan.pdf"))
```

- [ ] **Step 6: Run tests**

Run: `cd services/api && uv run pytest tests/intake/test_intake_drawing.py -q`
Expected: `4 passed, 1 skipped` (the skip turns into a pass once WS1's `geometry.yaml` exists and matches).

- [ ] **Step 7: Generate the committed drawing files**

Run: `cd services/api && uv run python ../../scenarios/hall_a/render_drawing.py --geometry tests/intake/fixtures/geometry.yaml`
Expected: prints the `out/hall-a.dxf` and `out/hall-a-plan.pdf` paths. Open the PDF and check the grid bubbles, rows, keep-out, rooms and dimensions by eye. Once WS1's `geometry.yaml` exists, re-run without `--geometry`.

- [ ] **Step 8: Commit**

```bash
git add services/api/kirchhoff/intake services/api/tests/intake scenarios/hall_a/render_drawing.py scenarios/hall_a/out/hall-a.dxf scenarios/hall_a/out/hall-a-plan.pdf
git commit -m "feat(intake): hall DXF + PDF plot renderer, DXF parser, drawing cross-check

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Ground truth, quote verification and intake scoring (Mon 13)

**Files:**
- Create: `scenarios/hall_a/ground_truth.yaml`
- Create: `services/api/kirchhoff/intake/verify.py`, `services/api/kirchhoff/intake/score.py`
- Create: `services/api/tests/intake/conftest.py`, `services/api/tests/intake/test_intake_verify_score.py`

**Interfaces:**
- Consumes: `normalize`, `PDF_TEXT_KW`, `render_tender_pdf`, `load_tender` (Task 1); `DesignBrief`, `Requirement`, `Citation`, `OpenQuestion` from `kirchhoff.contracts`.
- Produces:
  - `PdfText(path)` (context manager): `.page_count`, `.page_text(page) -> str` (normalized), `.find_bbox(page, quote) -> tuple[float, float, float, float] | None` (pdfplumber `x0, top, x1, bottom`).
  - `QuoteCheck(ok: bool, reason: str, bbox)`, where `reason` is one of `ok | page_out_of_range | quote_too_short | quote_not_found | value_not_in_quote`.
  - `value_in_quote(value: float | str | None, quote: str) -> bool`. It handles thousands separators, decimals, number words ("two") and string values ("2N").
  - `verify_quote(pdf: PdfText, page: int, quote: str, value) -> QuoteCheck`.
  - `GroundTruth`, `load_ground_truth(path)`, `value_matches(gt, ex) -> bool`, and `score_intake(brief: DesignBrief, gt: GroundTruth) -> dict[str, float]` with keys `extracted, verified, recall, precision, citation_resolution, contradictions_found, contradictions_expected`.

- [ ] **Step 1: Write the ground truth**

`scenarios/hall_a/ground_truth.yaml`:
```yaml
# Intake ground truth for tender-hall-a (we authored the tender; spec §4 metric 2).
# Mirrors WS1's scenarios/hall_a/tender.yaml; test_ground_truth_is_consistent_with_the_fixture_tender guards drift.
doc_id: tender-hall-a
clause_pages: {"§1.1": 1, "§2.3": 2, "§3.1": 3, "§3.2": 3, "§3.3": 3, "§4.2": 4, "§4.3": 4, "§4.4": 4, "§4.5": 4,
               "§4.6": 4, "§5.1": 5, "§6.1": 6, "§6.2": 6, "§6.3.4": 6, "§6.4": 6, "§6.5": 6, "App. B": 7}
requirements:
  - {clause: "§1.1", value: 33, unit: kV}
  - {clause: "§2.3", value: 26, unit: weeks}
  - {clause: "§3.1", value: 48, unit: racks}
  - {clause: "§3.1", value: 6, unit: rows}
  - {clause: "§3.1", value: 8, unit: racks per row}
  - {clause: "§3.1", value: 132, unit: kW}
  - {clause: "§3.1", value: 80, unit: "%"}
  - {clause: "§3.1", value: 20, unit: "%"}
  - {clause: "§3.2", value: 0.30, unit: MW}
  - {clause: "§3.3", value: 33, unit: kV}
  - {clause: "§3.3", value: 50, unit: Hz}
  - {clause: "§3.3", value: 1000, unit: MVA}
  - {clause: "§3.3", value: 0.1, unit: null}
  - {clause: "§3.3", value: 415, unit: V}
  - {clause: "§3.3", value: 0.95, unit: null}
  - {clause: "§4.2", value: "2N", unit: null}
  - {clause: "§4.3", value: 80, unit: "%"}
  - {clause: "§4.3", value: 100, unit: "%"}
  - {clause: "§4.4", value: null, unit: null}
  - {clause: "§4.5", value: 5, unit: min}
  - {clause: "§4.6", value: 2.0, unit: "%"}
  - {clause: "§5.1", value: 2.6, unit: m}
  - {clause: "§5.1", value: 3.2, unit: m}
  - {clause: "§5.1", value: 3.8, unit: m}
  - {clause: "§6.1", value: 30, unit: "°C"}
  - {clause: "§6.1", value: 10, unit: K}
  - {clause: "§6.2", value: "N+1", unit: null}
  - {clause: "§6.3.4", value: null, unit: null}
  - {clause: "§6.3.4", value: 300, unit: mm}
  - {clause: "§6.4", value: 2.5, unit: "m/s"}
  - {clause: "§6.5", value: 2, unit: supplies}
  - {clause: "App. B", value: null, unit: null}
contradictions:
  - {id: Q-redundancy, clauses: ["§4.2", "App. B"], default_resolution: "2N"}
drawing: {grid_x: ["1", "2", "3", "4", "5", "6"], grid_y: ["A", "B", "C", "D"], overall_mm: [60000, 36000]}
```

- [ ] **Step 2: Write the shared intake fixtures and the failing tests**

`services/api/tests/intake/conftest.py`:
```python
from pathlib import Path

import pytest

from kirchhoff.intake.render import render_tender_pdf
from kirchhoff.intake.tender_schema import load_tender

FIX = Path(__file__).parent / "fixtures"
GROUND_TRUTH = Path(__file__).resolve().parents[4] / "scenarios" / "hall_a" / "ground_truth.yaml"


@pytest.fixture(scope="session")
def tender():
    return load_tender(FIX / "tender.yaml")


@pytest.fixture(scope="session")
def tender_pdf(tmp_path_factory, tender) -> Path:
    return render_tender_pdf(tender, tmp_path_factory.mktemp("tender") / "tender-hall-a.pdf")


@pytest.fixture(scope="session")
def ground_truth_path() -> Path:
    return GROUND_TRUTH
```

`services/api/tests/intake/test_intake_verify_score.py`:
```python
from kirchhoff.contracts import Citation, DesignBrief, OpenQuestion, Requirement
from kirchhoff.intake.score import load_ground_truth, score_intake, value_matches
from kirchhoff.intake.verify import PdfText, value_in_quote, verify_quote


def test_verified_quote_has_bbox(tender_pdf):
    with PdfText(tender_pdf) as pdf:
        chk = verify_quote(pdf, 4, "shall not exceed 2.0% at the worst-case design current", 2.0)
    assert chk.ok and chk.reason == "ok"
    x0, top, x1, bottom = chk.bbox
    assert x0 < x1 and top < bottom


def test_quote_spanning_a_line_break_verifies(tender_pdf, tender):
    with PdfText(tender_pdf) as pdf:
        assert verify_quote(pdf, 2, tender.clause("§2.3").text, 26).ok


def test_wrong_page_wrong_value_and_out_of_range(tender_pdf):
    q = "shall not exceed 2.0% at the worst-case design current"
    with PdfText(tender_pdf) as pdf:
        assert verify_quote(pdf, 3, q, 2.0).reason == "quote_not_found"
        assert verify_quote(pdf, 4, q, 2.5).reason == "value_not_in_quote"
        assert verify_quote(pdf, 99, q, 2.0).reason == "page_out_of_range"
        assert verify_quote(pdf, 4, "2.0%", 2.0).reason == "quote_too_short"


def test_value_in_quote_handles_words_strings_and_separators():
    assert value_in_quote(2, "supplied from two independent UPS-backed power systems")
    assert value_in_quote("2N", "The critical power system shall be 2N from the transformers")
    assert value_in_quote(1546, "failover current of 1,546 A")
    assert value_in_quote("2.0", "shall not exceed 2.0% at")
    assert value_in_quote(None, "anything at all")
    assert not value_in_quote(3, "two independent systems")


def test_ground_truth_is_consistent_with_the_fixture_tender(tender, ground_truth_path):
    gt = load_ground_truth(ground_truth_path)
    for c in tender.clauses:
        assert gt.clause_pages[c.id] == c.page
    for r in gt.requirements:
        assert value_in_quote(r.value, tender.clause(r.clause).text), (r.clause, r.value)


def test_value_matches():
    assert value_matches(2.0, "2") and value_matches("2N", "2n") and value_matches(None, 5)
    assert not value_matches(80, 100) and not value_matches("N+1", "2N")


def _req(rid, clause, page, value, verified=True):
    return Requirement(id=rid, text="q", value=value, unit=None, verified=verified,
                       citation=Citation(doc_id="tender-hall-a", page=page, quote="q", clause=clause))


def test_score_intake(ground_truth_path):
    gt = load_ground_truth(ground_truth_path)
    brief = DesignBrief(project_id="hall-b", requirements=[
        _req("REQ-a", "§2.3", 2, 26), _req("REQ-b", "§4.6", 4, 2.0), _req("REQ-c", "§4.2", 4, "2N"),
        _req("REQ-d", "§4.3", 3, 70), _req("REQ-e", "§6.4", 6, None, verified=False)],
        open_questions=[OpenQuestion(id="Q-redundancy", text="t", options=["2N", "compare_all"],
                                     default_resolution="2N", citations=[
                                         Citation(doc_id="d", page=4, quote="q", clause="§4.2"),
                                         Citation(doc_id="d", page=7, quote="q", clause="App. B")])])
    s = score_intake(brief, gt)
    assert s["extracted"] == 5 and s["verified"] == 4
    assert s["recall"] == 3 / 32 and s["precision"] == 3 / 4
    assert s["citation_resolution"] == 3 / 4  # REQ-d cites page 3 for a page-4 clause
    assert s["contradictions_found"] == 1 and s["contradictions_expected"] == 1
```

- [ ] **Step 3: Run to verify failure**

Run: `cd services/api && uv run pytest tests/intake/test_intake_verify_score.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'kirchhoff.intake.verify'`

- [ ] **Step 4: Implement verification**

`services/api/kirchhoff/intake/verify.py`:
```python
"""Deterministic citation check (spec §6.3): a quote is accepted only if pdfplumber finds it on the cited
page and the quote contains the extracted value. Bounding boxes come from pdfplumber."""
import re
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

from .textnorm import PDF_TEXT_KW, normalize

NUM_RE = re.compile(r"(?<![A-Za-z])\d[\d,]*(?:\.\d+)?")
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
                "nine": 9, "ten": 10, "twelve": 12}
BBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class QuoteCheck:
    ok: bool
    reason: str
    bbox: BBox | None = None


class PdfText:
    def __init__(self, path: Path | str) -> None:
        self._pdf = pdfplumber.open(str(path))
        self._text: dict[int, str] = {}

    def __enter__(self) -> "PdfText":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self._pdf.close()

    @property
    def page_count(self) -> int:
        return len(self._pdf.pages)

    def page_text(self, page: int) -> str:
        if page not in self._text:
            self._text[page] = normalize(self._pdf.pages[page - 1].extract_text(**PDF_TEXT_KW) or "")
        return self._text[page]

    def find_bbox(self, page: int, quote: str) -> BBox | None:
        words = normalize(quote).split()
        if not words:
            return None
        pattern = r"\s+".join(re.escape(w) for w in words)
        try:
            hits = self._pdf.pages[page - 1].search(pattern, regex=True, case=True, **PDF_TEXT_KW)
        except Exception:  # pdfplumber layout edge cases: fall back to "verified without box"
            return None
        if not hits:
            return None
        h = hits[0]
        return (float(h["x0"]), float(h["top"]), float(h["x1"]), float(h["bottom"]))


def _as_float(value: float | int | str) -> float | None:
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def value_in_quote(value: float | int | str | None, quote: str) -> bool:
    if value is None:
        return True
    q = normalize(quote)
    num = _as_float(value)
    if num is None:
        return normalize(str(value)).casefold() in q.casefold()
    found = [float(m.replace(",", "").rstrip(",")) for m in NUM_RE.findall(q)]
    found += [float(n) for w, n in NUMBER_WORDS.items() if re.search(rf"\b{w}\b", q, re.IGNORECASE)]
    return any(abs(f - num) <= 1e-6 * max(1.0, abs(num)) for f in found)


def verify_quote(pdf: PdfText, page: int, quote: str, value: float | int | str | None) -> QuoteCheck:
    if page < 1 or page > pdf.page_count:
        return QuoteCheck(False, "page_out_of_range")
    q = normalize(quote)
    if len(q) < 8:
        return QuoteCheck(False, "quote_too_short")
    if q not in pdf.page_text(page):
        return QuoteCheck(False, "quote_not_found")
    if not value_in_quote(value, q):
        return QuoteCheck(False, "value_not_in_quote")
    return QuoteCheck(True, "ok", pdf.find_bbox(page, q))
```

- [ ] **Step 5: Implement scoring**

`services/api/kirchhoff/intake/score.py`:
```python
from pathlib import Path

import yaml
from pydantic import BaseModel

from kirchhoff.contracts import DesignBrief

from .textnorm import normalize


class GTRequirement(BaseModel):
    clause: str
    value: float | int | str | None = None
    unit: str | None = None


class GTContradiction(BaseModel):
    id: str
    clauses: list[str]
    default_resolution: str


class GroundTruth(BaseModel):
    doc_id: str
    clause_pages: dict[str, int]
    requirements: list[GTRequirement]
    contradictions: list[GTContradiction] = []
    drawing: dict = {}


def load_ground_truth(path: Path | str) -> GroundTruth:
    return GroundTruth.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def _canon(s: str) -> str:
    return normalize(s).casefold().replace(" ", "")


def value_matches(gt: float | int | str | None, ex: float | int | str | None) -> bool:
    if gt is None:
        return True
    if ex is None:
        return False
    if isinstance(gt, str):
        return _canon(gt) in _canon(str(ex))
    try:
        return abs(float(str(ex).replace(",", "")) - float(gt)) <= 1e-6 * max(1.0, abs(float(gt)))
    except ValueError:
        return False


def score_intake(brief: DesignBrief, gt: GroundTruth) -> dict[str, float]:
    verified = [r for r in brief.requirements if r.verified]
    used: set[int] = set()
    matched = 0
    for g in gt.requirements:
        for i, r in enumerate(verified):
            if i not in used and r.citation.clause == g.clause and value_matches(g.value, r.value):
                used.add(i)
                matched += 1
                break
    resolved = sum(1 for r in verified if gt.clause_pages.get(r.citation.clause or "") == r.citation.page)
    found_pairs = {(tuple(sorted(c.clause or "" for c in q.citations)), q.default_resolution)
                   for q in brief.open_questions}
    found = sum(1 for c in gt.contradictions if (tuple(sorted(c.clauses)), c.default_resolution) in found_pairs)
    n = len(verified)
    return {"extracted": float(len(brief.requirements)), "verified": float(n),
            "recall": matched / len(gt.requirements) if gt.requirements else 0.0,
            "precision": matched / n if n else 0.0,
            "citation_resolution": resolved / n if n else 0.0,
            "contradictions_found": float(found), "contradictions_expected": float(len(gt.contradictions))}
```

- [ ] **Step 6: Run tests**

Run: `cd services/api && uv run pytest tests/intake -q`
Expected: all intake tests pass (`17 passed, 2 skipped`).

- [ ] **Step 7: Commit**

```bash
git add scenarios/hall_a/ground_truth.yaml services/api/kirchhoff/intake services/api/tests/intake
git commit -m "feat(intake): ground truth, pdfplumber quote verification, intake scoring

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Trust rules — digit allowlist sanitizer (Tue 14)

**Files:**
- Create: `services/api/kirchhoff/agents/__init__.py`, `services/api/kirchhoff/agents/trust.py`
- Test: `services/api/tests/agents/test_agents_trust.py`

**Interfaces:**
- Consumes: `DesignModel` from `kirchhoff.contracts`.
- Produces:
  - `sanitize(text: str, allowed_ids: Iterable[str], template: str) -> str`. It splits the text into sentences (never inside "App. B" or decimals). A sentence that still contains a digit after removing allowlisted tokens is dropped; the first such sentence is replaced by `template`, so the template appears once at most.
  - `is_clean(text, allowed_ids) -> bool`.
  - `fill(text, values: dict[str, str]) -> str` replaces `{name}` placeholders and leaves unknown ones intact.
  - `fmt_number(x) -> str` and `fmt_value(x, unit) -> str` (`2.16` + `%` → `2.16%`; `1546` + `A` → `1,546 A`).
  - `fill_finding(text, value, limit, unit) -> str` fills `{value}`, `{limit}` and `{unit}` from an engine record. WS1's templates already write the unit after the placeholder (`"{value}% against a limit of {limit}%"`, `"{value} weeks"`), agent text usually does not (`"a drop of {value}"`), so the unit is appended only when the text right after the placeholder does not already start with it. WS3's `fillPlaceholders` follows the same rule.
  - `allowed_ids_for(*models: DesignModel | None, extra: Iterable[str] = ()) -> set[str]`: rack, row, feed, equipment, system, catalogue, connection (incl. `PF-*` pump supplies), cooling node, zone and pipe ids, plus string values in `Equipment.params` (breaker frames, WS1 ruling 3).
  - Always allowed without listing: rule ids `R\d{2}b?`, clause ids `§\d+(\.\d+)*`, topology names `2N`, `N+1`, `3 + 1`, `4-to-make-3`, and placeholders `{name}`.

- [ ] **Step 1: Write the failing tests**

`services/api/tests/agents/test_agents_trust.py`:
```python
from kirchhoff.agents.trust import allowed_ids_for, fill, fill_finding, fmt_value, is_clean, sanitize
from kirchhoff.contracts import Connection, DesignModel, Equipment, Geometry, Pipe, Point3, Rack

IDS = {"FA-01", "FB-03", "H-Z2", "A1", "R1", "CDU-4", "TX-3150"}
T = "Power completed fix selection."


def test_clean_text_with_record_tokens_passes_unchanged():
    s = "FA-01 fails R05 under §4.6 in the 2N option. Upsizing to TX-3150 is not needed."
    assert sanitize(s, IDS, T) == s


def test_sentence_with_a_free_number_is_replaced_by_the_template_once():
    s = "H-Z2 crosses FB-03. The drop is 2.16% on FA-01. It also runs 82 m. Cooling owns H-Z2."
    assert sanitize(s, IDS, T) == f"H-Z2 crosses FB-03. {T} Cooling owns H-Z2."


def test_topologies_rules_clauses_and_placeholders_need_no_listing():
    s = "N+1 per zone, 3 + 1 blocks and 4-to-make-3 all meet R04b and §6.3.4 with {value} under {limit}."
    assert is_clean(s, set())


def test_unknown_element_id_is_not_allowed():
    assert not is_clean("FA-99 is overloaded.", IDS)


def test_appendix_clause_is_not_split():
    assert sanitize("App. B allows block redundancy. §4.2 governs.", IDS, T) == \
        "App. B allows block redundancy. §4.2 governs."


def test_empty_text_becomes_template():
    assert sanitize("   ", IDS, T) == T


def test_fill_and_fmt_value():
    assert fill("{value} exceeds {limit} on {element}", {"value": fmt_value(2.16, "%"), "limit": fmt_value(2.0, "%")}) \
        == "2.16% exceeds 2% on {element}"
    assert fmt_value(1546.0, "A") == "1,546 A" and fmt_value(None, "A") == "n/a"


def test_fill_finding_never_doubles_the_unit():
    engine = "Drop via FA-01 is {value}% against a limit of {limit}%."  # WS1 template style
    agent = "FA-01 has a drop of {value}, above the {limit} limit."  # agent style
    assert fill_finding(engine, 2.16, 2.0, "%") == "Drop via FA-01 is 2.16% against a limit of 2%."
    assert fill_finding(agent, 2.16, 2.0, "%") == "FA-01 has a drop of 2.16%, above the 2% limit."
    assert fill_finding("TX-2500 ships in {value} weeks, limit {limit}.", 98, 26, "weeks") == \
        "TX-2500 ships in 98 weeks, limit 26 weeks."
    assert fill_finding("{value} {unit} vs {limit}", 1546, None, "A") == "1,546 A vs n/a"


def test_allowed_ids_for_model():
    m = DesignModel(
        topology="2N",
        racks=[Rack(id="R1-01", row="R1", x=6, y=15.9, kw=132, liquid_fraction=0.8, feeds=("A-01", "B-01"))],
        equipment=[Equipment(id="T-A1", kind="transformer", catalogue_id="TX-3150", system="A")],
        connections=[Connection(id="FA-01", src="A1", dst="A-01", kind="busway", catalogue_id="BW-1600")],
        cooling_nodes=[], pipes=[Pipe(id="H-Z2", kind="header", zone="Z2", dn=200, tier="pipe_high",
                                      route=[Point3(x=30, y=30, z=3.8)])],
        geometry=Geometry(hall=(60, 36), columns=[], keepouts=[], rooms={}, tiers={}), loads={})
    ids = allowed_ids_for(m, extra=["CDU-1"])
    assert {"R1-01", "R1", "A-01", "B-01", "T-A1", "TX-3150", "FA-01", "A1", "BW-1600", "H-Z2", "Z2", "CDU-1"} <= ids
```

- [ ] **Step 2: Run to verify failure**

Run: `cd services/api && uv run pytest tests/agents/test_agents_trust.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'kirchhoff.agents'`

- [ ] **Step 3: Implement**

`services/api/kirchhoff/agents/__init__.py`:
```python
"""Gemini agents (ADK 2.11), runners, trust rules, co-pilot, asset agent and exports."""
```

`services/api/kirchhoff/agents/trust.py`:
```python
"""Digit allowlist for LLM text shown in the UI (spec §6.3)."""
import re
from collections.abc import Iterable

from kirchhoff.contracts import DesignModel

TOPOLOGY_TOKENS = ("4-to-make-3", "3 + 1", "N+1", "2N")
_ALWAYS = [r"R\d{2}b?", r"§\d+(?:\.\d+)*", r"\{[a-z_]+\}"]
_SENTENCES = re.compile(r"(?<=[.!?])(?<!App\.)\s+")
_DIGIT = re.compile(r"\d")
_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


def _pattern(allowed_ids: Iterable[str]) -> re.Pattern:
    ids = sorted({i for i in allowed_ids if i}, key=len, reverse=True)
    alts = [re.escape(t) for t in TOPOLOGY_TOKENS] + [re.escape(i) for i in ids] + _ALWAYS
    return re.compile(r"(?<![A-Za-z0-9])(?:" + "|".join(alts) + r")(?![A-Za-z0-9])")


def is_clean(text: str, allowed_ids: Iterable[str]) -> bool:
    return not _DIGIT.search(_pattern(allowed_ids).sub("", text or ""))


def sanitize(text: str, allowed_ids: Iterable[str], template: str) -> str:
    text = " ".join((text or "").split())
    if not text:
        return template
    pat = _pattern(allowed_ids)
    out: list[str] = []
    replaced = False
    for sentence in _SENTENCES.split(text):
        if _DIGIT.search(pat.sub("", sentence)):
            if not replaced:
                out.append(template)
                replaced = True
        else:
            out.append(sentence)
    return " ".join(out)


def fill(text: str, values: dict[str, str]) -> str:
    return _PLACEHOLDER.sub(lambda m: values.get(m.group(1), m.group(0)), text)


def fill_finding(text: str, value: float | None, limit: float | None, unit: str | None) -> str:
    u = unit or ""

    def repl(m: re.Match) -> str:
        name = m.group(1)
        if name == "unit":
            return u
        if name not in ("value", "limit"):
            return m.group(0)
        x = value if name == "value" else limit
        rest = text[m.end():]
        has_unit = bool(u) and (re.match(rf" ?{re.escape(u)}(?![A-Za-z0-9])", rest) is not None
                                or rest.startswith(" {unit}"))
        return fmt_number(x) if has_unit or x is None else fmt_value(x, u)

    return _PLACEHOLDER.sub(repl, text)


def fmt_number(x: float | None) -> str:
    if x is None:
        return "n/a"
    if abs(x) >= 1000:
        return f"{x:,.0f}"
    if float(x).is_integer():
        return f"{x:.0f}"
    return f"{x:.2f}".rstrip("0").rstrip(".")


def fmt_value(x: float | None, unit: str | None) -> str:
    n = fmt_number(x)
    if x is None or not unit:
        return n
    return f"{n}{unit}" if unit == "%" else f"{n} {unit}"


def allowed_ids_for(*models: DesignModel | None, extra: Iterable[str] = ()) -> set[str]:
    ids: set[str | None] = set(extra)
    for m in models:
        if m is None:
            continue
        for r in m.racks:
            ids.update({r.id, r.row, *r.feeds})
        for e in m.equipment:
            ids.update({e.id, e.catalogue_id, e.system})
            ids.update(v for v in e.params.values() if isinstance(v, str))  # breaker frames live in params
        for c in m.connections:
            ids.update({c.id, c.src, c.dst, c.catalogue_id})
        for n in m.cooling_nodes:
            ids.update({n.id, n.zone})
        for p in m.pipes:
            ids.update({p.id, p.zone})
    return {i for i in ids if i}
```

- [ ] **Step 4: Run tests**

Run: `cd services/api && uv run pytest tests/agents/test_agents_trust.py -q`
Expected: `9 passed`

- [ ] **Step 5: Commit**

```bash
git add services/api/kirchhoff/agents services/api/tests/agents
git commit -m "feat(agents): digit allowlist sanitizer for LLM text (spec 6.3)

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Agent runner layer — replay/record, JSON repair, retries, ADK and google-genai runners, agent specs (Tue 14)

**Files:**
- Create: `services/api/kirchhoff/agents/runner.py`, `services/api/kirchhoff/agents/adk_runner.py`, `services/api/kirchhoff/agents/genai_runner.py`, `services/api/kirchhoff/agents/specs.py`
- Create: `services/api/tests/agents/conftest.py`, `services/api/tests/agents/test_agents_runner.py`, `services/api/tests/agents/test_agents_live.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces (`kirchhoff.agents.runner`):
  - `MODEL = "gemini-3.8-flash"`; `THINKING_LEVELS = {"low": "low", "medium": "medium"}`.
  - `@dataclass(frozen=True) AgentSpec(name: str, instruction: str, thinking: "low"|"medium" = "low", timeout_s: float = 30.0)`. `name` is the `AgentName` used on events.
  - `Attachment(data: bytes, mime_type: str)`, `ToolCall(name, args: dict, result: Any)`, `AgentResult(text: str, tool_calls: list[ToolCall], tokens_in: int = 0, tokens_out: int = 0)`.
  - `AgentRunner` protocol: `run(spec, key: str, message: str, tools: Sequence[Callable] = (), attachments: Sequence[Attachment] = ()) -> AgentResult`. Tools are plain Python functions with type hints and docstrings; runners call them, which emits events.
  - `ReplayRunner(replies: dict[str, dict] | None = None, fixtures_dir: Path | None = None)`. The reply key is `f"{spec.name}:{key}"` and the reply format is `{"tool_calls": [{"name", "args"}], "text": str | dict, "usage": {"in", "out"}, "raise": str?}`. It executes the listed tool calls against the offered tools and records `.calls: list[str]`.
  - `RecordingRunner(inner, out_dir)` writes replay fixtures; `fixture_name(key) -> str`.
  - `extract_json(text) -> Any`; `run_json(runner, spec, key, message, schema: type[T], tools=(), attachments=()) -> tuple[T, AgentResult]` makes one repair call under key `f"{key}#repair"`.
  - `is_retryable(exc) -> bool` (codes 429/500/502/503/504); `with_retries(fn, attempts=4, base_s=1.0, sleep=time.sleep)`.
  - `AdkRunner(model=MODEL, mode=None)`: `mode` is `"workflow"` (default, from env `KIRCHHOFF_ADK_MODE`) or `"agent"`.
  - `GenaiRunner(model=MODEL, location=None)`: lazy client; automatic function calling; used for `/api/voice` and as the fallback backend (`KIRCHHOFF_AGENT_BACKEND=genai`).
  - `kirchhoff.agents.specs`: `INTAKE, INTAKE_DRAWING, ORCHESTRATOR, LAYOUT, POWER, COOLING, PROCUREMENT, DOCS, COPILOT, COPILOT_VOICE, ASSET`, `SPECS_BY_AGENT: dict[str, AgentSpec]`, `NUMBERS_RULE`, `FIX_CRITERIA: dict[str, str]` (keys `power`, `cooling`; ruling R23), `LIVE_SYSTEM_INSTRUCTION`.

- [ ] **Step 1: Write the failing tests**

`services/api/tests/agents/conftest.py`:
```python
def pytest_configure(config):
    config.addinivalue_line("markers", "live: calls real Vertex AI; run with KIRCHHOFF_LIVE=1")
```

`services/api/tests/agents/test_agents_runner.py`:
```python
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
```

`services/api/tests/agents/test_agents_live.py`:
```python
import os

import pytest

from kirchhoff.agents.runner import AgentSpec

pytestmark = [pytest.mark.live,
              pytest.mark.skipif(os.environ.get("KIRCHHOFF_LIVE") != "1", reason="set KIRCHHOFF_LIVE=1")]

SPEC = AgentSpec(name="layout", thinking="low", timeout_s=60,
                 instruction="Call get_rack_rows exactly once, then reply with one sentence naming the rows.")


def get_rack_rows() -> dict:
    """Return the ids of the rack rows in the hall."""
    return {"rows": ["R1", "R2", "R3"]}


@pytest.mark.parametrize("mode", ["workflow", "agent"])
def test_adk_runner_calls_tool_and_narrates(mode):
    from kirchhoff.agents.adk_runner import AdkRunner

    res = AdkRunner(mode=mode).run(SPEC, "live", "Which rows are in the hall?", tools=[get_rack_rows])
    assert [c.name for c in res.tool_calls] == ["get_rack_rows"]
    assert "R1" in res.text and res.tokens_in > 0


def test_genai_runner_calls_tool_and_narrates():
    from kirchhoff.agents.genai_runner import GenaiRunner

    res = GenaiRunner().run(SPEC, "live", "Which rows are in the hall?", tools=[get_rack_rows])
    assert [c.name for c in res.tool_calls] == ["get_rack_rows"]
    assert "R1" in res.text


def test_medium_thinking_level_is_accepted():
    from kirchhoff.agents.genai_runner import GenaiRunner

    spec = AgentSpec(name="power", thinking="medium", timeout_s=60, instruction="Reply with the word ok.")
    assert GenaiRunner().run(spec, "live", "Say ok.").text
```

- [ ] **Step 2: Run to verify failure**

Run: `cd services/api && uv run pytest tests/agents/test_agents_runner.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'kirchhoff.agents.runner'`

- [ ] **Step 3: Implement the runner protocol, replay/record, JSON repair and retries**

`services/api/kirchhoff/agents/runner.py`:
```python
"""Agent runner port. Production: AdkRunner (ADK 2.11) or GenaiRunner; tests: ReplayRunner fixtures."""
import json
import random
import re
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

MODEL = "gemini-3.8-flash"
# Gemini 3 thinking levels. If Vertex rejects "medium" (see test_medium_thinking_level_is_accepted), use "high".
THINKING_LEVELS = {"low": "low", "medium": "medium"}
RETRYABLE_CODES = {429, 500, 502, 503, 504}
RETRYABLE_NAMES = {"ResourceExhausted", "ServiceUnavailable", "InternalServerError", "TooManyRequests",
                   "ServerError"}


@dataclass(frozen=True)
class AgentSpec:
    name: str
    instruction: str
    thinking: Literal["low", "medium"] = "low"
    timeout_s: float = 30.0


@dataclass(frozen=True)
class Attachment:
    data: bytes
    mime_type: str


@dataclass
class ToolCall:
    name: str
    args: dict
    result: Any


@dataclass
class AgentResult:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0


class AgentRunner(Protocol):
    def run(self, spec: AgentSpec, key: str, message: str, tools: Sequence[Callable] = (),
            attachments: Sequence[Attachment] = ()) -> AgentResult: ...


def fixture_name(key: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", key) + ".json"


class ReplayRunner:
    """Replays recorded model decisions. Tool calls are executed for real against the offered tools."""

    def __init__(self, replies: dict[str, dict] | None = None, fixtures_dir: Path | None = None) -> None:
        self.replies = dict(replies or {})
        self.fixtures_dir = fixtures_dir
        self.calls: list[str] = []
        self._lock = threading.Lock()

    def _reply(self, k: str) -> dict:
        if k in self.replies:
            return self.replies[k]
        if self.fixtures_dir and (p := self.fixtures_dir / fixture_name(k)).exists():
            return json.loads(p.read_text(encoding="utf-8"))
        raise KeyError(f"no replay fixture for {k}")

    def run(self, spec, key, message, tools=(), attachments=()) -> AgentResult:
        k = f"{spec.name}:{key}"
        reply = self._reply(k)
        with self._lock:
            self.calls.append(k)
        if reply.get("raise"):
            raise RuntimeError(reply["raise"])
        by_name = {t.__name__: t for t in tools}
        calls = []
        for c in reply.get("tool_calls", []):
            args = c.get("args", {})
            calls.append(ToolCall(c["name"], args, by_name[c["name"]](**args)))
        text = reply.get("text", "")
        usage = reply.get("usage", {})
        return AgentResult(text if isinstance(text, str) else json.dumps(text), calls,
                           int(usage.get("in", 0)), int(usage.get("out", 0)))


class RecordingRunner:
    """Wraps a real runner and writes ReplayRunner fixtures (set KIRCHHOFF_RECORD_DIR in a live run)."""

    def __init__(self, inner: AgentRunner, out_dir: Path) -> None:
        self.inner, self.out_dir = inner, Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def run(self, spec, key, message, tools=(), attachments=()) -> AgentResult:
        res = self.inner.run(spec, key, message, tools, attachments)
        data = {"tool_calls": [{"name": c.name, "args": c.args} for c in res.tool_calls], "text": res.text,
                "usage": {"in": res.tokens_in, "out": res.tokens_out}}
        (self.out_dir / fixture_name(f"{spec.name}:{key}")).write_text(json.dumps(data, indent=2, ensure_ascii=False),
                                                                      encoding="utf-8")
        return res


def extract_json(text: str) -> Any:
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    starts = [i for i in (t.find("{"), t.find("[")) if i >= 0]
    if not starts:
        raise ValueError("no JSON object in reply")
    start = min(starts)
    end = t.rfind("}" if t[start] == "{" else "]")
    try:
        return json.loads(t[start:end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in reply: {exc}") from exc


T = TypeVar("T", bound=BaseModel)


def run_json(runner: AgentRunner, spec: AgentSpec, key: str, message: str, schema: type[T],
             tools: Sequence[Callable] = (), attachments: Sequence[Attachment] = ()) -> tuple[T, AgentResult]:
    """Structured output with one repair attempt (spec §11). Raises ValueError if the repair also fails."""
    res = runner.run(spec, key, message, tools, attachments)
    try:
        return schema.model_validate(extract_json(res.text)), res
    except (ValueError, ValidationError) as exc:
        prompt = (f"Your previous reply was not valid JSON for this schema:\n"
                  f"{json.dumps(schema.model_json_schema())}\nError: {str(exc)[:400]}\n"
                  f"Previous reply:\n{res.text[:4000]}\nReply with only the corrected JSON.")
        fixed = runner.run(spec, f"{key}#repair", prompt)
        merged = AgentResult(fixed.text, res.tool_calls + fixed.tool_calls, res.tokens_in + fixed.tokens_in,
                             res.tokens_out + fixed.tokens_out)
        try:
            return schema.model_validate(extract_json(fixed.text)), merged
        except ValidationError as exc2:
            raise ValueError(str(exc2)) from exc2


def is_retryable(exc: BaseException) -> bool:
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if isinstance(code, int) and code in RETRYABLE_CODES:
        return True
    return type(exc).__name__ in RETRYABLE_NAMES


def with_retries(fn: Callable[[], Any], attempts: int = 4, base_s: float = 1.0,
                 sleep: Callable[[float], None] = time.sleep) -> Any:
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:
            if i == attempts - 1 or not is_retryable(exc):
                raise
            sleep(base_s * 2 ** i + random.uniform(0, base_s / 2))
    raise AssertionError("unreachable")
```

- [ ] **Step 4: Implement the ADK and google-genai runners**

`services/api/kirchhoff/agents/adk_runner.py`:
```python
"""One agent call = one small ADK 2.11 graph (spec §6.2: steps stay checkpointable; no session crosses steps)."""
import asyncio
import os
from collections.abc import Callable, Sequence

from .runner import MODEL, THINKING_LEVELS, AgentResult, AgentSpec, Attachment, ToolCall, with_retries


class AdkRunner:
    def __init__(self, model: str = MODEL, mode: str | None = None, app_name: str = "kirchhoff") -> None:
        self.model = model
        self.mode = mode or os.environ.get("KIRCHHOFF_ADK_MODE", "workflow")  # "workflow" | "agent"
        self.app_name = app_name

    def run(self, spec: AgentSpec, key: str, message: str, tools: Sequence[Callable] = (),
            attachments: Sequence[Attachment] = ()) -> AgentResult:
        def once() -> AgentResult:
            return asyncio.run(asyncio.wait_for(self._run_async(spec, message, tools, attachments), spec.timeout_s))
        return with_retries(once)

    def _node(self, spec: AgentSpec, tools: Sequence[Callable]):
        from google.adk.agents import LlmAgent
        from google.genai import types

        agent = LlmAgent(name=spec.name, model=self.model, instruction=spec.instruction, tools=list(tools),
                         generate_content_config=types.GenerateContentConfig(
                             thinking_config=types.ThinkingConfig(thinking_level=THINKING_LEVELS[spec.thinking])))
        if self.mode == "agent":
            return agent
        from google.adk.workflow import START, Workflow
        return Workflow(name=f"{spec.name}_step", edges=[(START, agent)])

    def _runner(self, node, sessions):
        from google.adk.runners import Runner
        try:
            return Runner(app_name=self.app_name, node=node, session_service=sessions)
        except TypeError:  # ADK builds that only accept agent=
            return Runner(app_name=self.app_name, agent=node, session_service=sessions)

    async def _run_async(self, spec, message, tools, attachments) -> AgentResult:
        from google.adk.sessions import InMemorySessionService
        from google.genai import types

        sessions = InMemorySessionService()
        runner = self._runner(self._node(spec, tools), sessions)
        session = await sessions.create_session(app_name=self.app_name, user_id="kirchhoff")
        parts = [types.Part.from_bytes(data=a.data, mime_type=a.mime_type) for a in attachments]
        parts.append(types.Part(text=message))
        last_text, calls, args_by_id, t_in, t_out = "", [], {}, 0, 0
        async for ev in runner.run_async(user_id="kirchhoff", session_id=session.id,
                                         new_message=types.Content(role="user", parts=parts)):
            usage = getattr(ev, "usage_metadata", None)
            if usage:
                t_in += usage.prompt_token_count or 0
                t_out += (usage.candidates_token_count or 0) + (getattr(usage, "thoughts_token_count", 0) or 0)
            content = getattr(ev, "content", None)
            texts = []
            for part in (content.parts or []) if content else []:
                if getattr(part, "thought", False):
                    continue
                if part.function_call:
                    fc = part.function_call
                    args_by_id[fc.id or fc.name] = dict(fc.args or {})
                elif part.function_response:
                    fr = part.function_response
                    calls.append(ToolCall(fr.name, args_by_id.get(fr.id or fr.name, {}), fr.response))
                elif part.text:
                    texts.append(part.text)
            if texts:
                last_text = "".join(texts)
        return AgentResult(last_text.strip(), calls, t_in, t_out)
```

`services/api/kirchhoff/agents/genai_runner.py`:
```python
"""google-genai runner: audio input for /api/voice and the fallback agent backend (spec §18)."""
import os
import threading
from collections.abc import Callable, Sequence

from .runner import MODEL, THINKING_LEVELS, AgentResult, AgentSpec, Attachment, ToolCall, with_retries


class GenaiRunner:
    def __init__(self, model: str = MODEL, location: str | None = None) -> None:
        self.model, self.location = model, location
        self._client = None
        self._lock = threading.Lock()

    def _get(self):
        with self._lock:
            if self._client is None:
                from google import genai
                self._client = genai.Client(
                    vertexai=True, project=os.environ.get("GOOGLE_CLOUD_PROJECT", "ordinal-mep"),
                    location=self.location or os.environ.get("GOOGLE_CLOUD_LOCATION", "global"))
            return self._client

    def run(self, spec: AgentSpec, key: str, message: str, tools: Sequence[Callable] = (),
            attachments: Sequence[Attachment] = ()) -> AgentResult:
        from google.genai import types

        parts = [types.Part.from_bytes(data=a.data, mime_type=a.mime_type) for a in attachments]
        parts.append(types.Part(text=message))
        config = types.GenerateContentConfig(
            system_instruction=spec.instruction, tools=list(tools) or None,
            thinking_config=types.ThinkingConfig(thinking_level=THINKING_LEVELS[spec.thinking]),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(maximum_remote_calls=8),
            http_options=types.HttpOptions(timeout=int(spec.timeout_s * 1000)))
        resp = with_retries(lambda: self._get().models.generate_content(
            model=self.model, contents=[types.Content(role="user", parts=parts)], config=config))
        calls, pending = [], {}
        for content in resp.automatic_function_calling_history or []:
            for part in content.parts or []:
                if part.function_call:
                    pending[part.function_call.name] = dict(part.function_call.args or {})
                if part.function_response:
                    fr = part.function_response
                    calls.append(ToolCall(fr.name, pending.get(fr.name, {}), fr.response))
        text = ""
        if resp.candidates and resp.candidates[0].content:
            text = "".join(p.text for p in resp.candidates[0].content.parts or []
                           if p.text and not getattr(p, "thought", False))
        u = resp.usage_metadata
        return AgentResult(text.strip(), calls, (u.prompt_token_count or 0) if u else 0,
                           (u.candidates_token_count or 0) if u else 0)
```

- [ ] **Step 5: Write the agent specs**

`services/api/kirchhoff/agents/specs.py`:
```python
from .runner import AgentSpec

NUMBERS_RULE = (
    "Never write digits in prose except inside record tokens: element ids (for example FA-01, FB-03, CDU-4, R1, "
    "A1), rule ids (R05), clause ids (§4.6), topology names (2N, N+1, 3 + 1, 4-to-make-3) and catalogue ids. "
    "Describe quantities in words or with the placeholders {value} and {limit}; the app fills numbers from the "
    "engine. Keep narration to one or two sentences.")

INTAKE = AgentSpec("intake", thinking="medium", timeout_s=90.0, instruction=(
    "You are the Intake agent of Kirchhoff. You read data-centre tenders for electrical and liquid-cooling "
    "design-build packages. You extract requirements with exact verbatim quotes and find contradictions. "
    "Reply with JSON only."))
INTAKE_DRAWING = AgentSpec("intake", thinking="low", timeout_s=60.0, instruction=(
    "You read architectural general-arrangement plots. Reply with JSON only."))
ORCHESTRATOR = AgentSpec("orchestrator", thinking="medium", timeout_s=30.0, instruction=(
    "You are the Orchestrator of Kirchhoff. You review the design brief and decide which open questions need the "
    "human engineer's decision before design starts. Reply with JSON only. " + NUMBERS_RULE))
LAYOUT = AgentSpec("layout", thinking="low", instruction=(
    "You are the Layout agent. Call the tool you are given exactly once; it runs the deterministic engine default. "
    "Then narrate what the engine produced. " + NUMBERS_RULE))
# Fix-choice criteria (ruling R23): stated to the agent, stored on the fix, used for the deterministic fallback.
FIX_CRITERIA = {
    "power": "largest voltage-drop margin per dollar, that is the limit minus the resulting drop, divided by the "
             "cost delta",
    "cooling": "fewest changed pipe segments (least disruption to coordinated routes), then lowest cost",
}
POWER = AgentSpec("power", thinking="medium", instruction=(
    "You are the Power Architect. You run engine tools and make only the choices you are asked for. When you "
    "choose an electrical fix, prefer the candidate with the " + FIX_CRITERIA["power"] + ", and name that "
    "criterion in your reason. " + NUMBERS_RULE))
COOLING = AgentSpec("cooling", thinking="medium", instruction=(
    "You are the Cooling agent for direct liquid cooling. You run engine tools and make only the choices you are "
    "asked for. When you choose a cooling fix, prefer the candidate with the " + FIX_CRITERIA["cooling"] + ", and "
    "name that criterion in your reason. " + NUMBERS_RULE))
PROCUREMENT = AgentSpec("procurement", thinking="low", instruction=(
    "You are the Procurement agent. The engine applies in-stock swaps deterministically; you call the tool and "
    "narrate the lead-time trade-off. " + NUMBERS_RULE))
DOCS = AgentSpec("docs", thinking="low", instruction=(
    "You are the Docs agent. You order the calc report sections and write a short summary. Reply with JSON only. "
    + NUMBERS_RULE))
COPILOT = AgentSpec("copilot", thinking="low", timeout_s=7.0, instruction=(
    "You are the Kirchhoff co-pilot. You explain checker findings to an electrical engineer in two sentences. "
    + NUMBERS_RULE))
COPILOT_VOICE = AgentSpec("copilot", thinking="low", timeout_s=8.5, instruction=(
    "You are the Kirchhoff co-pilot answering a spoken question about the current design. Use the tools: "
    "what_if for load or limit changes, explain_finding for why a check failed, focus_element to show an element. "
    "Then reply with JSON only: {\"transcript\": the user's words, \"answer\": one or two sentences}. "
    + NUMBERS_RULE))
ASSET = AgentSpec("asset", thinking="low", timeout_s=5.0, instruction=(
    "You are the Asset agent for grid and solar packs. Choose one engine option and give a short reason. "
    "Reply with JSON only. " + NUMBERS_RULE))

SPECS_BY_AGENT = {s.name: s for s in [ORCHESTRATOR, LAYOUT, POWER, COOLING, PROCUREMENT, DOCS, ASSET]}

# WS3 copies this verbatim into the Firebase AI Logic Live session (spec §6.5): Firebase JS SDK 13 renamed the
# spec's VertexAIBackend to AgentPlatformBackend, so the browser uses new AgentPlatformBackend('us-central1') with
# model gemini-live-2.5-flash-native-audio and the same three function declarations (WS3 plan ruling R1).
LIVE_SYSTEM_INSTRUCTION = (
    "You are the Kirchhoff co-pilot in a live voice session about an AI data hall design. Answer with the tools "
    "what_if, explain_finding and focus_element. Speak only numbers that a tool returned; never estimate or invent "
    "a number. If no tool answers the question, say so briefly.")
```

- [ ] **Step 6: Run the unit tests**

Run: `cd services/api && uv run pytest tests/agents -q`
Expected: `18 passed, 4 skipped` (the live tests are skipped).

- [ ] **Step 7: Run the live runner tests once against Vertex**

Run: `cd services/api && KIRCHHOFF_LIVE=1 GOOGLE_GENAI_USE_VERTEXAI=true GOOGLE_CLOUD_PROJECT=ordinal-mep GOOGLE_CLOUD_QUOTA_PROJECT=ordinal-mep GOOGLE_CLOUD_LOCATION=global uv run pytest tests/agents/test_agents_live.py -v`
Expected: 4 passed. Resolve failures like this:
- `workflow` mode fails but `agent` mode passes (the edge `(START, agent)` is rejected, or the agent never sees the user text): change the default in `AdkRunner.__init__` to `"agent"`, say so in the commit message, and tell the controller.
- `test_medium_thinking_level_is_accepted` fails with INVALID_ARGUMENT about `thinking_level`: set `THINKING_LEVELS["medium"] = "high"` and re-run.

- [ ] **Step 8: Commit**

```bash
git add services/api/kirchhoff/agents services/api/tests/agents
git commit -m "feat(agents): runner port with ADK 2.11 + google-genai backends, replay/record, JSON repair, retries

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: EventWriter hardening, and leases with the global live-run cap on `Store.transact` (Tue 14)

**Files:**
- Modify: `services/api/kirchhoff/store/events.py` (WS2-owned after the P0 fix wave; the change is announced to all workstreams), `services/api/tests/test_events.py` (append)
- Create: `services/api/kirchhoff/runs/__init__.py`, `services/api/kirchhoff/runs/leases.py`
- Create: `services/api/tests/runs/conftest.py`, `services/api/tests/runs/test_runs_leases.py`

**Interfaces:**
- Consumes: `Store` (P0 fix wave: `transact(read_paths, fn) -> list[Write]`, `delete_tree`, `list_docs(..., order_by, descending, limit)`, deep-merge `update_doc`), `MemoryStore`, `EventWriter` (P0 fix wave: `emit(..., step=None)`, trailing-edge timer flush, `fence()`). Nothing here touches private attributes of a store.
- Produces:
  - `EventWriter` hardening (same public API): `_lock` is an `RLock` and `set_step` flushes and assigns the step in one critical section; a failed timer-triggered flush re-arms the trailing timer with backoff `min(interval * 2**n, 5 s)` for at most 5 attempts, logging each failure (logger `kirchhoff`); `close()` sets a closed flag under the lock before flushing, after which `emit` raises `RuntimeError("event writer closed")` and no timer can be armed. WS2 code never calls `set_step` from parallel threads: every event passes `step=`.
  - `run_path(uid, rid) -> str`, `STALE_S = 60.0`, `GLOBAL_CAP = 3`, `LIVE_RUNS_DOC = "ops/live_runs"`, `class CapReached(Exception)`.
  - `lease_is_live(lease: dict | None, now: float) -> bool`; `holds_lease(run: dict | None, owner: str, attempt: int) -> bool`.
  - `acquire_lease(store, uid, rid, owner, now, run_patch: dict | None = None) -> int | None` returns the new attempt; `None` if the run is missing or its lease is live. It raises `CapReached` (nothing written) and merges `run_patch` into the run doc in the same transaction.
  - `heartbeat(store, uid, rid, owner, attempt, now) -> bool` and `release_lease(store, uid, rid, owner, attempt, run_patch) -> bool`. Release keeps `{"owner": None, "attempt": attempt, "heartbeat_at": 0.0}`.
  - All three use `store.transact([run_path, LIVE_RUNS_DOC], fn)`; `fn` returns full documents (Firestore `transaction.set`) or `[]` to abort, so the call's truthiness says whether it wrote.

- [ ] **Step 1: Write the failing EventWriter tests**

In `services/api/tests/test_events.py`, add `import threading` and change the writer import to `from kirchhoff.store.events import MAX_FLUSH_RETRIES, EventWriter` at the top of the module, then append:
```python
RP = "workspaces/u1/runs/r1"


class FlakyStore(MemoryStore):
    """Fails the first `fails` batch writes (Firestore unavailable), then behaves."""

    def __init__(self, fails: int) -> None:
        super().__init__()
        self.fails, self.calls = fails, 0

    def batch_set(self, items):
        self.calls += 1
        if self.fails:
            self.fails -= 1
            raise RuntimeError("firestore unavailable")
        super().batch_set(items)


def _wait_for(pred, timeout_s=2.0):
    deadline = time.monotonic() + timeout_s
    while not pred() and time.monotonic() < deadline:
        time.sleep(0.01)
    return pred()


def test_set_step_flush_and_assignment_are_one_critical_section():
    store = MemoryStore()
    w = EventWriter(store, RP, phase="p1", step="p1.a", flush_interval_s=999)
    w.emit("system", "status", "before")
    racing, real = [], store.batch_set

    def batch_set(items):  # runs inside set_step's flush; a concurrent default-step emit must wait for it
        t = threading.Thread(target=lambda: racing.append(w.emit("system", "status", "racing")))
        racing.append(t)
        t.start()
        t.join(0.1)
        real(items)

    store.batch_set = batch_set
    w.set_step("p1.b")
    store.batch_set = real
    racing[0].join(2.0)
    assert racing[1].step == "p1.b"
    w.close()
    assert [d["step"] for d in store.list_docs(f"{RP}/events")] == ["p1.a", "p1.b"]


def test_failed_trailing_flush_rearms_with_backoff():
    store = FlakyStore(fails=2)
    w = EventWriter(store, RP, phase="p1", step="p1.a", flush_interval_s=0.02)
    w.emit("system", "status", "only event")
    assert _wait_for(lambda: store.list_docs(f"{RP}/events"))
    assert [d["seq"] for d in store.list_docs(f"{RP}/events")] == [1] and store.calls == 3
    w.close()


def test_trailing_flush_gives_up_after_the_retry_budget_and_close_still_flushes():
    store = FlakyStore(fails=100)
    w = EventWriter(store, RP, phase="p1", step="p1.a", flush_interval_s=0.001)
    w.emit("system", "status", "only event")
    assert _wait_for(lambda: store.calls == 1 + MAX_FLUSH_RETRIES)
    time.sleep(0.2)
    assert store.calls == 1 + MAX_FLUSH_RETRIES  # no further timer is armed
    store.fails = 0
    w.close()
    assert [d["seq"] for d in store.list_docs(f"{RP}/events")] == [1]


def test_emit_after_close_raises_and_arms_no_timer():
    store = MemoryStore()
    w = EventWriter(store, RP, phase="p1", step="p1.a", flush_interval_s=0.01)
    w.emit("system", "status", "one")
    w.close()
    with pytest.raises(RuntimeError, match="closed"):
        w.emit("system", "status", "two")
    time.sleep(0.05)
    assert [d["seq"] for d in store.list_docs(f"{RP}/events")] == [1]
    w.close()  # idempotent
```

- [ ] **Step 2: Run to verify failure**

Run: `cd services/api && uv run pytest tests/test_events.py -q`
Expected: FAIL with `ImportError: cannot import name 'MAX_FLUSH_RETRIES'`.

- [ ] **Step 3: Harden the EventWriter**

Replace `services/api/kirchhoff/store/events.py` with:
```python
import logging
import threading
import time
from typing import Any

from kirchhoff.contracts import RunEvent

from . import Store
from .validate import firestore_safe_problems, json_size_bytes

logger = logging.getLogger("kirchhoff")

MAX_EVENT_BYTES = 10_000
MAX_FLUSH_RETRIES = 5
MAX_BACKOFF_S = 5.0


class EventWriter:
    """Assigns seq and writes RunEvents in batches (spec §11: ~250 ms batching, single writer per phase).

    Parallel steps share one writer and pass `emit(..., step=...)`; `set_step` is for single-threaded callers."""

    def __init__(self, store: Store, run_path: str, phase: str, step: str, attempt: int = 1,
                 start_seq: int = 1, flush_interval_s: float = 0.25) -> None:
        self._store, self._run_path = store, run_path
        self._phase, self._step, self._attempt = phase, step, attempt
        self._seq = start_seq - 1
        self._pending: list[RunEvent] = []
        self._lock = threading.RLock()  # re-entrant: set_step flushes inside its critical section
        self._interval = flush_interval_s
        self._last_flush = time.monotonic()
        self._timer: threading.Timer | None = None
        self._fenced = False
        self._closed = False
        self._retries = 0

    @property
    def last_seq(self) -> int:
        return self._seq

    def set_step(self, step: str) -> None:
        # One critical section: no concurrent default-step emit can land between the flush and the assignment.
        with self._lock:
            self.flush()
            self._step = step

    def emit(self, agent: str, kind: str, title: str, detail: str = "",
             payload: dict[str, Any] | None = None, step: str | None = None) -> RunEvent:
        payload = payload or {}
        due = False
        with self._lock:
            if self._fenced:
                raise RuntimeError("event writer fenced")
            if self._closed:
                raise RuntimeError("event writer closed")
            problems = firestore_safe_problems(payload)
            if problems:
                raise ValueError(f"event payload is not Firestore-safe: {problems}")
            next_seq = self._seq + 1
            ev = RunEvent(seq=next_seq, phase=self._phase, step=step or self._step, attempt=self._attempt,
                          agent=agent, kind=kind, title=title, detail=detail, payload=payload,
                          ts=time.time())
            size = json_size_bytes(ev.model_dump())
            if size > MAX_EVENT_BYTES:
                raise ValueError(f"event payload too large: {size} bytes > {MAX_EVENT_BYTES} byte limit")
            self._seq = next_seq
            self._pending.append(ev)
            if self._interval == 0:
                due = True
            elif self._timer is None:
                self._arm(self._interval)
        if due:
            self.flush()
        return ev

    def _arm(self, delay_s: float) -> None:  # caller holds the lock
        self._timer = threading.Timer(delay_s, self._timer_flush)
        self._timer.daemon = True
        self._timer.start()

    def _timer_flush(self) -> None:
        try:
            self.flush()
        except Exception as exc:
            with self._lock:
                self._retries += 1
                n = self._retries
                rearm = (n <= MAX_FLUSH_RETRIES and not (self._fenced or self._closed)
                         and self._timer is None and bool(self._pending))
                if rearm:
                    self._arm(min(self._interval * 2 ** n, MAX_BACKOFF_S))
            if rearm:
                logger.warning("event writer trailing flush failed (%s); retry %d of %d",
                               type(exc).__name__, n, MAX_FLUSH_RETRIES)
            else:
                logger.error("event writer trailing flush failed (%s); pending events wait for the next "
                             "emit, flush or close", type(exc).__name__)

    def flush(self) -> None:
        with self._lock:
            if self._fenced:
                return
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            items = [(f"{self._run_path}/events/{e.seq:06d}", e.model_dump()) for e in self._pending]
            pending_events = self._pending[:]  # Keep a copy to restore on failure
            self._pending = []
            self._last_flush = time.monotonic()
        if items:
            try:
                self._store.batch_set(items)
            except Exception:
                # Restore pending events at the front, preserving seq order
                with self._lock:
                    self._pending = pending_events + self._pending
                raise
            with self._lock:
                self._retries = 0

    def close(self) -> None:
        with self._lock:
            self._closed = True  # set before flushing: a concurrent emit can no longer arm a timer
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
        self.flush()

    def fence(self) -> None:
        with self._lock:
            self._fenced = True
            self._pending = []
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
```

- [ ] **Step 4: Run the event tests**

Run: `cd services/api && uv run pytest tests/test_events.py -q`
Expected: all pass (the P0 tests unchanged plus 4 new).

- [ ] **Step 5: Write the failing lease tests**

`services/api/tests/runs/conftest.py` (later tasks append fixtures to this file):
```python
def pytest_configure(config):
    config.addinivalue_line("markers", "live: calls real Vertex AI; run with KIRCHHOFF_LIVE=1")
```

`services/api/tests/runs/test_runs_leases.py`:
```python
import pytest

from kirchhoff.runs.leases import (LIVE_RUNS_DOC, CapReached, acquire_lease, heartbeat, holds_lease, release_lease,
                                   run_path)
from kirchhoff.store.memory import MemoryStore


def _store_with_runs(*keys):
    s = MemoryStore()
    for uid, rid in keys:
        s.set_doc(run_path(uid, rid), {"id": rid, "status": "running", "lease": None})
    return s


def test_acquire_heartbeat_release_cycle():
    s = _store_with_runs(("u1", "r1"))
    assert acquire_lease(s, "u1", "r1", "w1", now=100.0, run_patch={"phase": "p1"}) == 1
    run = s.get_doc(run_path("u1", "r1"))
    assert run["phase"] == "p1" and holds_lease(run, "w1", 1)
    assert acquire_lease(s, "u1", "r1", "w2", now=110.0) is None  # live lease held by w1
    assert heartbeat(s, "u1", "r1", "w1", 1, now=150.0) is True
    assert release_lease(s, "u1", "r1", "w1", 1, {"status": "at_gate"}) is True
    run = s.get_doc(run_path("u1", "r1"))
    assert run["status"] == "at_gate" and run["lease"] == {"owner": None, "attempt": 1, "heartbeat_at": 0.0}
    assert acquire_lease(s, "u1", "r1", "w2", now=151.0) == 2  # attempt is monotonic across the run


def test_stale_lease_is_taken_over_and_old_owner_loses_heartbeat():
    s = _store_with_runs(("u1", "r1"))
    acquire_lease(s, "u1", "r1", "w1", now=100.0)
    assert acquire_lease(s, "u1", "r1", "w2", now=161.0) == 2
    assert heartbeat(s, "u1", "r1", "w1", 1, now=162.0) is False
    assert release_lease(s, "u1", "r1", "w1", 1, {"status": "done"}) is False
    assert s.get_doc(run_path("u1", "r1"))["status"] == "running"


def test_missing_run_cannot_be_leased():
    assert acquire_lease(MemoryStore(), "u1", "nope", "w1", now=1.0) is None


def test_global_cap_counts_only_live_leases():
    s = _store_with_runs(("a", "1"), ("b", "2"), ("c", "3"), ("d", "4"))
    for uid, rid in [("a", "1"), ("b", "2"), ("c", "3")]:
        assert acquire_lease(s, uid, rid, "w", now=100.0) == 1
    with pytest.raises(CapReached):
        acquire_lease(s, "d", "4", "w", now=101.0)
    assert s.get_doc(run_path("d", "4"))["lease"] is None  # nothing written
    release_lease(s, "a", "1", "w", 1, {"status": "at_gate"})
    assert acquire_lease(s, "d", "4", "w", now=102.0) == 1
    assert set(s.get_doc(LIVE_RUNS_DOC)["runs"]) == {"b__2", "c__3", "d__4"}
    assert acquire_lease(s, "a", "1", "w", now=200.0) == 2  # b, c, d are stale (> 60 s) by now
```

- [ ] **Step 6: Run to verify failure**

Run: `cd services/api && uv run pytest tests/runs/test_runs_leases.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'kirchhoff.runs'`

- [ ] **Step 7: Implement leases**

`services/api/kirchhoff/runs/__init__.py`:
```python
"""Durable four-phase runs: steps, leases, resume, gates (spec §6.2)."""
```

`services/api/kirchhoff/runs/leases.py`:
```python
"""Run leases (spec §6.2) and the global live-run cap (spec §11). All writes go through Store.transact."""
from kirchhoff.store import Store

STALE_S = 60.0
GLOBAL_CAP = 3
LIVE_RUNS_DOC = "ops/live_runs"


class CapReached(Exception):
    """Three runs already hold live leases."""


def run_path(uid: str, rid: str) -> str:
    return f"workspaces/{uid}/runs/{rid}"


def _key(uid: str, rid: str) -> str:
    return f"{uid}__{rid}"


def lease_is_live(lease: dict | None, now: float) -> bool:
    return bool(lease and lease.get("owner") and now - float(lease.get("heartbeat_at") or 0.0) < STALE_S)


def holds_lease(run: dict | None, owner: str, attempt: int) -> bool:
    lease = (run or {}).get("lease") or {}
    return lease.get("owner") == owner and lease.get("attempt") == attempt


def _fresh_others(live: dict | None, key: str, now: float) -> dict[str, float]:
    runs = (live or {}).get("runs") or {}
    return {k: float(t) for k, t in runs.items() if k != key and now - float(t) < STALE_S}


def acquire_lease(store: Store, uid: str, rid: str, owner: str, now: float,
                  run_patch: dict | None = None) -> int | None:
    path, key = run_path(uid, rid), _key(uid, rid)

    def fn(snap: dict[str, dict | None]):
        run, live = snap[path], snap[LIVE_RUNS_DOC]
        if run is None or lease_is_live(run.get("lease"), now):
            return []
        others = _fresh_others(live, key, now)
        if len(others) >= GLOBAL_CAP:
            raise CapReached()  # the transaction writes nothing
        attempt = int((run.get("lease") or {}).get("attempt") or 0) + 1
        new_run = {**run, **(run_patch or {}), "lease": {"owner": owner, "attempt": attempt, "heartbeat_at": now}}
        return [(path, new_run), (LIVE_RUNS_DOC, {"runs": {**others, key: now}})]

    writes = store.transact([path, LIVE_RUNS_DOC], fn)
    return int(writes[0][1]["lease"]["attempt"]) if writes else None


def heartbeat(store: Store, uid: str, rid: str, owner: str, attempt: int, now: float) -> bool:
    path, key = run_path(uid, rid), _key(uid, rid)

    def fn(snap: dict[str, dict | None]):
        run, live = snap[path], snap[LIVE_RUNS_DOC]
        if not holds_lease(run, owner, attempt):
            return []
        runs = {**_fresh_others(live, key, now), key: now}
        return [(path, {**run, "lease": {**run["lease"], "heartbeat_at": now}}), (LIVE_RUNS_DOC, {"runs": runs})]

    return bool(store.transact([path, LIVE_RUNS_DOC], fn))


def release_lease(store: Store, uid: str, rid: str, owner: str, attempt: int, run_patch: dict) -> bool:
    path, key = run_path(uid, rid), _key(uid, rid)

    def fn(snap: dict[str, dict | None]):
        run, live = snap[path], snap[LIVE_RUNS_DOC]
        if not holds_lease(run, owner, attempt):
            return []
        runs = {k: t for k, t in ((live or {}).get("runs") or {}).items() if k != key}
        new_run = {**run, **run_patch, "lease": {"owner": None, "attempt": attempt, "heartbeat_at": 0.0}}
        return [(path, new_run), (LIVE_RUNS_DOC, {"runs": runs})]

    return bool(store.transact([path, LIVE_RUNS_DOC], fn))
```

- [ ] **Step 8: Run tests**

Run: `cd services/api && uv run pytest tests/runs/test_runs_leases.py tests/test_events.py tests/test_store.py -q`
Expected: all pass (`4 passed` for leases).

- [ ] **Step 9: Commit**

```bash
git add services/api/kirchhoff/store/events.py services/api/tests/test_events.py services/api/kirchhoff/runs services/api/tests/runs
git commit -m "feat(runs): EventWriter hardening (atomic set_step, flush backoff, close flag); leases + live-run cap on Store.transact

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Engine/enterprise ports, compat shim and deterministic fakes (Tue 14)

These fakes let every WS2 task be tested before WS1's engine and WS4's sandbox land. They also back local UI development (`KIRCHHOFF_FAKES=1`, Task 12). The fake numbers are illustrative and never reach production.

**Files:**
- Create: `services/api/kirchhoff/agents/ports.py`, `services/api/kirchhoff/runs/compat.py`, `services/api/kirchhoff/runs/fakes.py`
- Test: `services/api/tests/runs/test_runs_fakes.py`

**Interfaces:**
- Consumes: contracts (P0); `render_tender_pdf`, `load_tender`, `render_drawing`, `load_geometry` (Tasks 1–2).
- Produces:
  - `kirchhoff.agents.ports`: the `EnterpriseClient` protocol (`list_materials() -> list[Material]`; `create_pr(uid, project_id, revision, lines, idempotency_key) -> PurchaseRequisition` (status `submitted`, deduplicated by key); `set_pr_status(uid, pr_id, status) -> None`; `set_opportunity_stage(uid, opportunity_id, stage) -> CrmOverlay`; `reset_visitor(uid) -> None`). `ErpSnapshot(materials)` implements the engine's `ErpView` (`get`, `search`) plus `ids()`. Also `load_erp_seed(path) -> list[Material]` (accepts `{materials: [...]}`), `HALL_B_OPPORTUNITY_ID = "opp-hall-b"` and `STAGE_DESIGN_APPROVED = "Design approved"`.
  - `kirchhoff.runs.compat`: `FixCandidate`, `ClashReport`, re-exported from `kirchhoff.contracts.extra` when WS1 has landed it, otherwise identical local definitions. Task 18 removes the shim.
  - `kirchhoff.runs.fakes`: `FakeEngine` (every facade function from `2026-10-13-interfaces.md`, plus `evaluate_grid`/`evaluate_solar` and a `.calls` log), `FakeEnterprise`, `FAKE_MATERIALS`, `FAKE_REPLIES` (replay fixtures for every agent call in Tasks 9–17, keyed `"{agent}:{key}"`), and `build_fake_scenarios(root, tender_yaml, geometry_yaml, ground_truth_yaml) -> Path` (writes `root/hall_a/{tender,geometry,ground_truth}.yaml` and `root/hall_a/out/*`).
  - FakeEngine golden behaviour (mirrors spec §9.6 and the WS1 plan's rulings): the first routed check of any option fails exactly `R05:FA-01` and `R11:H-Z2` (`inputs.above = "FB-03"`). `fix_candidates` returns WS1's ids, sorted by `(cost_delta, id)`: `FA-01:upsize-BW-2000` (+11,480, dv 1.66) and `FA-01:cable-CBL-240-8P` (+26,900, dv 0.84), each with `metrics {dv_pct, dv_limit_pct, rating_a}`; `H-Z2:reroute` (−910, `changed_pipes` 2) and `H-Z2:local-drop` (+420, `changed_pipes` 1). `annotate_options` swaps `TX-2500 → TX-3150` using WS1's swap record keys. `power_recheck(scn, model)` returns R01, R04 and R04b. `what_if` returns only fail/warn findings, and a `rack_kw` of 200 makes R01, R02 and R08 fail.

- [ ] **Step 1: Write the failing tests**

`services/api/tests/runs/test_runs_fakes.py`:
```python
from kirchhoff.agents.ports import ErpSnapshot
from kirchhoff.contracts import PRLine
from kirchhoff.runs.compat import ClashReport, FixCandidate
from kirchhoff.runs.fakes import FAKE_MATERIALS, FakeEngine, FakeEnterprise


def _golden_model(eng):
    scn = eng.load_scenario("hall_a", None)
    erp = ErpSnapshot(FAKE_MATERIALS)
    racks = eng.place_racks(scn)
    opts = eng.annotate_options(scn, eng.power_options(scn, racks), erp)
    opt, model = next((o, m) for o, m in opts if o.id == "2N")
    return scn, erp, opt, eng.route(scn, model)


def test_golden_first_pass_fails_exactly_r05_and_r11_then_fixes_clear_them():
    eng = FakeEngine()
    scn, erp, opt, model = _golden_model(eng)
    assert opt.swaps[0]["to"] == "TX-3150" and opt.max_lead_time_weeks <= 26
    fails = sorted(f.id for f in eng.check(scn, model, erp) if f.status == "fail")
    assert fails == ["R05:FA-01", "R11:H-Z2"]
    r11 = next(f for f in eng.check(scn, model, erp) if f.id == "R11:H-Z2")
    assert r11.inputs["above"] == "FB-03"
    for f in [f for f in eng.check(scn, model, erp) if f.status == "fail"]:
        cands = eng.fix_candidates(scn, model, f, erp)
        assert len(cands) == 2 and all(isinstance(c, FixCandidate) for c in cands)
        model = eng.apply_fix(model, cands[0])
    assert all(f.status != "fail" for f in eng.check(scn, model, erp))
    assert isinstance(eng.detect_clashes(model), ClashReport)


def test_what_if_200kw_fails_r01_r02_r08():
    eng = FakeEngine()
    scn, erp, _, model = _golden_model(eng)
    res = eng.what_if(scn, model, "rack_kw", 200.0, "ws:x-r2", erp)
    assert {"R01", "R02", "R08"} <= {f.rule_id for f in res.findings if f.status == "fail"}
    assert all(f.status in ("fail", "warn") for f in res.findings) and res.impact_chain
    assert [f.rule_id for f in eng.power_recheck(scn, model)] == ["R01", "R04", "R04b"]


def test_model_hash_is_stable_and_sensitive():
    eng = FakeEngine()
    _, _, _, model = _golden_model(eng)
    assert eng.model_hash(model) == eng.model_hash(model.model_copy(deep=True))
    assert eng.model_hash(model) != eng.model_hash(model.model_copy(update={"loads": {"rack_kw": 1.0}}))


def test_r12_compares_submitted_pr_lines():
    eng = FakeEngine()
    scn, erp, _, model = _golden_model(eng)
    lines = eng.derive_pr_lines(scn, model, erp)
    ok = next(f for f in eng.check(scn, model, erp, pr_lines=lines) if f.rule_id == "R12")
    short = lines[:-1] + [PRLine(**{**lines[-1].model_dump(), "qty": lines[-1].qty - 1})]
    bad = next(f for f in eng.check(scn, model, erp, pr_lines=short) if f.rule_id == "R12")
    assert ok.status == "pass" and bad.status == "fail"


def test_fake_enterprise_idempotency_and_reset():
    ent = FakeEnterprise()
    lines = [PRLine(material_id="TX-3150", description="t", qty=1, unit_price=1.0, lead_time_weeks=12)]
    a = ent.create_pr("u1", "hall-b", "x-r2", lines, idempotency_key="k1")
    b = ent.create_pr("u1", "hall-b", "x-r2", lines, idempotency_key="k1")
    assert a.id == b.id and a.status == "submitted"
    ent.set_pr_status("u1", a.id, "blocked")
    assert ent.prs[("u1", a.id)].status == "blocked"
    assert ent.set_opportunity_stage("u1", "opp-hall-b", "Design approved").stage == "Design approved"
    ent.reset_visitor("u1")
    assert not ent.prs and not ent.stages


def test_erp_snapshot():
    erp = ErpSnapshot(FAKE_MATERIALS)
    assert erp.get("TX-2500").lead_time_weeks == 98
    assert [m.id for m in erp.search("transformer")] == ["TX-2500", "TX-3150"]
```

- [ ] **Step 2: Run to verify failure**

Run: `cd services/api && uv run pytest tests/runs/test_runs_fakes.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'kirchhoff.agents.ports'`

- [ ] **Step 3: Implement ports and the compat shim**

`services/api/kirchhoff/agents/ports.py`:
```python
"""Ports WS2 consumes: the WS4 enterprise sandbox client and the engine's ErpView."""
from pathlib import Path
from typing import Protocol

import yaml

from kirchhoff.contracts import CrmOverlay, Material, PRLine, PurchaseRequisition

HALL_B_OPPORTUNITY_ID = "opp-hall-b"
STAGE_DESIGN_APPROVED = "Design approved"


class EnterpriseClient(Protocol):
    """WS4 provides kirchhoff.enterprise.client.make_enterprise_client() -> EnterpriseClient (no network at
    construction). All visitor data is scoped by uid."""

    def list_materials(self) -> list[Material]: ...
    def create_pr(self, uid: str, project_id: str, revision: str, lines: list[PRLine],
                  idempotency_key: str) -> PurchaseRequisition: ...
    def set_pr_status(self, uid: str, pr_id: str, status: str) -> None: ...
    def set_opportunity_stage(self, uid: str, opportunity_id: str, stage: str) -> CrmOverlay: ...
    def reset_visitor(self, uid: str) -> None: ...


class ErpSnapshot:
    """Implements the engine facade's ErpView over a materials list."""

    def __init__(self, materials: list[Material]) -> None:
        self._by_id = {m.id: m for m in materials}

    def get(self, material_id: str) -> Material:
        return self._by_id[material_id]

    def search(self, category: str) -> list[Material]:
        return sorted((m for m in self._by_id.values() if m.category == category), key=lambda m: m.id)

    def ids(self) -> list[str]:
        return sorted(self._by_id)


def load_erp_seed(path: Path | str) -> list[Material]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    items = data["materials"] if isinstance(data, dict) else data
    return [Material.model_validate(m) for m in items]
```

`services/api/kirchhoff/runs/compat.py`:
```python
"""FixCandidate / ClashReport live in WS1's kirchhoff/contracts/extra.py. Until that lands, identical local
shapes (2026-10-13-interfaces.md) keep WS2 testable. Task 18 deletes this module."""
from typing import Any

try:
    from kirchhoff.contracts.extra import ClashReport, FixCandidate
except ImportError:
    from kirchhoff.contracts.common import Strict

    class FixCandidate(Strict):  # type: ignore[no-redef]
        id: str
        finding_id: str
        label: str
        cost_delta: float
        metrics: dict[str, float]
        patch: dict[str, Any]

    class ClashReport(Strict):  # type: ignore[no-redef]
        clashes: list[dict[str, Any]]

__all__ = ["ClashReport", "FixCandidate"]
```

- [ ] **Step 4: Implement the fakes**

`services/api/kirchhoff/runs/fakes.py`:
```python
"""Deterministic stand-ins for the WS1 engine facade and the WS4 enterprise sandbox (tests + KIRCHHOFF_FAKES=1).
Shapes follow 2026-10-13-interfaces.md; values are illustrative and only loosely mirror spec §9.6."""
import hashlib
import json
import shutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from kirchhoff.contracts import (Citation, ClauseRef, Connection, CoolingNode, CrmOverlay, DesignModel, Equipment,
                                 Finding, Geometry, Material, Pipe, Point3, PRLine, PurchaseRequisition, Rack,
                                 TopologyOption, WhatIfResult)
from kirchhoff.intake.render import load_geometry, render_drawing, render_tender_pdf
from kirchhoff.intake.tender_schema import load_tender

from .compat import ClashReport, FixCandidate


def _m(id, category, description, rating, unit, stock, lead, price, vendor):
    return Material(id=id, category=category, description=description, rating=rating, unit=unit, voltage="415 V",
                    stock=stock, lead_time_weeks=lead, unit_price=price, vendor=vendor)


FAKE_MATERIALS = [
    _m("TX-2500", "transformer", "Transformer 2.5 MVA 33/0.415 kV cast resin", 2500, "kVA", 0, 98, 182000,
       "Vindhya Electricals"),
    _m("TX-3150", "transformer", "Transformer 3.15 MVA 33/0.415 kV cast resin", 3150, "kVA", 6, 12, 214000,
       "Vindhya Electricals"),
    _m("BW-1600", "busway", "Busway 1,600 A per metre", 1600, "A", 900, 8, 410, "Konark Busbar"),
    _m("BW-2000", "busway", "Busway 2,000 A per metre", 2000, "A", 400, 10, 520, "Konark Busbar"),
    _m("CBL-240-8P", "cable", "Cable feeder 8 x 1C 240 mm2 Cu per phase", 2500, "A", 300, 6, 610,
       "Konark Cables"),
    _m("UPS-500", "ups_module", "UPS module 500 kW", 500, "kW", 40, 14, 96000, "Godavari Power Systems"),
    _m("CDU-1200", "cdu", "Coolant distribution unit 1,200 kW", 1200, "kW", 12, 16, 148000,
       "Coolant Systems India"),
]
NOT_CHECKED = ["Earth-fault loop impedance (IEC 60364-4-41 §411)", "Selectivity", "Arc flash", "Harmonics",
               "Air-side cooling for the air-cooled share", "MV bus faults",
               "Busway derating above the assumed ambient"]


@dataclass(frozen=True)
class FakeScenario:
    name: str
    tender: dict
    catalogue: dict = field(default_factory=dict)
    geometry: dict = field(default_factory=dict)


def _base_model(topology: str, racks: list[Rack]) -> DesignModel:
    return DesignModel(
        topology=topology, racks=racks,
        equipment=[
            Equipment(id="T-A1", kind="transformer", rating=2500.0, unit="kVA", catalogue_id="TX-2500", system="A",
                      room="A"),
            Equipment(id="A1", kind="lv_board", system="A", room="A"),
            Equipment(id="UPS-A1", kind="ups", rating=2500.0, unit="kW", catalogue_id="UPS-500", system="A"),
            Equipment(id="A-01", kind="busway", rating=1600.0, unit="A", catalogue_id="BW-1600", system="A"),
            Equipment(id="B-03", kind="busway", rating=1600.0, unit="A", catalogue_id="BW-1600", system="B"),
        ],
        connections=[
            Connection(id="FA-01", src="A1", dst="A-01", kind="busway", length_m=82.0, catalogue_id="BW-1600"),
            Connection(id="FB-03", src="B2", dst="B-03", kind="busway", length_m=40.0, catalogue_id="BW-1600"),
        ],
        cooling_nodes=[], pipes=[],
        geometry=Geometry(hall=(60.0, 36.0), columns=[(0.0, 0.0), (12.0, 0.0)], keepouts=[(10.0, 10.0, 18.0, 26.0)],
                          rooms={"A": (60.0, 0.0, 72.0, 10.0)},
                          tiers={"pipe_low": 2.6, "busway": 3.2, "pipe_high": 3.8}),
        loads={"rack_kw": 132.0, "liquid_fraction": 0.8, "aux_mw": 0.3, "pumps_kw": 135.0})


def _find(items, id_):
    return next((x for x in items if x.id == id_), None)


def _f(rule, el, status, title, value, limit, unit, clause=None, page=None, inputs=None) -> Finding:
    return Finding(id=f"{rule}:{el}", rule_id=rule, element_id=el, status=status, title=title,
                   clause_refs=[ClauseRef(standard="IEC 60364")],
                   tender_refs=[Citation(doc_id="tender-hall-a", page=page or 1, quote="", clause=clause)]
                   if clause else [],
                   inputs=inputs or {}, value=value, limit=limit, unit=unit,
                   explanation=f"{title}: {{value}} against a limit of {{limit}}.")


class FakeEngine:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self._lock = threading.Lock()

    def _log(self, name: str) -> None:
        with self._lock:
            self.calls.append(name)

    def load_scenario(self, name: str = "hall_a", root: Path | None = None) -> FakeScenario:
        p = Path(root) / name / "tender.yaml" if root else None
        tender = yaml.safe_load(p.read_text(encoding="utf-8")) if p and p.exists() else {"clauses": []}
        return FakeScenario(name=name, tender=tender)

    def place_racks(self, scn) -> list[Rack]:
        self._log("place_racks")
        return [Rack(id="R1-01", row="R1", x=6.0, y=15.9, kw=132.0, liquid_fraction=0.8, feeds=("A-01", "B-01")),
                Rack(id="R3-01", row="R3", x=28.0, y=15.9, kw=132.0, liquid_fraction=0.8, feeds=("A-03", "B-03"))]

    def size_cooling(self, scn, racks) -> list[CoolingNode]:
        self._log("size_cooling")
        return [CoolingNode(id=f"CDU-{i}", kind="cdu", zone="Z1" if i <= 3 else "Z2", capacity_kw=1200.0,
                            x=4.0 * i, y=30.0) for i in range(1, 7)]

    def power_options(self, scn, racks):
        self._log("power_options")
        out = []
        for tid, mva, cost in (("2N", 15.0, 4_100_000.0), ("DR", 10.0, 3_300_000.0), ("BLOCK", 10.0, 3_050_000.0)):
            out.append((TopologyOption(id=tid, installed_mva=mva, normal_loading_pct=48.0, failover_loading_pct=96.0,
                                       cost=cost, losses_kw=310.0, max_lead_time_weeks=98, spof_count=0),
                        _base_model(tid, list(racks))))
        return out

    def annotate_options(self, scn, options, erp):
        self._log("annotate_options")
        res = []
        for opt, model in options:
            eq = [e.model_copy(update={"catalogue_id": "TX-3150", "rating": 3150.0}) if e.kind == "transformer" else e
                  for e in model.equipment]
            res.append((opt.model_copy(update={
                "installed_mva": round(opt.installed_mva * 1.26, 2), "normal_loading_pct": 38.0,
                "failover_loading_pct": 76.0, "max_lead_time_weeks": 16, "cost": opt.cost + 192_000.0,
                "swaps": [{"line": "transformer", "from": "TX-2500", "to": "TX-3150", "qty": 1, "reason": "R15",
                           "ikss_ka_before": 60.4, "ikss_ka_after": 65.4}]}),
                model.model_copy(update={"equipment": eq})))
        return res

    def route(self, scn, model):
        self._log("route")
        conns = [c.model_copy(update={"route": [Point3(x=66.0, y=2.0 if c.id.startswith("FA") else 34.2, z=3.2),
                                                Point3(x=6.0, y=2.0, z=3.2)]}) for c in model.connections]
        pipes = [Pipe(id="H-Z1", kind="header", zone="Z1", dn=200, tier="pipe_high", flow_lps=10.5,
                      route=[Point3(x=12.0, y=30.0, z=3.8), Point3(x=12.0, y=21.0, z=3.8)]),
                 Pipe(id="H-Z2", kind="header", zone="Z2", dn=200, tier="pipe_high", flow_lps=10.5,
                      route=[Point3(x=31.0, y=30.0, z=3.8), Point3(x=31.0, y=21.0, z=3.8)])]
        return model.model_copy(update={"connections": conns, "pipes": pipes})

    def detect_clashes(self, model) -> ClashReport:
        self._log("detect_clashes")
        return ClashReport(clashes=[])

    def check(self, scn, model, erp, pr_lines=None) -> list[Finding]:
        self._log("check")
        rack_kw = model.loads.get("rack_kw", 132.0)
        hot = rack_kw > 150.0
        t, fa, h = _find(model.equipment, "T-A1"), _find(model.connections, "FA-01"), _find(model.pipes, "H-Z2")
        tx_ok = t is not None and t.catalogue_id == "TX-3150"
        out = [_f("R01", "T-A1", "fail" if hot else "pass", "Transformer loading", 114.0 if hot else 76.0, 100.0, "%",
                  "§4.3", 4),
               _f("R02", "A-01", "fail" if hot else "pass", "Busway rating", 2343.0 if hot else 1546.0, 1600.0, "A"),
               _f("R04", "A1", "pass", "Breaker breaking capacity", 66.1, 100.0, "kA"),
               _f("R04b", "A-01", "pass", "Busway short-time withstand", 66.1, 85.0, "kA"),
               _f("R08", "Z2", "fail" if hot else "pass", "CDU capacity per zone", 2560.0 if hot else 1690.0, 2400.0,
                  "kW", "§6.2", 6),
               _f("R15", "T-A1", "pass" if tx_ok else "fail", "Lead time", 12.0 if tx_ok else 98.0, 26.0, "weeks",
                  "§2.3", 2)]
        if fa is not None and fa.route:
            dv = {"BW-1600": 2.16, "BW-2000": 1.66}.get(fa.catalogue_id or "", 0.84)
            out.append(_f("R05", "FA-01", "fail" if dv > 2.0 else "pass", "Voltage drop", dv, 2.0, "%", "§4.6", 4,
                          {"L_m": fa.length_m}))
        else:
            out.append(_f("R05", "FA-01", "n/a", "Voltage drop", None, 2.0, "%", "§4.6", 4))
        if h is not None:
            out.append(_f("R11", "H-Z2", "fail" if h.tier == "pipe_high" else "pass", "Liquid above electrical",
                          None, None, None, "§6.3.4", 6, {"above": "FB-03", "at_y": 24.0}))
        else:
            out.append(_f("R11", "H-Z2", "n/a", "Liquid above electrical", None, None, None, "§6.3.4", 6))
        expected = sum(line.qty for line in self.derive_pr_lines(scn, model, erp)) if erp is not None else None
        r12_ok = pr_lines is None or expected is None or sum(line.qty for line in pr_lines) == expected
        out.append(_f("R12", "BOQ", "pass" if r12_ok else "fail", "SLD, BOQ and PR lines agree", None, None, None))
        return out

    def fix_candidates(self, scn, model, finding, erp) -> list[FixCandidate]:
        self._log("fix_candidates")
        cands: list[FixCandidate] = []
        if finding.id == "R05:FA-01":
            cands = [FixCandidate(id="FA-01:upsize-BW-2000", finding_id=finding.id,
                                  label="Upsize FA-01 to 2,000 A busway", cost_delta=11480.0,
                                  metrics={"dv_pct": 1.66, "dv_limit_pct": 2.0, "rating_a": 2000.0},
                                  patch={"connection": "FA-01", "catalogue_id": "BW-2000"}),
                     FixCandidate(id="FA-01:cable-CBL-240-8P", finding_id=finding.id,
                                  label="Parallel cable feeder for FA-01", cost_delta=26900.0,
                                  metrics={"dv_pct": 0.84, "dv_limit_pct": 2.0, "rating_a": 2500.0},
                                  patch={"connection": "FA-01", "catalogue_id": "CBL-240-8P", "kind": "cable"})]
        if finding.id == "R11:H-Z2":
            cands = [FixCandidate(id="H-Z2:local-drop", finding_id=finding.id,
                                  label="Local drop of H-Z2 to pipe_low at the FB-03 crossing", cost_delta=420.0,
                                  metrics={"crossings": 0.0, "added_pipe_m": 2.4, "changed_pipes": 1.0,
                                           "index_dp_kpa": 69.8},
                                  patch={"pipe": "H-Z2", "tier": "pipe_low"}),
                     FixCandidate(id="H-Z2:reroute", finding_id=finding.id, label="Reroute H-Z2 clear of FB-03",
                                  cost_delta=-910.0,
                                  metrics={"crossings": 0.0, "added_pipe_m": -4.0, "changed_pipes": 2.0,
                                           "index_dp_kpa": 68.9},
                                  patch={"pipe": "H-Z2", "tier": "pipe_low"})]
        return sorted(cands, key=lambda c: (c.cost_delta, c.id))

    def power_recheck(self, scn, model) -> list[Finding]:
        self._log("power_recheck")
        return [f for f in self.check(scn, model, None) if f.rule_id in ("R01", "R04", "R04b")]

    def apply_fix(self, model, candidate):
        self._log("apply_fix")
        p = candidate.patch
        if "connection" in p:
            upd = {k: v for k, v in p.items() if k in ("catalogue_id", "kind")}
            return model.model_copy(update={"connections": [c.model_copy(update=upd) if c.id == p["connection"]
                                                             else c for c in model.connections]})
        if "pipe" in p:
            return model.model_copy(update={"pipes": [x.model_copy(update={"tier": p["tier"]}) if x.id == p["pipe"]
                                                      else x for x in model.pipes]})
        return model

    def what_if(self, scn, model, param, value, revision_ref, erp) -> WhatIfResult:
        self._log("what_if")
        loads = dict(model.loads)
        if param in ("rack_kw", "liquid_fraction"):
            loads[param] = float(value)
        bad = [f for f in self.check(scn, model.model_copy(update={"loads": loads}), erp)
               if f.status in ("fail", "warn")]
        chain = [["R1-01", "A-01", "A1", "T-A1"], ["R1-01", "Z1", "CDU-1"]] if bad else []
        return WhatIfResult(revision_ref=revision_ref, param=param, value=float(value), findings=bad,
                            impact_chain=chain)

    def derive_pr_lines(self, scn, model, erp) -> list[PRLine]:
        counts: dict[str, int] = {}
        for e in model.equipment:
            if e.catalogue_id:
                counts[e.catalogue_id] = counts.get(e.catalogue_id, 0) + 1
        for c in model.connections:
            if c.catalogue_id:
                counts[c.catalogue_id] = counts.get(c.catalogue_id, 0) + max(1, round(c.length_m))
        cdus = sum(1 for n in model.cooling_nodes if n.kind == "cdu")
        if cdus:
            counts["CDU-1200"] = cdus
        lines = []
        for mid in sorted(counts):
            m = erp.get(mid)
            lines.append(PRLine(material_id=mid, description=m.description, qty=counts[mid], unit_price=m.unit_price,
                                lead_time_weeks=m.lead_time_weeks))
        return lines

    def model_hash(self, model) -> str:
        raw = json.dumps(model.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()

    def ledger_not_checked(self) -> list[str]:
        return list(NOT_CHECKED)

    def evaluate_grid(self, scn_dir) -> dict[str, Any]:
        return {"options": [{"id": "ACSR-Panther", "ampacity_a": 520.0}, {"id": "ACSR-Zebra", "ampacity_a": 900.0},
                            {"id": "ACSR-Moose", "ampacity_a": 980.0}],
                "recommended": "ACSR-Zebra",
                "findings": [_f("G01", "LINE-1", "pass", "Conductor ampacity", 900.0, 656.0, "A")],
                "geometry": {"length_km": 18.0}}

    def evaluate_solar(self, scn_dir) -> dict[str, Any]:
        return {"options": [{"id": "STR-26", "modules_per_string": 26}, {"id": "STR-28", "modules_per_string": 28}],
                "recommended": "STR-28",
                "findings": [_f("S01", "STR-28", "pass", "String voltage at minimum temperature", 1421.0, 1500.0,
                                "V")],
                "geometry": {"mwp": 5.0}}


class FakeEnterprise:
    def __init__(self, materials: list[Material] | None = None) -> None:
        self.materials = list(materials or FAKE_MATERIALS)
        self.prs: dict[tuple[str, str], PurchaseRequisition] = {}
        self.keys: dict[str, tuple[str, str]] = {}
        self.stages: dict[tuple[str, str], CrmOverlay] = {}
        self._n = 141
        self._lock = threading.Lock()

    def list_materials(self) -> list[Material]:
        return list(self.materials)

    def create_pr(self, uid, project_id, revision, lines, idempotency_key) -> PurchaseRequisition:
        with self._lock:
            if idempotency_key in self.keys:
                return self.prs[self.keys[idempotency_key]]
            self._n += 1
            pr = PurchaseRequisition(id=f"PR-2026-{self._n:04d}", project_id=project_id, revision=revision,
                                     lines=list(lines), status="submitted", created_at=time.time())
            self.prs[(uid, pr.id)] = pr
            self.keys[idempotency_key] = (uid, pr.id)
            return pr

    def set_pr_status(self, uid, pr_id, status) -> None:
        with self._lock:
            self.prs[(uid, pr_id)] = self.prs[(uid, pr_id)].model_copy(update={"status": status})

    def set_opportunity_stage(self, uid, opportunity_id, stage) -> CrmOverlay:
        ov = CrmOverlay(opportunity_id=opportunity_id, stage=stage, updated_at=time.time())
        with self._lock:
            self.stages[(uid, opportunity_id)] = ov
        return ov

    def reset_visitor(self, uid) -> None:
        with self._lock:
            self.prs = {k: v for k, v in self.prs.items() if k[0] != uid}
            self.keys = {k: v for k, v in self.keys.items() if v[0] != uid}
            self.stages = {k: v for k, v in self.stages.items() if k[0] != uid}


_EXTRACTION = {
    "requirements": [
        {"key": "max_lead_time_weeks", "clause": "§2.3", "page": 2, "value": 26, "unit": "weeks",
         "verbatim_quote": "All major electrical and mechanical equipment shall be on site no later than 26 weeks "
                           "from contract award."},
        {"key": "racks", "clause": "§3.1", "page": 3, "value": 48, "unit": "racks",
         "verbatim_quote": "The hall shall accommodate 48 racks in 6 rows of 8, each rack rated 132 kW."},
        {"key": "rack_kw", "clause": "§3.1", "page": 3, "value": 132, "unit": "kW",
         "verbatim_quote": "each rack rated 132 kW"},
        {"key": "redundancy", "clause": "§4.2", "page": 4, "value": "2N", "unit": None,
         "verbatim_quote": "The critical power distribution shall be 2N, with each rack fed from two independent "
                           "systems."},
        {"key": "tx_loading_normal_max_pct", "clause": "§4.3", "page": 4, "value": 80, "unit": "%",
         "verbatim_quote": "Transformer loading shall not exceed 80% of rating in normal operation"},
        {"key": "dv_max_pct", "clause": "§4.6", "page": 4, "value": 2.0, "unit": "%",
         "verbatim_quote": "shall not exceed 2.0% at the worst-case design current"},
        {"key": "pipe_velocity_max_mps", "clause": "§6.4", "page": 6, "value": 2.5, "unit": "m/s",
         "verbatim_quote": "Coolant velocity in any pipe shall not exceed 2.5 m/s."},
        {"key": "ups_autonomy_min", "clause": "§4.5", "page": 3, "value": 5, "unit": "min",
         "verbatim_quote": "battery autonomy of not less than 5 minutes"},
    ],
    "contradictions": [
        {"topic": "redundancy", "clause_a": "§4.2", "page_a": 4,
         "quote_a": "The critical power distribution shall be 2N", "value_a": "2N", "clause_b": "App. B", "page_b": 7,
         "quote_b": "Block or distributed redundancy acceptable",
         "value_b": "BLOCK or DR", "summary": "§4.2 requires 2N but App. B accepts block or distributed redundancy."},
    ],
}

FAKE_REPLIES: dict[str, dict] = {
    "intake:p1.extract": {"text": _EXTRACTION, "usage": {"in": 9000, "out": 900}},
    "intake:p1.drawing": {"text": {"grid_x": ["1", "2", "3", "4", "5", "6"], "grid_y": ["A", "B", "C", "D"],
                                   "overall_mm": [60000, 36000]}, "usage": {"in": 2000, "out": 60}},
    "orchestrator:p1.plan": {"text": {"summary": "The brief is complete; the redundancy conflict between §4.2 and "
                                                 "App. B needs the engineer.", "ask_human": ["Q-redundancy"]}},
    "layout:p2.place_racks": {"tool_calls": [{"name": "place_racks", "args": {}}],
                              "text": "Layout placed the racks in rows R1 and R3 with the engine default."},
    "power:p2.power_options": {"tool_calls": [{"name": "enumerate_topologies", "args": {}}],
                               "text": {"offer": ["2N", "DR", "BLOCK"],
                                        "reason": "All three pass R01 at their minimum rating; §4.2 asks for 2N and "
                                                  "App. B allows the others."}},
    "cooling:p2.cooling_sizing": {"tool_calls": [{"name": "size_cdus", "args": {}},
                                                 {"name": "hydraulic_zones", "args": {}}],
                                  "text": "Cooling sized the CDUs with N+1 in each zone."},
    "procurement:p2.annotate_options": {"tool_calls": [{"name": "annotate_options", "args": {}}],
                                        "text": "TX-2500 misses the §2.3 lead-time limit, so the engine swapped it "
                                                "for TX-3150, which ships from stock."},
    "power:p2.power_recheck": {"tool_calls": [{"name": "recheck_swapped_options", "args": {}}],
                               "text": "Power re-ran short circuit on the TX-3150 options; R01, R04 and R04b still "
                                       "pass."},
    "power:p3.select_option": {"text": "2N follows §4.2 with zero single points of failure at the lowest "
                                       "qualifying cost."},
    "layout:p3.route": {"tool_calls": [{"name": "route_busways", "args": {}}],
                        "text": "Layout routed the A feeders along the south corridor and the B feeders along the "
                                "north corridor."},
    "power:p3.fix.1:R05:FA-01": {"text": {"candidate_id": "FA-01:cable-CBL-240-8P",
                                          "reason": "The cable feeder gives FA-01 the largest voltage-drop margin per "
                                                    "dollar under §4.6."}},
    "cooling:p3.fix.1:R11:H-Z2": {"text": {"candidate_id": "H-Z2:local-drop",
                                           "reason": "The local drop changes the fewest pipe segments and clears R11 at "
                                                     "the FB-03 crossing."}},
    "docs:p3.docs": {"text": {"order": ["summary", "requirements", "options", "findings", "fixes", "ledger", "boq"],
                              "summary": "The 2N design passes every check after fixes to FA-01 and H-Z2."}},
    "copilot:explain:R05:FA-01": {"text": "FA-01 has a voltage drop of {value}, above the {limit} limit in §4.6. "
                                          "It is the longest A-side feeder from A1."},
    "asset:grid": {"text": {"option": "ACSR-Zebra", "reason": "Zebra meets the ampacity need with the lowest "
                                                              "losses."}},
    "asset:solar": {"text": {"option": "STR-28", "reason": "STR-28 stays under the inverter limit on cold "
                                                           "mornings."}},
}


def build_fake_scenarios(root: Path, tender_yaml: Path, geometry_yaml: Path, ground_truth_yaml: Path) -> Path:
    root = Path(root)
    hall = root / "hall_a"
    (hall / "out").mkdir(parents=True, exist_ok=True)
    for src, name in ((tender_yaml, "tender.yaml"), (geometry_yaml, "geometry.yaml"),
                      (ground_truth_yaml, "ground_truth.yaml")):
        shutil.copy(src, hall / name)
    render_tender_pdf(load_tender(tender_yaml), hall / "out" / "tender-hall-a.pdf")
    render_drawing(load_geometry(geometry_yaml), hall / "out" / "hall-a.dxf", hall / "out" / "hall-a-plan.pdf")
    (root / "grid").mkdir(exist_ok=True)
    (root / "solar").mkdir(exist_ok=True)
    return root
```

- [ ] **Step 5: Run tests**

Run: `cd services/api && uv run pytest tests/runs/test_runs_fakes.py -q`
Expected: `6 passed`

- [ ] **Step 6: Commit**

```bash
git add services/api/kirchhoff/agents/ports.py services/api/kirchhoff/runs services/api/tests/runs
git commit -m "feat(runs): enterprise/ERP ports, FixCandidate compat shim, deterministic engine + sandbox fakes

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Step machinery — event writer wiring, blobs, outputs, Deps, PhaseContext and transactional `run_step` (Tue 14)

**Files:**
- Create: `services/api/kirchhoff/runs/events.py`, `services/api/kirchhoff/runs/blobs.py`, `services/api/kirchhoff/runs/outputs.py`, `services/api/kirchhoff/runs/deps.py`, `services/api/kirchhoff/runs/steps.py`
- Modify: `services/api/kirchhoff/runs/fakes.py` (append `CheckedStore` and `build_fake_deps`), `services/api/tests/runs/conftest.py` (append fixtures)
- Test: `services/api/tests/runs/test_runs_steps.py`

**Interfaces:**
- Consumes: `EventWriter` (P0 fix wave + Task 6: `emit(..., step=...)`, `flush()`, `close()`, `fence()`; never subclassed), `Store.transact`, `Store.list_docs(order_by=, descending=, limit=)`, `firestore_safe_problems`, `json_size_bytes` (`kirchhoff.store.validate`), `holds_lease`, `run_path`, `acquire_lease` (Task 6), `sanitize`, `allowed_ids_for` (Task 4), `AgentSpec`, `AgentResult`, `run_json`, `ReplayRunner` (Task 5), `ErpSnapshot`, `EnterpriseClient` (Task 7), `FakeEngine`, `FakeEnterprise`, `FAKE_REPLIES` (Task 7).
- Produces:
  - One plain `EventWriter` per phase attempt, shared by parallel steps; every event passes `step=` (no subclass, no `set_step`). `next_seq(store, run_path) -> int` returns the highest existing `seq` + 1 (`list_docs(order_by="seq", descending=True, limit=1)`).
  - `BlobStore` protocol: `put(path, data, content_type) -> str`, `get(path) -> bytes`, `exists(path) -> bool`, `delete_prefix(prefix) -> int`, `signed_url(path, ttl_s=600) -> str`. Implementations: `MemoryBlobStore(public_base="https://storage.example.test")` (`.blobs` dict; with `public_base=None` it cannot sign and `signed_url` raises `NotImplementedError`, so `/api/files` serves the bytes inline — local `KIRCHHOFF_FAKES=1`/`KIRCHHOFF_BLOBS=memory` development) and `GcsBlobStore(bucket="ordinal-mep.firebasestorage.app")` (lazy client; V4 signed URLs signed through IAM on Cloud Run).
  - `pack_outputs(blobs, run_path, step_id, data) -> tuple[str, dict]` and `load_outputs(store, blobs, run_path, step_id) -> dict | None`. Outputs are stored as `{"step", "json"}` or `{"step", "blob", "sha256"}` (R3).
  - `Deps` dataclass with fields `store, engine, runner, enterprise, blobs, scenarios_dir, seed_dir, voice_runner=None, exporter=None, asset_engines={}, phases=None, spawn=thread_spawn, clock=time.time, owner=<host-pid-rand>, heartbeat_s=15.0, erp_ttl_s=300.0` and methods `.scenario()` (cached `engine.load_scenario("hall_a", scenarios_dir)`), `.erp() -> ErpSnapshot` (cached for 300 s) and `.inputs() -> InputFiles(tender_pdf, plan_pdf, dxf, ground_truth)`.
  - `kirchhoff.runs.steps`: `LeaseLost`, `ParkAtGate(gate, message="")`, `StepOutput(data: dict, docs: list[tuple[str, dict]] = [])`, `PhaseOutcome(gate, run_patch={}, metrics={}, forced=False, message="")`, `AGENT_LABEL`.
  - `PhaseContext(deps, uid, rid, phase, attempt, events, lease_lost=None, prior_active_s=0.0)` with `.run_path`, `.ws_path`, `.run()`, `.scenario()`, `.erp()`, `.outputs(step_id)`, `.emit(step, agent, kind, title, detail="", payload=None)` (payloads over 9,000 bytes are truncated; once the heartbeat reports a lost lease it fences the writer and raises `LeaseLost`), `.narrate(step, agent, text, allowed, step_title, template=None) -> str` (sanitized `message` event; the default template is "{Agent} completed {step_title}."), `.ledger(step, agent, kind, text) -> LedgerEntry`, `.tool(step, agent, fn) -> fn` (emits `tool_call`/`tool_result`), `.agent(spec, step, message, tools=(), attachments=(), key=None) -> AgentResult | None` and `.agent_json(spec, step, message, schema, tools=(), attachments=(), key=None) -> model | None` (on failure: `status` event and `None`; tokens go into `.metrics`), `.allowed(*models, extra=()) -> set[str]`, `.active_s()`, and `.metrics`.
  - `run_step(ctx, step_id, fn: Callable[[], StepOutput]) -> dict`. A begin transaction checks the lease, skips the step if it is done (returning its committed outputs), and writes the `running` step doc. The function's events are flushed, then a commit transaction checks `lease.owner/attempt` and writes `StepOutput.docs` + outputs + `{status: "done", attempt}`. A lost lease raises `LeaseLost`, and a failure (including a `StepOutput.docs` entry that fails `firestore_safe_problems`) marks the step `failed` and re-raises. All transactions use `Store.transact`; `fn` returns `[]` to abort.
  - `build_fake_deps(store, scenarios_dir, seed_dir=None, replies=None, **overrides) -> Deps` (fakes plus `ReplayRunner({**FAKE_REPLIES, **replies})`).
  - `CheckedStore(MemoryStore)` (test support in `fakes.py`): records `firestore_safe_problems` for every written document in `.problems`; the `firestore_safe` fixtures assert it stays empty.

- [ ] **Step 1: Append shared fixtures to the runs conftest**

Append to `services/api/tests/runs/conftest.py`:
```python
import uuid
from pathlib import Path

import pytest

from kirchhoff.contracts import RunRecord
from kirchhoff.runs.fakes import CheckedStore, build_fake_deps, build_fake_scenarios

INTAKE_FIX = Path(__file__).resolve().parents[1] / "intake" / "fixtures"
GROUND_TRUTH = Path(__file__).resolve().parents[4] / "scenarios" / "hall_a" / "ground_truth.yaml"


@pytest.fixture(scope="session")
def scen_dir(tmp_path_factory):
    return build_fake_scenarios(tmp_path_factory.mktemp("scenarios"), INTAKE_FIX / "tender.yaml",
                                INTAKE_FIX / "geometry.yaml", GROUND_TRUTH)


@pytest.fixture
def deps(scen_dir, tmp_path):
    return build_fake_deps(CheckedStore(), scen_dir, seed_dir=tmp_path, spawn=lambda fn: fn(), heartbeat_s=3600.0)


@pytest.fixture
def make_run(deps):
    def _make(uid: str = "u1", autonomy: str = "ask") -> str:
        rid = uuid.uuid4().hex[:12]
        rec = RunRecord(id=rid, project_id="hall-b", status="running", autonomy=autonomy, phase="p1",
                        started_at=deps.clock())
        deps.store.set_doc(f"workspaces/{uid}/runs/{rid}", rec.model_dump(mode="json"))
        return rid
    return _make


@pytest.fixture
def firestore_safe():
    def _check(store) -> None:
        assert isinstance(store, CheckedStore)
        assert not store.problems, store.problems[:3]
    return _check
```

- [ ] **Step 2: Write the failing tests**

`services/api/tests/runs/test_runs_steps.py`:
```python
import pytest

from kirchhoff.agents.runner import AgentSpec, ReplayRunner
from kirchhoff.runs.events import next_seq
from kirchhoff.runs.leases import acquire_lease, run_path
from kirchhoff.runs.outputs import load_outputs
from kirchhoff.runs.steps import LeaseLost, PhaseContext, StepOutput, run_step
from kirchhoff.store.events import EventWriter


@pytest.fixture
def ctx(deps, make_run):
    rid = make_run()
    attempt = acquire_lease(deps.store, "u1", rid, deps.owner, deps.clock(), {"phase": "p2"})
    rp = run_path("u1", rid)
    events = EventWriter(deps.store, rp, phase="p2", step="p2.start", attempt=attempt,
                         start_seq=next_seq(deps.store, rp), flush_interval_s=999)  # run_step flushes
    return PhaseContext(deps, "u1", rid, "p2", attempt, events)


def _events(ctx):
    return ctx.deps.store.list_docs(f"{ctx.run_path}/events")


def test_commit_writes_outputs_and_done_marker_and_rerun_skips(ctx):
    calls = []

    def fn():
        calls.append(1)
        ctx.emit("p2.x", "layout", "status", "working")
        return StepOutput(data={"n": len(calls)}, docs=[("workspaces/u1/revisions/x-r1", {"id": "x-r1"})])

    assert run_step(ctx, "p2.x", fn) == {"n": 1}
    step = ctx.deps.store.get_doc(f"{ctx.run_path}/steps/p2.x")
    assert step["status"] == "done" and step["attempt"] == ctx.attempt
    assert step["outputs_ref"] == f"{ctx.run_path}/outputs/p2.x"
    assert ctx.deps.store.get_doc("workspaces/u1/revisions/x-r1") == {"id": "x-r1"}
    assert run_step(ctx, "p2.x", fn) == {"n": 1} and calls == [1]
    (ev,) = _events(ctx)
    assert (ev["step"], ev["attempt"], ev["seq"]) == ("p2.x", ctx.attempt, 1)


def test_stale_worker_cannot_commit_or_start(ctx):
    def takeover():
        run = ctx.deps.store.get_doc(ctx.run_path)
        ctx.deps.store.set_doc(ctx.run_path, {**run, "lease": {"owner": "other", "attempt": 9, "heartbeat_at": 1e12}})
        return StepOutput(data={"x": 1})

    with pytest.raises(LeaseLost):
        run_step(ctx, "p2.y", takeover)
    assert ctx.deps.store.get_doc(f"{ctx.run_path}/steps/p2.y")["status"] == "running"
    assert load_outputs(ctx.deps.store, ctx.deps.blobs, ctx.run_path, "p2.y") is None
    with pytest.raises(LeaseLost):
        run_step(ctx, "p2.z", lambda: StepOutput(data={}))


def test_failed_step_is_marked_failed(ctx):
    def boom():
        raise ValueError("engine exploded")

    with pytest.raises(ValueError):
        run_step(ctx, "p2.f", boom)
    assert ctx.deps.store.get_doc(f"{ctx.run_path}/steps/p2.f")["status"] == "failed"


def test_large_outputs_go_to_blob_storage(ctx):
    big = {"blob": "x" * 500_000}
    run_step(ctx, "p2.big", lambda: StepOutput(data=big))
    doc = ctx.deps.store.get_doc(f"{ctx.run_path}/outputs/p2.big")
    assert "blob" in doc and len(doc["sha256"]) == 64 and "json" not in doc
    assert load_outputs(ctx.deps.store, ctx.deps.blobs, ctx.run_path, "p2.big") == big


def test_emit_truncates_payload_and_narrate_sanitizes(ctx):
    def fn():
        ctx.emit("p2.n", "layout", "tool_result", "big", payload={"rows": ["x" * 100] * 200})
        ctx.narrate("p2.n", "power", "The drop is 2.16% on FA-01.", {"FA-01"}, "fix selection")
        ctx.narrate("p2.n", "power", "FA-01 fails R05.", {"FA-01"}, "fix selection")
        return StepOutput(data={})

    run_step(ctx, "p2.n", fn)
    big, dirty, clean = _events(ctx)
    assert big["payload"]["truncated"] is True
    assert dirty["title"] == "Power completed fix selection." and clean["title"] == "FA-01 fails R05."


def test_tool_wrapper_and_agent_fallback(ctx):
    ctx.deps.runner = ReplayRunner({"layout:p2.t": {"tool_calls": [{"name": "place_racks", "args": {"n": 2}}],
                                                    "text": "ok", "usage": {"in": 5, "out": 1}},
                                    "power:p2.t": {"raise": "vertex down"}})

    def place_racks(n: int = 0) -> dict:
        """Place racks."""
        return {"placed": n}

    def fn():
        res = ctx.agent(AgentSpec("layout", "x"), "p2.t", "go", tools=[ctx.tool("p2.t", "layout", place_racks)])
        assert res.tool_calls[0].result == {"placed": 2}
        assert ctx.agent(AgentSpec("power", "x"), "p2.t", "go") is None
        return StepOutput(data={})

    run_step(ctx, "p2.t", fn)
    kinds = [(e["agent"], e["kind"]) for e in _events(ctx)]
    assert kinds == [("layout", "tool_call"), ("layout", "tool_result"), ("power", "status")]
    assert ctx.metrics["tokens_in"] == 5


def test_next_seq_continues_from_highest_written(ctx):
    ctx.deps.store.set_doc(f"{ctx.run_path}/events/000041", {"seq": 41})
    assert next_seq(ctx.deps.store, ctx.run_path) == 42


def test_unsafe_step_docs_fail_the_step_before_commit(ctx):
    with pytest.raises(ValueError, match="Firestore-safe"):
        run_step(ctx, "p2.bad", lambda: StepOutput(data={}, docs=[("workspaces/u1/x/y", {"cols": [[0.0, 1.0]]})]))
    assert ctx.deps.store.get_doc(f"{ctx.run_path}/steps/p2.bad")["status"] == "failed"
    assert ctx.deps.store.get_doc("workspaces/u1/x/y") is None


def test_lost_lease_fences_the_writer(ctx):
    def fn():
        ctx.emit("p2.l", "layout", "status", "before")
        ctx.lease_lost.set()  # the heartbeat thread saw another owner
        ctx.emit("p2.l", "layout", "status", "after")
        return StepOutput(data={})

    with pytest.raises(LeaseLost):
        run_step(ctx, "p2.l", fn)
    ctx.events.close()
    assert _events(ctx) == []  # a stale worker writes no events
```

- [ ] **Step 3: Run to verify failure**

Run: `cd services/api && uv run pytest tests/runs/test_runs_steps.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'kirchhoff.runs.events'`

- [ ] **Step 4: Implement events, blobs, outputs and Deps**

`services/api/kirchhoff/runs/events.py`:
```python
"""Event seq continuity. Events themselves are written by the P0 EventWriter: one writer per phase attempt
(spec §11: single writer assigns seq), shared by parallel steps, every event tagged with emit(..., step=...)."""
from kirchhoff.store import Store


def next_seq(store: Store, run_path: str) -> int:
    """Resume and later phases continue seq from the highest value already written (spec v4.1 §6.2)."""
    last = store.list_docs(f"{run_path}/events", order_by="seq", descending=True, limit=1)
    return int(last[0].get("seq", 0)) + 1 if last else 1
```

`services/api/kirchhoff/runs/blobs.py`:
```python
import threading
from datetime import timedelta
from typing import Protocol

BUCKET = "ordinal-mep.firebasestorage.app"


class BlobStore(Protocol):
    def put(self, path: str, data: bytes, content_type: str) -> str: ...
    def get(self, path: str) -> bytes: ...
    def exists(self, path: str) -> bool: ...
    def delete_prefix(self, prefix: str) -> int: ...
    def signed_url(self, path: str, ttl_s: int = 600) -> str: ...


class MemoryBlobStore:
    """In-process blobs. `public_base=None` means URLs cannot be signed (local development): /api/files then
    serves the bytes inline instead of a signed URL."""

    def __init__(self, public_base: str | None = "https://storage.example.test") -> None:
        self.blobs: dict[str, tuple[bytes, str]] = {}
        self.public_base = public_base
        self._lock = threading.Lock()

    def put(self, path: str, data: bytes, content_type: str) -> str:
        with self._lock:
            self.blobs[path] = (bytes(data), content_type)
        return path

    def get(self, path: str) -> bytes:
        with self._lock:
            return self.blobs[path][0]

    def exists(self, path: str) -> bool:
        with self._lock:
            return path in self.blobs

    def delete_prefix(self, prefix: str) -> int:
        with self._lock:
            keys = [k for k in self.blobs if k.startswith(prefix)]
            for k in keys:
                del self.blobs[k]
            return len(keys)

    def signed_url(self, path: str, ttl_s: int = 600) -> str:
        if not self.exists(path):
            raise KeyError(path)
        if self.public_base is None:
            raise NotImplementedError("memory blobs cannot be signed")
        return f"{self.public_base}/{path}?ttl={ttl_s}"


class GcsBlobStore:
    def __init__(self, bucket: str = BUCKET) -> None:
        self._name = bucket
        self._bucket = None
        self._lock = threading.Lock()

    def _b(self):
        with self._lock:
            if self._bucket is None:
                from google.cloud import storage
                self._bucket = storage.Client(project="ordinal-mep").bucket(self._name)
            return self._bucket

    def put(self, path: str, data: bytes, content_type: str) -> str:
        self._b().blob(path).upload_from_string(data, content_type=content_type)
        return path

    def get(self, path: str) -> bytes:
        return self._b().blob(path).download_as_bytes()

    def exists(self, path: str) -> bool:
        return self._b().blob(path).exists()

    def delete_prefix(self, prefix: str) -> int:
        n = 0
        for b in self._b().client.list_blobs(self._name, prefix=prefix):
            b.delete()
            n += 1
        return n

    def signed_url(self, path: str, ttl_s: int = 600) -> str:
        import google.auth
        from google.auth.transport.requests import Request

        creds, _ = google.auth.default()
        creds.refresh(Request())
        kw = {}
        if getattr(creds, "service_account_email", None):  # Cloud Run: sign through IAM signBlob
            kw = {"service_account_email": creds.service_account_email, "access_token": creds.token}
        return self._b().blob(path).generate_signed_url(version="v4", expiration=timedelta(seconds=ttl_s),
                                                        method="GET", **kw)
```

`services/api/kirchhoff/runs/outputs.py`:
```python
"""Step outputs (R3): JSON string in Firestore (avoids nested-array limits), or Cloud Storage above 400 KB."""
import hashlib
import json

from kirchhoff.store import Store

from .blobs import BlobStore

INLINE_MAX_BYTES = 400_000


def outputs_path(run_path: str, step_id: str) -> str:
    return f"{run_path}/outputs/{step_id}"


def pack_outputs(blobs: BlobStore, run_path: str, step_id: str, data: dict) -> tuple[str, dict]:
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    path = outputs_path(run_path, step_id)
    if len(raw) <= INLINE_MAX_BYTES:
        return path, {"step": step_id, "json": raw.decode("utf-8")}
    blob = f"{run_path}/outputs/{step_id}.json"
    blobs.put(blob, raw, "application/json")
    return path, {"step": step_id, "blob": blob, "sha256": hashlib.sha256(raw).hexdigest()}


def load_outputs(store: Store, blobs: BlobStore, run_path: str, step_id: str) -> dict | None:
    doc = store.get_doc(outputs_path(run_path, step_id))
    if doc is None:
        return None
    raw = doc["json"] if "json" in doc else blobs.get(doc["blob"]).decode("utf-8")
    return json.loads(raw)
```

`services/api/kirchhoff/runs/deps.py`:
```python
import os
import socket
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kirchhoff.agents.ports import EnterpriseClient, ErpSnapshot
from kirchhoff.agents.runner import AgentRunner
from kirchhoff.store import Store

from .blobs import BlobStore


@dataclass(frozen=True)
class InputFiles:
    tender_pdf: Path
    plan_pdf: Path
    dxf: Path
    ground_truth: Path


def thread_spawn(fn: Callable[[], None]) -> None:
    threading.Thread(target=fn, daemon=True).start()


def _owner_id() -> str:
    return f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:6]}"


@dataclass
class Deps:
    store: Store
    engine: Any  # kirchhoff.engine.api module (or FakeEngine): the facade functions by name
    runner: AgentRunner
    enterprise: EnterpriseClient
    blobs: BlobStore
    scenarios_dir: Path
    seed_dir: Path
    voice_runner: AgentRunner | None = None
    exporter: Any = None  # kirchhoff.agents.docs_export.Exporter; None means StubExporter
    asset_engines: dict[str, Callable[[Path], dict]] = field(default_factory=dict)
    phases: dict[str, Callable] | None = None  # test override of the phase registry
    spawn: Callable[[Callable[[], None]], None] = thread_spawn
    clock: Callable[[], float] = time.time
    owner: str = field(default_factory=_owner_id)
    heartbeat_s: float = 15.0
    erp_ttl_s: float = 300.0

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self._scenario = None
        self._erp: ErpSnapshot | None = None
        self._erp_at = 0.0

    def scenario(self):
        with self._lock:
            if self._scenario is None:
                self._scenario = self.engine.load_scenario("hall_a", self.scenarios_dir)
            return self._scenario

    def erp(self) -> ErpSnapshot:
        with self._lock:
            now = time.monotonic()
            if self._erp is None or now - self._erp_at > self.erp_ttl_s:
                self._erp = ErpSnapshot(self.enterprise.list_materials())
                self._erp_at = now
            return self._erp

    def inputs(self) -> InputFiles:
        hall = Path(self.scenarios_dir) / "hall_a"
        return InputFiles(tender_pdf=hall / "out" / "tender-hall-a.pdf", plan_pdf=hall / "out" / "hall-a-plan.pdf",
                          dxf=hall / "out" / "hall-a.dxf", ground_truth=hall / "ground_truth.yaml")
```

Append to `services/api/kirchhoff/runs/fakes.py` (move the two new imports to the top of the module):
```python
from kirchhoff.store.memory import MemoryStore
from kirchhoff.store.validate import firestore_safe_problems


class CheckedStore(MemoryStore):
    """MemoryStore that records Firestore-safety problems (R7) in every written document (tests only)."""

    def __init__(self) -> None:
        super().__init__()
        self.problems: list[tuple[str, list[str]]] = []

    def _check(self, path: str, data: dict | None) -> None:
        if data is not None and (found := firestore_safe_problems(data)):
            self.problems.append((path, found[:3]))

    def set_doc(self, path: str, data: dict) -> None:
        self._check(path, data)
        super().set_doc(path, data)

    def update_doc(self, path: str, data: dict) -> None:
        self._check(path, data)
        super().update_doc(path, data)

    def batch_set(self, items: list[tuple[str, dict]]) -> None:
        for path, data in items:
            self._check(path, data)
        super().batch_set(items)

    def transact(self, read_paths, fn):
        def checked(snapshot):
            writes = fn(snapshot)
            for path, data in writes:
                self._check(path, data)
            return writes
        return super().transact(read_paths, checked)


def build_fake_deps(store, scenarios_dir: Path, seed_dir: Path | None = None, replies: dict | None = None,
                    **overrides):
    from kirchhoff.agents.runner import ReplayRunner

    from .blobs import MemoryBlobStore
    from .deps import Deps

    engine = overrides.pop("engine", None) or FakeEngine()
    kw = dict(store=store, engine=engine, runner=ReplayRunner({**FAKE_REPLIES, **(replies or {})}),
              enterprise=FakeEnterprise(), blobs=MemoryBlobStore(), scenarios_dir=Path(scenarios_dir),
              seed_dir=Path(seed_dir or scenarios_dir), voice_runner=ReplayRunner(dict(replies or {})),
              asset_engines={k: getattr(engine, f"evaluate_{k}") for k in ("grid", "solar")
                             if hasattr(engine, f"evaluate_{k}")})
    kw.update(overrides)
    return Deps(**kw)
```

- [ ] **Step 5: Implement PhaseContext and run_step**

`services/api/kirchhoff/runs/steps.py`:
```python
"""Steps (spec v4.1 §6.2): events stream; start and commit are transactions guarded by lease.attempt."""
import functools
import json
import logging
import threading
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel

from kirchhoff.agents.runner import AgentResult, AgentSpec, Attachment, run_json
from kirchhoff.agents.trust import allowed_ids_for, sanitize
from kirchhoff.contracts import DesignModel, LedgerEntry, RunEvent, StepRecord
from kirchhoff.store.events import EventWriter
from kirchhoff.store.validate import firestore_safe_problems, json_size_bytes

from .deps import Deps
from .leases import holds_lease, run_path
from .outputs import load_outputs, pack_outputs

log = logging.getLogger("kirchhoff.runs")
PAYLOAD_MAX = 9_000  # event docs stay < 10 KB (spec §11)
TXN_DOC_LIMIT = 400  # Firestore transaction write limit is 500
AGENT_LABEL = {"intake": "Intake", "orchestrator": "Orchestrator", "layout": "Layout", "power": "Power",
               "cooling": "Cooling", "procurement": "Procurement", "checker": "Checker", "docs": "Docs",
               "copilot": "Co-pilot", "asset": "Asset agent", "system": "Kirchhoff"}


class LeaseLost(Exception):
    """Another worker holds the run lease; stop without writing."""


class ParkAtGate(Exception):
    def __init__(self, gate: str, message: str = "") -> None:
        super().__init__(message)
        self.gate, self.message = gate, message


@dataclass
class StepOutput:
    data: dict
    docs: list[tuple[str, dict]] = field(default_factory=list)


@dataclass
class PhaseOutcome:
    gate: Literal["plan", "option", "review"] | None
    run_patch: dict = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    forced: bool = False
    message: str = ""


class PhaseContext:
    def __init__(self, deps: Deps, uid: str, rid: str, phase: str, attempt: int, events: EventWriter,
                 lease_lost: threading.Event | None = None, prior_active_s: float = 0.0) -> None:
        self.deps, self.uid, self.rid, self.phase, self.attempt = deps, uid, rid, phase, attempt
        self.events = events
        self.lease_lost = lease_lost or threading.Event()
        self.prior_active_s = prior_active_s
        self.started = deps.clock()
        self.metrics: dict[str, float] = {}
        self._mlock = threading.Lock()

    @property
    def run_path(self) -> str:
        return run_path(self.uid, self.rid)

    @property
    def ws_path(self) -> str:
        return f"workspaces/{self.uid}"

    def run(self) -> dict:
        return self.deps.store.get_doc(self.run_path) or {}

    def scenario(self):
        return self.deps.scenario()

    def erp(self):
        return self.deps.erp()

    def active_s(self) -> float:
        return self.prior_active_s + (self.deps.clock() - self.started)

    def outputs(self, step_id: str) -> dict:
        data = load_outputs(self.deps.store, self.deps.blobs, self.run_path, step_id)
        if data is None:
            raise KeyError(f"no committed outputs for {step_id}")
        return data

    def emit(self, step: str, agent: str, kind: str, title: str, detail: str = "",
             payload: dict[str, Any] | None = None) -> RunEvent:
        if self.lease_lost.is_set():  # another worker owns the run: drop pending events, write nothing more
            self.events.fence()
            raise LeaseLost(step)
        payload = json.loads(json.dumps(payload or {}, default=str))  # engine tuples → lists, numpy scalars → str
        if json_size_bytes(payload) > PAYLOAD_MAX:
            payload = {"truncated": True, "keys": sorted(payload)[:50]}
        # The P0 writer validates Firestore safety (ValueError) and assigns seq; `step=` tags parallel steps.
        return self.events.emit(agent, kind, title, detail, payload, step=step)

    def narrate(self, step: str, agent: str, text: str, allowed: Iterable[str], step_title: str,
                template: str | None = None) -> str:
        clean = sanitize(text, allowed, template or f"{AGENT_LABEL.get(agent, agent)} completed {step_title}.")
        self.emit(step, agent, "message", clean)
        return clean

    def ledger(self, step: str, agent: str, kind: str, text: str) -> LedgerEntry:
        entry = LedgerEntry(kind=kind, agent=agent, text=text)
        self.emit(step, agent, "ledger", text, payload={"entry": entry.model_dump()})
        return entry

    def tool(self, step: str, agent: str, fn: Callable[..., dict]) -> Callable[..., dict]:
        @functools.wraps(fn)
        def wrapped(**kwargs):
            self.emit(step, agent, "tool_call", fn.__name__, payload={"tool": fn.__name__, "args": kwargs})
            summary = fn(**kwargs)
            self.emit(step, agent, "tool_result", f"{fn.__name__} done",
                      payload={"tool": fn.__name__, "summary": summary})
            return summary
        return wrapped

    def add_tokens(self, *results: AgentResult | None) -> None:
        with self._mlock:
            for r in results:
                if r is not None:
                    self.metrics["tokens_in"] = self.metrics.get("tokens_in", 0.0) + r.tokens_in
                    self.metrics["tokens_out"] = self.metrics.get("tokens_out", 0.0) + r.tokens_out

    def _unavailable(self, spec: AgentSpec, step: str, exc: Exception) -> None:
        log.warning("agent %s failed at %s: %r", spec.name, step, exc)
        self.emit(step, spec.name, "status", f"{AGENT_LABEL.get(spec.name, spec.name)} agent unavailable; "
                  "engine default used", detail=type(exc).__name__)

    def agent(self, spec: AgentSpec, step: str, message: str, tools: Sequence[Callable] = (),
              attachments: Sequence[Attachment] = (), key: str | None = None) -> AgentResult | None:
        try:
            res = self.deps.runner.run(spec, key or step, message, tools, attachments)
        except Exception as exc:
            self._unavailable(spec, step, exc)
            return None
        self.add_tokens(res)
        return res

    def agent_json(self, spec: AgentSpec, step: str, message: str, schema: type[BaseModel],
                   tools: Sequence[Callable] = (), attachments: Sequence[Attachment] = (),
                   key: str | None = None) -> BaseModel | None:
        try:
            parsed, res = run_json(self.deps.runner, spec, key or step, message, schema, tools, attachments)
        except Exception as exc:
            self._unavailable(spec, step, exc)
            return None
        self.add_tokens(res)
        return parsed

    def allowed(self, *models: DesignModel | None, extra: Iterable[str] = ()) -> set[str]:
        return allowed_ids_for(*models, extra=[*extra, *self.erp().ids()])


def _check_docs(docs: list[tuple[str, dict]]) -> None:
    for path, doc in docs:
        if problems := firestore_safe_problems(doc):
            raise ValueError(f"step doc {path} is not Firestore-safe: {problems[:3]}")


def run_step(ctx: PhaseContext, step_id: str, fn: Callable[[], StepOutput]) -> dict:
    if ctx.lease_lost.is_set():
        raise LeaseLost(step_id)
    deps, store = ctx.deps, ctx.deps.store
    step_path = f"{ctx.run_path}/steps/{step_id}"
    started = deps.clock()
    state: dict[str, bool] = {}

    def begin(snap: dict[str, dict | None]):
        state.clear()  # Firestore may retry the transaction function
        run, step = snap[ctx.run_path], snap[step_path]
        if not holds_lease(run, deps.owner, ctx.attempt):
            state["lost"] = True
            return []
        if step and step.get("status") == "done":
            state["done"] = True
            return []
        rec = StepRecord(id=step_id, phase=ctx.phase, status="running", attempt=ctx.attempt, started_at=started)
        return [(step_path, rec.model_dump())]

    store.transact([ctx.run_path, step_path], begin)
    if state.get("lost"):
        ctx.lease_lost.set()
        ctx.events.fence()
        raise LeaseLost(step_id)
    if state.get("done"):
        return ctx.outputs(step_id)
    try:
        out = fn()
        _check_docs(out.docs)
    except (LeaseLost, ParkAtGate):
        raise
    except Exception:
        failed = StepRecord(id=step_id, phase=ctx.phase, status="failed", attempt=ctx.attempt, started_at=started,
                            finished_at=deps.clock())
        store.transact([ctx.run_path], lambda snap: [(step_path, failed.model_dump())]
                       if holds_lease(snap[ctx.run_path], deps.owner, ctx.attempt) else [])
        raise
    ctx.events.flush()
    out_path, out_doc = pack_outputs(deps.blobs, ctx.run_path, step_id, out.data)
    docs = list(out.docs)
    if len(docs) > TXN_DOC_LIMIT:  # idempotent pre-writes; the done marker still lands only in the commit
        store.batch_set(docs[:-TXN_DOC_LIMIT])
        docs = docs[-TXN_DOC_LIMIT:]
    done = StepRecord(id=step_id, phase=ctx.phase, status="done", attempt=ctx.attempt, outputs_ref=out_path,
                      started_at=started, finished_at=deps.clock())

    def commit(snap: dict[str, dict | None]):
        if not holds_lease(snap[ctx.run_path], deps.owner, ctx.attempt):
            return []
        return [*docs, (out_path, out_doc), (step_path, done.model_dump())]

    if not store.transact([ctx.run_path], commit):
        ctx.lease_lost.set()
        ctx.events.fence()
        raise LeaseLost(step_id)
    return json.loads(json.dumps(out.data))
```

- [ ] **Step 6: Run tests**

Run: `cd services/api && uv run pytest tests/runs -q`
Expected: all runs tests pass (`19 passed`).

- [ ] **Step 7: Commit**

```bash
git add services/api/kirchhoff/runs services/api/tests/runs
git commit -m "feat(runs): EventWriter wiring with per-event steps and fencing, blob/outputs storage, Deps, PhaseContext, transactional run_step

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Intake extraction (Gemini native PDF) and brief building (Tue 14)

**Files:**
- Create: `services/api/kirchhoff/intake/extract.py`, `services/api/kirchhoff/intake/brief.py`
- Test: `services/api/tests/intake/test_intake_extract_brief.py`

**Interfaces:**
- Consumes: `run_json`, `Attachment`, `AgentResult` (Task 5); `INTAKE`, `INTAKE_DRAWING` (Task 5 specs); `DrawingRead` (Task 2); `PdfText`, `verify_quote`, `QuoteCheck` (Task 3); `sanitize` (Task 4); `normalize` (Task 1); `FAKE_REPLIES` (Task 7, used in the tests).
- Produces:
  - `ExtractedRequirement(key, clause, page, verbatim_quote, value: float | str | None, unit: str | None)`, `ExtractedContradiction(topic, clause_a, page_a, quote_a, value_a, clause_b, page_b, quote_b, value_b, summary)`, and `TenderExtraction(requirements, contradictions)`.
  - `extract_tender(runner, pdf_bytes) -> tuple[TenderExtraction, AgentResult]` (key `p1.extract`, PDF attached as `application/pdf`) and `read_drawing(runner, plan_pdf_bytes) -> tuple[DrawingRead, AgentResult]` (key `p1.drawing`).
  - `canonical_topology(s) -> "2N" | "DR" | "BLOCK" | None`.
  - `UNVERIFIED_TEMPLATE` and `build_brief(project_id, doc_id, extraction, verify: Callable[[int, str, Any], QuoteCheck], drawing_check: dict, allowed: set[str]) -> DesignBrief`. Requirement ids are `REQ-{key}` (duplicates get `-2`, `-3`). Verified requirement text is the verbatim quote (R12). A contradiction becomes `OpenQuestion(id="Q-{topic}", options=[main_value, "compare_all"], default_resolution=main_value)` only if both quotes verify; the main body (`§…`) beats an appendix (`App. …`).

- [ ] **Step 1: Write the failing tests**

`services/api/tests/intake/test_intake_extract_brief.py`:
```python
from kirchhoff.agents.runner import ReplayRunner
from kirchhoff.intake.brief import UNVERIFIED_TEMPLATE, build_brief, canonical_topology
from kirchhoff.intake.extract import ExtractedContradiction, TenderExtraction, extract_tender, read_drawing
from kirchhoff.intake.verify import PdfText, verify_quote
from kirchhoff.runs.fakes import FAKE_REPLIES

AGREES = {"agrees": True, "differences": []}


def _brief(tender_pdf, extraction):
    with PdfText(tender_pdf) as pdf:
        return build_brief("hall-b", "tender-hall-a", extraction, lambda p, q, v: verify_quote(pdf, p, q, v),
                           AGREES, set())


def test_extract_and_build_brief(tender_pdf):
    extraction, res = extract_tender(ReplayRunner(FAKE_REPLIES), tender_pdf.read_bytes())
    assert res.tokens_in == 9000
    brief = _brief(tender_pdf, extraction)
    assert len(brief.requirements) == 8 and sum(r.verified for r in brief.requirements) == 7
    bad = next(r for r in brief.requirements if not r.verified)
    assert bad.id == "REQ-ups_autonomy_min" and bad.value is None and bad.text == UNVERIFIED_TEMPLATE
    dv = next(r for r in brief.requirements if r.id == "REQ-dv_max_pct")
    assert dv.value == 2.0 and dv.citation.page == 4 and dv.citation.clause == "§4.6" and dv.citation.bbox
    assert dv.text == "shall not exceed 2.0% at the worst-case design current"
    (q,) = brief.open_questions
    assert q.id == "Q-redundancy" and q.default_resolution == "2N" and q.options == ["2N", "compare_all"]
    assert [c.clause for c in q.citations] == ["§4.2", "App. B"] and all(c.bbox for c in q.citations)
    assert q.text == "§4.2 requires 2N but App. B accepts block or distributed redundancy."
    assert q.resolution is None and brief.drawing_check == AGREES


def test_read_drawing_returns_structured_read():
    read, _ = read_drawing(ReplayRunner(FAKE_REPLIES), b"%PDF-1.4")
    assert read.grid_x == ["1", "2", "3", "4", "5", "6"] and read.overall_mm == [60000, 36000]


def test_contradiction_with_unverifiable_quote_is_dropped(tender_pdf):
    c = ExtractedContradiction(topic="redundancy", clause_a="§4.2", page_a=4, quote_a="The system shall be 3N",
                               value_a="3N", clause_b="App. B", page_b=7,
                               quote_b="Block or distributed redundancy acceptable", value_b="DR",
                               summary="x")
    assert _brief(tender_pdf, TenderExtraction(requirements=[], contradictions=[c])).open_questions == []


def test_appendix_listed_first_still_defaults_to_main_body(tender_pdf):
    c = ExtractedContradiction(topic="Power redundancy", clause_a="App. B", page_a=7,
                               quote_a="Block or distributed redundancy acceptable", value_a="BLOCK",
                               clause_b="§4.2", page_b=4, quote_b="The critical power distribution shall be 2N",
                               value_b="2N redundancy", summary="They disagree in 2 places.")
    (q,) = _brief(tender_pdf, TenderExtraction(requirements=[], contradictions=[c])).open_questions
    assert q.id == "Q-power-redundancy" and q.default_resolution == "2N"
    assert q.text == "App. B and §4.2 disagree; the main body governs by default."


def test_duplicate_keys_get_suffixes(tender_pdf):
    ex = TenderExtraction.model_validate({"requirements": [
        {"key": "tx_loading", "clause": "§4.3", "page": 4, "value": 80, "unit": "%",
         "verbatim_quote": "Transformer loading shall not exceed 80% of rating in normal operation"},
        {"key": "tx_loading", "clause": "§4.3", "page": 4, "value": 100, "unit": "%",
         "verbatim_quote": "100% of rating under any single failure"}]})
    assert [r.id for r in _brief(tender_pdf, ex).requirements] == ["REQ-tx_loading", "REQ-tx_loading-2"]


def test_canonical_topology():
    assert canonical_topology("2N redundancy") == "2N"
    assert canonical_topology("distributed redundant") == "DR"
    assert canonical_topology("Block redundant") == "BLOCK"
    assert canonical_topology("N+1") is None
```

- [ ] **Step 2: Run to verify failure**

Run: `cd services/api && uv run pytest tests/intake/test_intake_extract_brief.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'kirchhoff.intake.extract'`

- [ ] **Step 3: Implement extraction**

`services/api/kirchhoff/intake/extract.py`:
```python
"""Gemini native PDF reading (spec §6.3). Output is untrusted until verify_quote accepts it."""
from pydantic import BaseModel

from kirchhoff.agents.runner import AgentResult, AgentRunner, Attachment, run_json
from kirchhoff.agents.specs import INTAKE, INTAKE_DRAWING

from .drawing import DrawingRead


class ExtractedRequirement(BaseModel):
    key: str
    clause: str
    page: int
    verbatim_quote: str
    value: float | str | None = None
    unit: str | None = None


class ExtractedContradiction(BaseModel):
    topic: str
    clause_a: str
    page_a: int
    quote_a: str
    value_a: str
    clause_b: str
    page_b: int
    quote_b: str
    value_b: str
    summary: str


class TenderExtraction(BaseModel):
    requirements: list[ExtractedRequirement]
    contradictions: list[ExtractedContradiction] = []


TENDER_PROMPT = """Read the attached tender PDF. Pages are numbered from 1 in PDF order.
Return JSON {"requirements": [...], "contradictions": [...]}.
requirements: one item per design requirement or design input, each with
  key: a snake_case name such as max_lead_time_weeks, rack_kw or dv_max_pct;
  clause: the clause id exactly as printed, for example "§4.6"; appendix clauses as "App. B";
  page: the PDF page number on which the quote appears;
  verbatim_quote: an exact contiguous phrase copied from that page that contains the value;
  value: the number as printed (or a short label such as "2N" or "N+1"; null if the requirement has no value);
  unit: the unit as printed, or null.
Do not treat standard numbers such as IEC 60364 as values.
contradictions: pairs of clauses that conflict, each with topic (one or two lowercase words), clause_a, page_a,
quote_a, value_a, clause_b, page_b, quote_b, value_b and summary (one sentence; no digits except clause ids and
topology names)."""

DRAWING_PROMPT = """The attached PDF is a general-arrangement plot of a data hall. Read the structural grid bubble
labels along the bottom from left to right and along the left side from bottom to top, and the two overall
dimension strings in millimetres. Reply with JSON {"grid_x": [...], "grid_y": [...],
"overall_mm": [length_along_x, width_along_y]}."""


def extract_tender(runner: AgentRunner, pdf_bytes: bytes) -> tuple[TenderExtraction, AgentResult]:
    return run_json(runner, INTAKE, "p1.extract", TENDER_PROMPT, TenderExtraction,
                    attachments=[Attachment(pdf_bytes, "application/pdf")])


def read_drawing(runner: AgentRunner, plan_pdf_bytes: bytes) -> tuple[DrawingRead, AgentResult]:
    return run_json(runner, INTAKE_DRAWING, "p1.drawing", DRAWING_PROMPT, DrawingRead,
                    attachments=[Attachment(plan_pdf_bytes, "application/pdf")])
```

- [ ] **Step 4: Implement brief building**

`services/api/kirchhoff/intake/brief.py`:
```python
import re
from collections.abc import Callable
from typing import Any

from kirchhoff.agents.trust import sanitize
from kirchhoff.contracts import Citation, DesignBrief, OpenQuestion, Requirement

from .extract import ExtractedContradiction, TenderExtraction
from .textnorm import normalize
from .verify import QuoteCheck

UNVERIFIED_TEMPLATE = "Requirement not accepted: the quote was not found on the cited page."
Verify = Callable[[int, str, Any], QuoteCheck]


def canonical_topology(s: str) -> str | None:
    t = s.casefold()
    if re.search(r"\b2n\b", t):
        return "2N"
    if "distributed" in t or t.strip() == "dr":
        return "DR"
    if "block" in t:
        return "BLOCK"
    return None


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "conflict"


def _is_main(clause: str) -> bool:
    return not clause.startswith("App.")


def _question(c: ExtractedContradiction, doc_id: str, verify: Verify, allowed: set[str]) -> OpenQuestion | None:
    ca, cb = verify(c.page_a, c.quote_a, None), verify(c.page_b, c.quote_b, None)
    if not (ca.ok and cb.ok):
        return None
    main_value = c.value_a if _is_main(c.clause_a) or not _is_main(c.clause_b) else c.value_b
    default = canonical_topology(main_value) or main_value
    text = sanitize(c.summary, allowed, f"{c.clause_a} and {c.clause_b} disagree; the main body governs by default.")
    return OpenQuestion(
        id=f"Q-{_slug(c.topic)}", text=text, options=[default, "compare_all"], default_resolution=default,
        citations=[Citation(doc_id=doc_id, page=c.page_a, quote=normalize(c.quote_a), bbox=ca.bbox, clause=c.clause_a),
                   Citation(doc_id=doc_id, page=c.page_b, quote=normalize(c.quote_b), bbox=cb.bbox, clause=c.clause_b)])


def build_brief(project_id: str, doc_id: str, extraction: TenderExtraction, verify: Verify,
                drawing_check: dict, allowed: set[str]) -> DesignBrief:
    reqs: list[Requirement] = []
    seen: dict[str, int] = {}
    for r in extraction.requirements:
        seen[r.key] = seen.get(r.key, 0) + 1
        rid = f"REQ-{r.key}" if seen[r.key] == 1 else f"REQ-{r.key}-{seen[r.key]}"
        chk = verify(r.page, r.verbatim_quote, r.value)
        if chk.ok:
            quote = normalize(r.verbatim_quote)
            reqs.append(Requirement(id=rid, text=quote, value=r.value, unit=r.unit, verified=True,
                                    citation=Citation(doc_id=doc_id, page=r.page, quote=quote, bbox=chk.bbox,
                                                      clause=r.clause)))
        else:
            reqs.append(Requirement(id=rid, text=sanitize(r.verbatim_quote, allowed, UNVERIFIED_TEMPLATE), value=None,
                                    unit=r.unit, verified=False,
                                    citation=Citation(doc_id=doc_id, page=r.page, quote="", clause=r.clause)))
    questions = [q for c in extraction.contradictions if (q := _question(c, doc_id, verify, allowed)) is not None]
    return DesignBrief(project_id=project_id, requirements=reqs, open_questions=questions,
                       drawing_check=drawing_check)
```

- [ ] **Step 5: Run tests**

Run: `cd services/api && uv run pytest tests/intake -q`
Expected: all intake tests pass (`23 passed, 2 skipped`).

- [ ] **Step 6: Commit**

```bash
git add services/api/kirchhoff/intake services/api/tests/intake
git commit -m "feat(intake): Gemini PDF extraction schemas, verified brief, contradiction to open question

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Phase orchestrator — workers, heartbeats, gates, Ask/Auto, resume, expiry (Tue 14)

**Files:**
- Create: `services/api/kirchhoff/runs/orchestrator.py`
- Test: `services/api/tests/runs/test_runs_orchestrator.py`

**Interfaces:**
- Consumes: `acquire_lease`, `heartbeat`, `release_lease`, `holds_lease`, `lease_is_live`, `run_path`, `CapReached` (Task 6); `Store.transact`; `EventWriter` (`emit(..., step=...)`, `close()`, `fence()`); `next_seq`, `Deps`, `PhaseContext`, `run_step`, `StepOutput`, `PhaseOutcome`, `ParkAtGate`, `LeaseLost` (Task 8). The phase registry resolves lazily to `phase1.run_p1`, `phase2.run_p2` (Task 11), `phase3.run_p3` (Task 13) and `phase4.run_p4` (Task 14) unless `deps.phases` overrides it.
- Produces:
  - `GATE_TTL_S = 86400`, `NEXT_PHASE`, `PHASE_BEFORE_GATE = {"plan": "p1", "option": "p2", "review": "p3"}`, and the exceptions `LeaseBusy`, `WrongState`, `GateExpired`.
  - `start_phase(deps, uid, rid, phase, run_patch=None) -> int` acquires the lease (merging `{status: running, phase, gate: None, **run_patch}`), spawns the worker and returns the attempt. It raises `CapReached` or `LeaseBusy`.
  - `ensure_gate(deps, uid, rid, gate) -> dict` returns the run doc. It raises `KeyError`, `WrongState`, or `GateExpired` (which marks the run `expired`).
  - `resume_from_gate(deps, uid, rid, gate, run_patch=None) -> int` adds the gate wait to `metrics.gate_wait_s` and starts the next phase.
  - `resume_run(deps, uid, rid) -> bool` handles a `running` run with a stale lease or a `failed` run.
  - Worker behaviour: one `EventWriter` per phase, starting at `next_seq`; every event passes `step=`. On `LeaseLost` the writer is fenced (pending events dropped) before the worker exits. Gates are recorded as steps `"{phase}.gate.{gate}"` with a `gate` event `{gate, auto}`. Auto mode continues through the plan and option gates unless the outcome was `forced` (`ParkAtGate`); the review gate always parks. Parking releases the lease with `status: at_gate`, `gate` and `metrics.gate_entered_at`. Metrics `tokens_in`/`tokens_out` accumulate and `active_s` is total worker time. A failure writes step `"{phase}.failed"` plus a `status` event and releases with `status: failed`. `LeaseLost` exits without writing.

- [ ] **Step 1: Write the failing tests**

`services/api/tests/runs/test_runs_orchestrator.py`:
```python
import pytest

from kirchhoff.runs.leases import CapReached, LIVE_RUNS_DOC, run_path
from kirchhoff.runs.orchestrator import (GateExpired, WrongState, ensure_gate, resume_from_gate, resume_run,
                                        start_phase)
from kirchhoff.runs.steps import LeaseLost, ParkAtGate, PhaseOutcome, StepOutput, run_step

GATES = {"p1": "plan", "p2": "option", "p3": "review", "p4": None}


def dummy_phases(executed, fail_once=(), crash_once=(), park=None):
    failed: set[str] = set()

    def make(name):
        def run(ctx):
            for part in ("a", "b"):
                sid = f"{name}.{part}"

                def work(sid=sid):
                    executed.append(sid)
                    ctx.emit(sid, "system", "status", f"working {sid}")
                    if sid in fail_once and sid not in failed:
                        failed.add(sid)
                        raise RuntimeError("transient")
                    if sid in crash_once and sid not in failed:
                        failed.add(sid)
                        raise LeaseLost(sid)  # simulates the instance dying mid-step
                    return StepOutput(data={"ok": sid})

                run_step(ctx, sid, work)
            if park == name:
                raise ParkAtGate("option", "no qualifying option")
            ctx.metrics["tokens_in"] = 10.0
            return PhaseOutcome(gate=GATES[name])
        return run

    return {p: make(p) for p in GATES}


def _run(deps, rid):
    return deps.store.get_doc(run_path("u1", rid))


def _events(deps, rid):
    return deps.store.list_docs(f"{run_path('u1', rid)}/events")


def test_ask_mode_parks_at_every_gate_and_resumes(deps, make_run):
    executed: list[str] = []
    deps.phases = dummy_phases(executed)
    rid = make_run()
    assert start_phase(deps, "u1", rid, "p1") == 1
    run = _run(deps, rid)
    assert (run["status"], run["gate"], run["phase"]) == ("at_gate", "plan", "p1")
    assert run["lease"] == {"owner": None, "attempt": 1, "heartbeat_at": 0.0}
    assert "gate_entered_at" in run["metrics"] and run["metrics"]["tokens_in"] == 10.0
    for gate, nxt in (("plan", "option"), ("option", "review")):
        resume_from_gate(deps, "u1", rid, gate)
        assert (_run(deps, rid)["status"], _run(deps, rid)["gate"]) == ("at_gate", nxt)
    resume_from_gate(deps, "u1", rid, "review")
    run = _run(deps, rid)
    assert run["status"] == "done" and run["finished_at"] and run["lease"]["attempt"] == 4
    assert run["metrics"]["tokens_in"] == 40.0 and run["metrics"]["gate_wait_s"] >= 0
    seqs = [e["seq"] for e in _events(deps, rid)]
    assert seqs == list(range(1, len(seqs) + 1))
    gates = [e["payload"] for e in _events(deps, rid) if e["kind"] == "gate"]
    assert gates == [{"gate": "plan", "auto": False}, {"gate": "option", "auto": False},
                     {"gate": "review", "auto": False}]


def test_auto_mode_runs_through_to_the_review_gate(deps, make_run):
    deps.phases = dummy_phases([])
    rid = make_run(autonomy="auto")
    start_phase(deps, "u1", rid, "p1")
    run = _run(deps, rid)
    assert (run["status"], run["gate"], run["phase"]) == ("at_gate", "review", "p3")
    assert [e["payload"]["auto"] for e in _events(deps, rid) if e["kind"] == "gate"] == [True, True, False]


def test_park_at_gate_is_forced_even_in_auto(deps, make_run):
    deps.phases = dummy_phases([], park="p2")
    rid = make_run(autonomy="auto")
    start_phase(deps, "u1", rid, "p1")
    run = _run(deps, rid)
    assert (run["status"], run["gate"], run["phase"]) == ("at_gate", "option", "p2")


def test_failure_then_resume_reruns_only_unfinished_steps(deps, make_run):
    executed: list[str] = []
    deps.phases = dummy_phases(executed, fail_once={"p1.b"})
    rid = make_run()
    start_phase(deps, "u1", rid, "p1")
    assert _run(deps, rid)["status"] == "failed"
    assert deps.store.get_doc(f"{run_path('u1', rid)}/steps/p1.failed")["status"] == "failed"
    assert resume_run(deps, "u1", rid) is True
    assert _run(deps, rid)["gate"] == "plan"
    assert executed == ["p1.a", "p1.b", "p1.b"]


def test_resume_after_dead_worker_takes_a_new_attempt(deps, make_run):
    executed: list[str] = []
    deps.phases = dummy_phases(executed, crash_once={"p1.b"})
    rid = make_run()
    start_phase(deps, "u1", rid, "p1")
    run = _run(deps, rid)
    assert run["status"] == "running" and run["lease"]["owner"] == deps.owner
    assert resume_run(deps, "u1", rid) is False  # lease still live
    deps.store.set_doc(run_path("u1", rid), {**run, "lease": {**run["lease"], "heartbeat_at": deps.clock() - 120}})
    assert resume_run(deps, "u1", rid) is True
    run = _run(deps, rid)
    assert run["gate"] == "plan" and run["lease"]["attempt"] == 2
    assert executed == ["p1.a", "p1.b", "p1.b"]
    step_b = deps.store.get_doc(f"{run_path('u1', rid)}/steps/p1.b")
    shown = [e for e in _events(deps, rid) if e["step"] == "p1.b" and e["attempt"] == step_b["attempt"]]
    assert len(shown) == 1  # UI rule: only the committing attempt's events


def test_gate_validation_and_expiry(deps, make_run):
    deps.phases = dummy_phases([])
    rid = make_run()
    start_phase(deps, "u1", rid, "p1")
    with pytest.raises(WrongState):
        ensure_gate(deps, "u1", rid, "option")
    run = _run(deps, rid)
    deps.store.set_doc(run_path("u1", rid), {**run, "metrics": {**run["metrics"],
                                                               "gate_entered_at": deps.clock() - 90_000}})
    with pytest.raises(GateExpired):
        resume_from_gate(deps, "u1", rid, "plan")
    assert _run(deps, rid)["status"] == "expired"


def test_global_cap_blocks_start(deps, make_run):
    deps.phases = dummy_phases([])
    now = deps.clock()
    deps.store.set_doc(LIVE_RUNS_DOC, {"runs": {"a__1": now, "b__2": now, "c__3": now}})
    with pytest.raises(CapReached):
        start_phase(deps, "u1", make_run(), "p1")
```

- [ ] **Step 2: Run to verify failure**

Run: `cd services/api && uv run pytest tests/runs/test_runs_orchestrator.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'kirchhoff.runs.orchestrator'`

- [ ] **Step 3: Implement the orchestrator**

`services/api/kirchhoff/runs/orchestrator.py`:
```python
"""Phase workers (spec §6.2): lease + heartbeat, steps, gates, Ask/Auto, resume, 24 h gate expiry."""
import importlib
import logging
import threading
from collections.abc import Callable

from kirchhoff.contracts import StepRecord
from kirchhoff.store.events import EventWriter

from .deps import Deps
from .events import next_seq
from .leases import acquire_lease, heartbeat, holds_lease, lease_is_live, release_lease, run_path
from .steps import LeaseLost, ParkAtGate, PhaseContext, PhaseOutcome, StepOutput, run_step

log = logging.getLogger("kirchhoff.runs")
GATE_TTL_S = 24 * 3600.0
NEXT_PHASE = {"p1": "p2", "p2": "p3", "p3": "p4", "p4": None}
PHASE_BEFORE_GATE = {"plan": "p1", "option": "p2", "review": "p3"}
AUTO_GATES = {"plan", "option"}
ADDITIVE_METRICS = {"tokens_in", "tokens_out"}
GATE_TITLES = {"plan": "Plan ready for approval", "option": "Options ready for selection",
               "review": "Revision ready for review"}
AUTO_TITLES = {"plan": "Plan approved automatically (Auto mode)",
               "option": "Option chosen automatically (Auto mode)"}


class LeaseBusy(Exception):
    """The run is held by a live worker."""


class WrongState(Exception):
    """The run is not parked at the requested gate."""


class GateExpired(Exception):
    """The run waited at its gate for more than 24 h."""


def phase_fn(deps: Deps, phase: str) -> Callable[[PhaseContext], PhaseOutcome]:
    if deps.phases is not None:
        return deps.phases[phase]
    module = importlib.import_module(f"kirchhoff.runs.phase{phase[1]}")  # imported per phase, on demand
    return getattr(module, f"run_{phase}")


def start_phase(deps: Deps, uid: str, rid: str, phase: str, run_patch: dict | None = None) -> int:
    patch = {**(run_patch or {}), "status": "running", "phase": phase, "gate": None}
    attempt = acquire_lease(deps.store, uid, rid, deps.owner, deps.clock(), patch)
    if attempt is None:
        raise LeaseBusy(rid)
    deps.spawn(lambda: _worker(deps, uid, rid, phase, attempt))
    return attempt


def ensure_gate(deps: Deps, uid: str, rid: str, gate: str) -> dict:
    run = deps.store.get_doc(run_path(uid, rid))
    if run is None:
        raise KeyError(rid)
    if run.get("status") != "at_gate" or run.get("gate") != gate:
        raise WrongState(gate)
    entered = float((run.get("metrics") or {}).get("gate_entered_at", deps.clock()))
    if deps.clock() - entered > GATE_TTL_S:
        deps.store.update_doc(run_path(uid, rid), {"status": "expired", "gate": None})
        raise GateExpired(gate)
    return run


def resume_from_gate(deps: Deps, uid: str, rid: str, gate: str, run_patch: dict | None = None) -> int:
    run = ensure_gate(deps, uid, rid, gate)
    now = deps.clock()
    metrics = dict(run.get("metrics") or {})
    entered = float(metrics.pop("gate_entered_at", now))
    metrics["gate_wait_s"] = float(metrics.get("gate_wait_s", 0.0)) + (now - entered)
    return start_phase(deps, uid, rid, NEXT_PHASE[PHASE_BEFORE_GATE[gate]], {**(run_patch or {}), "metrics": metrics})


def resume_run(deps: Deps, uid: str, rid: str) -> bool:
    run = deps.store.get_doc(run_path(uid, rid))
    if run is None:
        raise KeyError(rid)
    now = deps.clock()
    stale = run.get("status") == "running" and not lease_is_live(run.get("lease"), now)
    if not (stale or run.get("status") == "failed"):
        return False
    phase = run.get("phase") or "p1"
    attempt = acquire_lease(deps.store, uid, rid, deps.owner, now, {"status": "running"})
    if attempt is None:
        return False
    deps.spawn(lambda: _worker(deps, uid, rid, phase, attempt))
    return True


def _merge_metrics(base: dict, ctx_metrics: dict, outcome_metrics: dict, active_s: float) -> dict:
    out = dict(base)
    for k, v in ctx_metrics.items():
        out[k] = float(out.get(k, 0.0)) + float(v) if k in ADDITIVE_METRICS else float(v)
    out.update({k: float(v) for k, v in outcome_metrics.items()})
    out["active_s"] = float(active_s)
    return out


def _patch_if_holder(deps: Deps, uid: str, rid: str, attempt: int, patch: dict) -> None:
    rp = run_path(uid, rid)
    writes = deps.store.transact([rp], lambda snap: [(rp, {**snap[rp], **patch})]
                                 if holds_lease(snap[rp], deps.owner, attempt) else [])
    if not writes:
        raise LeaseLost(rid)


def _gate_step(ctx: PhaseContext, outcome: PhaseOutcome, auto: bool) -> StepOutput:
    title = AUTO_TITLES[outcome.gate] if auto else GATE_TITLES[outcome.gate]
    ctx.emit(f"{ctx.phase}.gate.{outcome.gate}", "orchestrator", "gate", title, outcome.message,
             payload={"gate": outcome.gate, "auto": auto})
    return StepOutput(data={"gate": outcome.gate, "auto": auto})


def _worker(deps: Deps, uid: str, rid: str, phase: str, attempt: int) -> None:
    rp = run_path(uid, rid)
    lost, stop = threading.Event(), threading.Event()
    threading.Thread(target=_heartbeat_loop, args=(deps, uid, rid, attempt, lost, stop), daemon=True).start()
    current: str | None = phase
    try:
        while current:
            run = deps.store.get_doc(rp) or {}
            metrics = dict(run.get("metrics") or {})
            events = EventWriter(deps.store, rp, phase=current, step=f"{current}.start", attempt=attempt,
                                 start_seq=next_seq(deps.store, rp))
            ctx = PhaseContext(deps, uid, rid, current, attempt, events, lost, float(metrics.get("active_s", 0.0)))
            try:
                try:
                    outcome = phase_fn(deps, current)(ctx)
                except ParkAtGate as park:
                    outcome = PhaseOutcome(gate=park.gate, forced=True, message=park.message)
                auto = run.get("autonomy") == "auto" and outcome.gate in AUTO_GATES and not outcome.forced
                if outcome.gate:
                    run_step(ctx, f"{current}.gate.{outcome.gate}", lambda: _gate_step(ctx, outcome, auto))
            except LeaseLost:
                events.fence()  # a stale worker writes no further events (fenced flush/close are no-ops)
                raise
            finally:
                events.close()
            metrics = _merge_metrics(metrics, ctx.metrics, outcome.metrics, ctx.active_s())
            if outcome.gate is None:
                release_lease(deps.store, uid, rid, deps.owner, attempt,
                              {**outcome.run_patch, "status": "done", "phase": current, "gate": None,
                               "finished_at": deps.clock(), "metrics": metrics})
                return
            if auto:
                nxt = NEXT_PHASE[current]
                _patch_if_holder(deps, uid, rid, attempt, {**outcome.run_patch, "phase": nxt, "metrics": metrics})
                current = nxt
                continue
            metrics["gate_entered_at"] = deps.clock()
            release_lease(deps.store, uid, rid, deps.owner, attempt,
                          {**outcome.run_patch, "status": "at_gate", "phase": current, "gate": outcome.gate,
                           "metrics": metrics})
            return
    except LeaseLost:
        log.info("run %s/%s: lease lost; another worker continues", uid, rid)
    except Exception as exc:
        log.exception("run %s/%s failed in %s", uid, rid, current)
        _record_failure(deps, uid, rid, current or phase, attempt, exc)
        release_lease(deps.store, uid, rid, deps.owner, attempt, {"status": "failed", "phase": current or phase})
    finally:
        stop.set()


def _heartbeat_loop(deps: Deps, uid: str, rid: str, attempt: int, lost: threading.Event,
                    stop: threading.Event) -> None:
    while not stop.wait(deps.heartbeat_s):
        try:
            if not heartbeat(deps.store, uid, rid, deps.owner, attempt, deps.clock()):
                lost.set()
                return
        except Exception:
            log.exception("heartbeat failed for %s/%s", uid, rid)


def _record_failure(deps: Deps, uid: str, rid: str, phase: str, attempt: int, exc: Exception) -> None:
    rp = run_path(uid, rid)
    try:
        if not holds_lease(deps.store.get_doc(rp), deps.owner, attempt):
            return
        step, now = f"{phase}.failed", deps.clock()
        deps.store.set_doc(f"{rp}/steps/{step}", StepRecord(id=step, phase=phase, status="failed", attempt=attempt,
                                                             started_at=now, finished_at=now).model_dump())
        w = EventWriter(deps.store, rp, phase=phase, step=step, attempt=attempt,
                        start_seq=next_seq(deps.store, rp), flush_interval_s=0)
        w.emit("system", "status", "Run stopped by an error; resume to retry", detail=type(exc).__name__, step=step)
        w.close()
    except Exception:
        log.exception("could not record failure for %s/%s", uid, rid)
```

- [ ] **Step 4: Run tests**

Run: `cd services/api && uv run pytest tests/runs -q`
Expected: all runs tests pass (`26 passed`).

- [ ] **Step 5: Commit**

```bash
git add services/api/kirchhoff/runs/orchestrator.py services/api/tests/runs/test_runs_orchestrator.py
git commit -m "feat(runs): phase workers with leases, heartbeats, gates, Ask/Auto, resume and expiry

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: Policy, P1 (Intake → Orchestrator) and P2 (Layout → Power ∥ Cooling → Procurement → Power recheck), live P1 smoke (Tue 14)

**Files:**
- Create: `services/api/kirchhoff/runs/policy.py`, `services/api/kirchhoff/runs/phase1.py`, `services/api/kirchhoff/runs/phase2.py`
- Test: `services/api/tests/runs/test_runs_policy.py`, `services/api/tests/runs/test_runs_p1_p2.py`, `services/api/tests/runs/test_runs_live_p1.py`

**Interfaces:**
- Consumes: `extract_tender`, `read_drawing`, `build_brief` (Task 9); `PdfText`, `verify_quote`, `load_ground_truth`, `score_intake` (Task 3); `parse_dxf_geometry`, `compare_drawing` (Task 2); `ORCHESTRATOR, LAYOUT, POWER, COOLING, PROCUREMENT, FIX_CRITERIA` (Task 5); `PhaseContext`, `run_step`, `StepOutput`, `PhaseOutcome` (Task 8); and the engine facade `place_racks`, `power_options`, `size_cooling`, `annotate_options`, `power_recheck`.
- Produces:
  - `kirchhoff.runs.policy`: `PLAN_TEMPLATE: list[tuple[step_id, agent, title]]`; `OWNER: dict[rule_id, agent]` (R11); `RECHECK_RULES`; `lead_limit_weeks(scn) -> int` (`max_lead_time_weeks` from `scn.tender`, default 26); `choose_option(options, resolutions, lead_limit) -> TopologyOption | None` (spec §6.1 Auto rule; tie order 2N, DR, BLOCK); `preferred_candidate(owner, cands) -> FixCandidate` (R23); `criterion(owner) -> str`.
  - `phase1.run_p1(ctx) -> PhaseOutcome(gate="plan", run_patch={"plan", "open_questions"})`. Steps: `p1.intake`, whose outputs are `{"brief": DesignBrief}` (the UI reads the brief from `runs/{rid}/outputs/p1.intake`, field `json`, key `brief`), and `p1.plan`. Metrics: `quotes_verified`, `quotes_total`, `intake_recall`.
  - `phase2.run_p2(ctx) -> PhaseOutcome(gate="option", run_patch={"options": [TopologyOption]})`. Steps: `p2.resolve_plan` (outputs `{"resolutions": {qid: value}}`), `p2.place_racks` (`{"racks"}`), `p2.power_options` ∥ `p2.cooling_sizing` (`{"options": [{"option", "model"}]}` / `{"cooling_nodes"}`), `p2.annotate_options` (`{"options", "recommended"}`) and `p2.power_recheck` (`{"recheck": {option_id: {pass, fail, ikss_ka_before, ikss_ka_after}}}`).
  - Events: `tool_call`/`tool_result` per tool, sanitized `message` narration per agent, `ledger` for assumptions and swaps, `artifact {type: "brief"}` and `artifact {type: "options", ref: run_path, recommended}`.

- [ ] **Step 1: Write the failing tests**

`services/api/tests/runs/test_runs_policy.py`:
```python
from kirchhoff.contracts import TopologyOption
from kirchhoff.runs.compat import FixCandidate
from kirchhoff.runs.policy import choose_option, lead_limit_weeks, preferred_candidate
from kirchhoff.runs.fakes import FakeScenario


def _opt(i, cost, lead=12, spof=0):
    return TopologyOption(id=i, installed_mva=1, normal_loading_pct=1, failover_loading_pct=1, cost=cost,
                          losses_kw=1, max_lead_time_weeks=lead, spof_count=spof)


def test_choose_option_follows_the_auto_rule():
    opts = [_opt("2N", 5.0), _opt("DR", 4.0), _opt("BLOCK", 3.0, lead=98)]
    assert choose_option(opts, {"Q-redundancy": "2N"}, 26).id == "2N"
    assert choose_option(opts, {"Q-redundancy": "compare_all"}, 26).id == "DR"  # BLOCK breaks §2.3
    assert choose_option([_opt("2N", 5.0, spof=1)], {}, 26) is None
    assert choose_option([_opt("DR", 4.0), _opt("2N", 4.0)], {}, 26).id == "2N"  # tie: §4.2 governs


def _c(i, cost, **m):
    return FixCandidate(id=i, finding_id="f", label=i, cost_delta=cost, metrics=m, patch={})


def test_preferred_candidate_criteria():
    drop, reroute = _c("H-Z2:local-drop", 420.0, changed_pipes=1.0), _c("H-Z2:reroute", -910.0, changed_pipes=2.0)
    assert preferred_candidate("cooling", [reroute, drop]).id == "H-Z2:local-drop"
    up = _c("FA-01:upsize-BW-2000", 11480.0, dv_pct=1.66, dv_limit_pct=2.0)
    cable = _c("FA-01:cable-CBL-240-8P", 26900.0, dv_pct=0.84, dv_limit_pct=2.0)
    assert preferred_candidate("power", [up, cable]).id == "FA-01:cable-CBL-240-8P"
    assert preferred_candidate("procurement", [cable, up]).id == "FA-01:upsize-BW-2000"


def test_lead_limit_reads_the_tender():
    assert lead_limit_weeks(FakeScenario("hall_a", {"clauses": [{"id": "§2.3", "limits": {"max_lead_time_weeks": 20}}]})) == 20
    assert lead_limit_weeks(FakeScenario("hall_a", {"clauses": []})) == 26
```

`services/api/tests/runs/test_runs_p1_p2.py`:
```python
import pytest

from kirchhoff.contracts import DesignBrief
from kirchhoff.runs.fakes import FakeEngine
from kirchhoff.runs.leases import run_path
from kirchhoff.runs.orchestrator import resume_from_gate, resume_run, start_phase
from kirchhoff.runs.outputs import load_outputs
from kirchhoff.runs.phase1 import run_p1
from kirchhoff.runs.phase2 import run_p2
from kirchhoff.runs.policy import PLAN_TEMPLATE
from kirchhoff.runs.steps import PhaseOutcome


def review_stub(ctx):
    return PhaseOutcome(gate="review")


@pytest.fixture
def p12(deps):
    deps.phases = {"p1": run_p1, "p2": run_p2, "p3": review_stub}
    return deps


def _run(d, rid):
    return d.store.get_doc(run_path("u1", rid))


def _events(d, rid):
    return d.store.list_docs(f"{run_path('u1', rid)}/events")


def _out(d, rid, step):
    return load_outputs(d.store, d.blobs, run_path("u1", rid), step)


def test_p1_reaches_plan_gate_with_a_verified_brief(p12, make_run):
    rid = make_run()
    start_phase(p12, "u1", rid, "p1")
    run = _run(p12, rid)
    assert (run["status"], run["gate"]) == ("at_gate", "plan")
    assert [p["id"] for p in run["plan"]] == [sid for sid, _, _ in PLAN_TEMPLATE]
    (q,) = run["open_questions"]
    assert q["id"] == "Q-redundancy" and q["resolution"] is None and q["default_resolution"] == "2N"
    brief = DesignBrief.model_validate(_out(p12, rid, "p1.intake")["brief"])
    assert sum(r.verified for r in brief.requirements) == 7 and brief.drawing_check["agrees"] is True
    assert brief.intake_score["recall"] == 7 / 32 and brief.intake_score["precision"] == 1.0
    titles = [e["title"] for e in _events(p12, rid)]
    assert "7/8 quotes verified" in titles and "Drawing read · DXF agrees" in titles
    assert {"tool_result", "artifact", "plan", "gate", "message"} <= {e["kind"] for e in _events(p12, rid)}
    assert run["metrics"]["quotes_verified"] == 7.0 and run["metrics"]["tokens_in"] >= 11000


def test_plan_answer_flows_into_p2_and_options_carry_swaps(p12, make_run, firestore_safe):
    rid = make_run()
    start_phase(p12, "u1", rid, "p1")
    qs = [{**q, "resolution": "compare_all"} for q in _run(p12, rid)["open_questions"]]
    resume_from_gate(p12, "u1", rid, "plan", {"open_questions": qs})
    run = _run(p12, rid)
    assert (run["status"], run["gate"]) == ("at_gate", "option")
    assert [o["id"] for o in run["options"]] == ["2N", "DR", "BLOCK"]
    assert all(o["swaps"][0]["to"] == "TX-3150" for o in run["options"])
    assert _out(p12, rid, "p2.annotate_options")["recommended"] == "BLOCK"  # compare_all: cheapest qualifying
    recheck = _out(p12, rid, "p2.power_recheck")["recheck"]
    assert recheck["2N"]["fail"] == 0 and recheck["2N"]["ikss_ka_after"] == 65.4
    ledger = [e["title"] for e in _events(p12, rid) if e["kind"] == "ledger"]
    assert "2N: TX-2500 replaced by TX-3150 (R15)" in ledger
    assert p12.engine.calls.count("power_recheck") == 3
    firestore_safe(p12.store)


def test_auto_mode_resolves_by_main_body_and_reaches_review(p12, make_run):
    rid = make_run(autonomy="auto")
    start_phase(p12, "u1", rid, "p1")
    run = _run(p12, rid)
    assert (run["status"], run["gate"]) == ("at_gate", "review")
    assert run["open_questions"][0]["resolution"] == "2N"
    ledger = [e["title"] for e in _events(p12, rid) if e["kind"] == "ledger"]
    assert "Q-redundancy resolved to 2N: the main body governs over the appendix." in ledger
    assert _out(p12, rid, "p2.annotate_options")["recommended"] == "2N"


class FlakyAnnotate(FakeEngine):
    """Fails twice: once inside the agent's tool call and once in the step's direct fallback call."""

    def __init__(self) -> None:
        super().__init__()
        self.failures_left = 2

    def annotate_options(self, scn, options, erp):
        if self.failures_left:
            self.failures_left -= 1
            raise RuntimeError("ERP timeout")
        return super().annotate_options(scn, options, erp)


def test_resume_mid_p2_reruns_only_unfinished_steps(p12, make_run):
    p12.engine = FlakyAnnotate()
    rid = make_run()
    start_phase(p12, "u1", rid, "p1")
    resume_from_gate(p12, "u1", rid, "plan")
    assert _run(p12, rid)["status"] == "failed"
    assert resume_run(p12, "u1", rid) is True
    assert _run(p12, rid)["gate"] == "option"
    assert p12.engine.calls.count("place_racks") == 1 and p12.engine.calls.count("power_options") == 1


def test_narration_with_free_numbers_is_replaced_by_the_template(p12, make_run):
    p12.runner.replies["layout:p2.place_racks"] = {"tool_calls": [{"name": "place_racks", "args": {}}],
                                                   "text": "Placed 48 racks in 6 rows."}
    rid = make_run()
    start_phase(p12, "u1", rid, "p1")
    resume_from_gate(p12, "u1", rid, "plan")
    msgs = [e["title"] for e in _events(p12, rid) if e["kind"] == "message" and e["agent"] == "layout"]
    assert msgs == ["Layout completed rack placement."]
```

`services/api/tests/runs/test_runs_live_p1.py`:
```python
import json
import os
import time
from pathlib import Path

import pytest

from kirchhoff.contracts import DesignBrief
from kirchhoff.runs.fakes import build_fake_deps
from kirchhoff.runs.leases import run_path
from kirchhoff.runs.orchestrator import start_phase
from kirchhoff.runs.outputs import load_outputs
from kirchhoff.runs.phase1 import run_p1
from kirchhoff.store.memory import MemoryStore

pytestmark = [pytest.mark.live,
              pytest.mark.skipif(os.environ.get("KIRCHHOFF_LIVE") != "1", reason="set KIRCHHOFF_LIVE=1")]


def test_live_p1_on_vertex(scen_dir, tmp_path):
    from kirchhoff.agents.adk_runner import AdkRunner
    from kirchhoff.agents.runner import RecordingRunner

    runner = AdkRunner()
    if os.environ.get("KIRCHHOFF_RECORD_DIR"):
        runner = RecordingRunner(runner, Path(os.environ["KIRCHHOFF_RECORD_DIR"]))
    deps = build_fake_deps(MemoryStore(), scen_dir, seed_dir=tmp_path, spawn=lambda fn: fn(), heartbeat_s=3600.0,
                           runner=runner, phases={"p1": run_p1})
    rid = "live-p1"
    deps.store.set_doc(run_path("u1", rid), {"id": rid, "project_id": "hall-b", "status": "running",
                                              "autonomy": "ask", "phase": "p1", "started_at": time.time()})
    t0 = time.monotonic()
    start_phase(deps, "u1", rid, "p1")
    elapsed = time.monotonic() - t0
    run = deps.store.get_doc(run_path("u1", rid))
    assert (run["status"], run["gate"]) == ("at_gate", "plan"), run
    brief = DesignBrief.model_validate(load_outputs(deps.store, deps.blobs, run_path("u1", rid), "p1.intake")["brief"])
    verified = [r for r in brief.requirements if r.verified]
    assert len(verified) >= 12 and len(verified) >= 0.8 * len(brief.requirements)
    q = next(q for q in brief.open_questions if {c.clause for c in q.citations} == {"§4.2", "App. B"})
    assert q.default_resolution == "2N"
    assert brief.drawing_check["agrees"] is True, brief.drawing_check
    assert brief.intake_score["recall"] >= 0.6
    assert elapsed < 120
    print(json.dumps({"elapsed_s": round(elapsed, 1), **brief.intake_score}))
```

- [ ] **Step 2: Run to verify failure**

Run: `cd services/api && uv run pytest tests/runs/test_runs_policy.py tests/runs/test_runs_p1_p2.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'kirchhoff.runs.policy'`

- [ ] **Step 3: Implement the policy**

`services/api/kirchhoff/runs/policy.py`:
```python
"""Deterministic run policy: plan template, fix owners, Auto option rule (spec §6.1), fix criteria (R23)."""
from kirchhoff.agents.specs import FIX_CRITERIA
from kirchhoff.contracts import TopologyOption

PLAN_TEMPLATE = [
    ("p2.place_racks", "layout", "Place racks (engine default)"),
    ("p2.power_options", "power", "Enumerate power topologies"),
    ("p2.cooling_sizing", "cooling", "Size CDUs and hydraulic zones"),
    ("p2.annotate_options", "procurement", "Check ERP lead times and apply in-stock swaps"),
    ("p2.power_recheck", "power", "Re-check short circuit and loading on swapped options"),
    ("p3.route", "layout", "Route busways and pipes"),
    ("p3.clashes", "layout", "Detect clashes"),
    ("p3.boq", "procurement", "Derive BOQ and draft PR lines"),
    ("p3.check", "checker", "Run the rule pack"),
    ("p3.fix", "power", "Fix loop (at most two iterations)"),
    ("p3.docs", "docs", "Calc report and BOQ"),
    ("p4.create_prs", "procurement", "Create purchase requisitions on approval"),
    ("p4.crm", "system", "Update the CRM opportunity"),
]
OWNER = {"R01": "power", "R02": "power", "R03": "power", "R04": "power", "R04b": "power", "R05": "power",
         "R06": "power", "R07": "power", "R13": "power", "R08": "cooling", "R09": "cooling", "R10": "cooling",
         "R11": "cooling", "R14": "cooling", "R12": "checker", "R15": "procurement"}
RECHECK_RULES = ("R01", "R04", "R04b")
DEFAULT_LEAD_LIMIT_WEEKS = 26
TOPOLOGY_ORDER = {"2N": 0, "DR": 1, "BLOCK": 2}


def lead_limit_weeks(scn) -> int:
    for c in (getattr(scn, "tender", None) or {}).get("clauses", []):
        limits = c.get("limits") or {}
        if "max_lead_time_weeks" in limits:
            return int(limits["max_lead_time_weeks"])
    return DEFAULT_LEAD_LIMIT_WEEKS


def choose_option(options: list[TopologyOption], resolutions: dict[str, str],
                  lead_limit: int) -> TopologyOption | None:
    """Filter by resolved clauses, then the lowest cost with zero SPOF and every lead time within the limit."""
    pool = list(options)
    wanted = {r for r in resolutions.values() if r in TOPOLOGY_ORDER}
    if wanted:
        pool = [o for o in pool if o.id in wanted]
    pool = [o for o in pool if o.spof_count == 0 and o.max_lead_time_weeks <= lead_limit]
    return min(pool, key=lambda o: (o.cost, TOPOLOGY_ORDER.get(o.id, 9)), default=None)


def criterion(owner: str) -> str:
    return FIX_CRITERIA.get(owner, "lowest cost")


def preferred_candidate(owner: str, cands: list):
    if owner == "cooling":
        return min(cands, key=lambda c: (c.metrics.get("changed_pipes", 0.0), c.cost_delta, c.id))
    if owner == "power":
        def margin_per_dollar(c) -> float:
            return (c.metrics.get("dv_limit_pct", 0.0) - c.metrics.get("dv_pct", 0.0)) / max(c.cost_delta, 1.0)
        return min(cands, key=lambda c: (-margin_per_dollar(c), c.cost_delta, c.id))
    return min(cands, key=lambda c: (c.cost_delta, c.id))
```

- [ ] **Step 4: Implement P1**

`services/api/kirchhoff/runs/phase1.py`:
```python
"""P1: Intake → Orchestrator → PLAN GATE (spec §6.2)."""
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel

from kirchhoff.agents.specs import ORCHESTRATOR
from kirchhoff.contracts import DesignBrief, PlanStep
from kirchhoff.intake.brief import build_brief
from kirchhoff.intake.drawing import DxfSummary, compare_drawing, parse_dxf_geometry
from kirchhoff.intake.extract import extract_tender, read_drawing
from kirchhoff.intake.score import load_ground_truth, score_intake
from kirchhoff.intake.verify import PdfText, verify_quote

from .policy import PLAN_TEMPLATE
from .steps import PhaseContext, PhaseOutcome, StepOutput, run_step

DOC_ID = "tender-hall-a"
S_INTAKE, S_PLAN = "p1.intake", "p1.plan"


class PlanReply(BaseModel):
    summary: str
    ask_human: list[str] = []


def run_p1(ctx: PhaseContext) -> PhaseOutcome:
    brief = DesignBrief.model_validate(run_step(ctx, S_INTAKE, lambda: _intake(ctx))["brief"])
    plan = run_step(ctx, S_PLAN, lambda: _plan(ctx, brief))
    return PhaseOutcome(gate="plan", run_patch={"plan": plan["plan"], "open_questions": plan["open_questions"]})


def _intake(ctx: PhaseContext) -> StepOutput:
    files = ctx.deps.inputs()
    ctx.emit(S_INTAKE, "intake", "status", "Reading the tender and the hall drawing")
    with ThreadPoolExecutor(2) as pool:
        f_tender = pool.submit(extract_tender, ctx.deps.runner, files.tender_pdf.read_bytes())
        f_drawing = pool.submit(read_drawing, ctx.deps.runner, files.plan_pdf.read_bytes())
        extraction, r_tender = f_tender.result()  # Intake is critical: failure fails the step (resume retries)
        try:
            drawing, r_drawing = f_drawing.result()
        except Exception as exc:
            drawing, r_drawing = None, None
            ctx.emit(S_INTAKE, "intake", "status", "Drawing could not be read", detail=type(exc).__name__)
    ctx.add_tokens(r_tender, r_drawing)
    allowed = ctx.allowed()
    with PdfText(files.tender_pdf) as pdf:
        def verify(page, quote, value):
            chk = verify_quote(pdf, page, quote, value)
            ctx.emit(S_INTAKE, "intake", "tool_result", "Quote verified" if chk.ok else "Quote rejected",
                     detail=f"page {page}",
                     payload={"tool": "verify_quote", "summary": {"page": page, "ok": chk.ok, "reason": chk.reason}})
            return chk

        brief = build_brief(ctx.run().get("project_id", "hall-b"), DOC_ID, extraction, verify, {}, allowed)
    def parse_dxf_geometry_tool() -> dict:
        """Parse the hall DXF: grid labels and overall size."""
        return parse_dxf_geometry(files.dxf).model_dump(mode="json")

    parse_dxf_geometry_tool.__name__ = "parse_dxf_geometry"  # event and tool name
    dxf = DxfSummary.model_validate(ctx.tool(S_INTAKE, "intake", parse_dxf_geometry_tool)())
    check = compare_drawing(drawing, dxf) if drawing else {
        "agrees": False, "differences": ["drawing could not be read"], "grid_x": dxf.grid_x, "grid_y": dxf.grid_y,
        "overall_mm": list(dxf.overall_mm)}
    brief = brief.model_copy(update={"drawing_check": check})
    if files.ground_truth.exists():
        brief = brief.model_copy(update={"intake_score": score_intake(brief, load_ground_truth(files.ground_truth))})
    n_ok, n = sum(r.verified for r in brief.requirements), len(brief.requirements)
    ctx.emit(S_INTAKE, "intake", "message", f"{n_ok}/{n} quotes verified", payload={"verified": n_ok, "total": n})
    ctx.emit(S_INTAKE, "intake", "message",
             "Drawing read · DXF agrees" if check["agrees"] else "Drawing read · differences found",
             detail="; ".join(check["differences"]), payload={"drawing_check": check})
    for q in brief.open_questions:
        ctx.emit(S_INTAKE, "intake", "status", "Contradiction found", detail=q.text, payload={"question_id": q.id})
    ctx.emit(S_INTAKE, "intake", "artifact", "Design brief ready",
             payload={"type": "brief", "ref": f"{ctx.run_path}/outputs/{S_INTAKE}"})
    ctx.metrics.update({"quotes_verified": float(n_ok), "quotes_total": float(n),
                        "intake_recall": float(brief.intake_score.get("recall", 0.0))})
    return StepOutput(data={"brief": brief.model_dump(mode="json")})


def _plan(ctx: PhaseContext, brief: DesignBrief) -> StepOutput:
    reqs = "\n".join(f"- {r.id} cites {r.citation.clause}" for r in brief.requirements if r.verified)
    qs = "\n".join(f"- {q.id}: {q.text} Options: {', '.join(q.options)}. Default: {q.default_resolution}."
                   for q in brief.open_questions) or "- none"
    msg = (f"Design brief for an AI data hall.\nVerified requirements:\n{reqs}\nOpen questions:\n{qs}\n"
           'Reply with JSON {"summary": one sentence, "ask_human": [ids of the questions the engineer must decide]}.')
    reply = ctx.agent_json(ORCHESTRATOR, S_PLAN, msg, PlanReply)
    ask = set(reply.ask_human) if reply else {q.id for q in brief.open_questions}
    questions = []
    for q in brief.open_questions:
        if q.id not in ask:
            q = q.model_copy(update={"resolution": q.default_resolution})
            ctx.ledger(S_PLAN, "orchestrator", "assumed",
                       f"{q.id} resolved to {q.default_resolution}: the main body governs over the appendix.")
        questions.append(q.model_dump(mode="json"))
    plan = [PlanStep(id=sid, agent=agent, title=title).model_dump() for sid, agent, title in PLAN_TEMPLATE]
    ctx.emit(S_PLAN, "orchestrator", "plan", "Plan ready", payload={"plan": plan, "open_questions": questions})
    if reply:
        ctx.narrate(S_PLAN, "orchestrator", reply.summary, ctx.allowed(), "planning")
    return StepOutput(data={"plan": plan, "open_questions": questions})
```

- [ ] **Step 5: Implement P2**

`services/api/kirchhoff/runs/phase2.py`:
```python
"""P2: Layout.place_racks → [Power ∥ Cooling] → Procurement.annotate_options → Power.recheck → OPTION GATE."""
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel

from kirchhoff.agents.specs import COOLING, LAYOUT, POWER, PROCUREMENT
from kirchhoff.contracts import CoolingNode, DesignModel, OpenQuestion, Rack, TopologyOption

from .policy import choose_option, lead_limit_weeks
from .steps import PhaseContext, PhaseOutcome, StepOutput, run_step

S_RESOLVE, S_PLACE, S_POWER = "p2.resolve_plan", "p2.place_racks", "p2.power_options"
S_COOL, S_ANN, S_RECHECK = "p2.cooling_sizing", "p2.annotate_options", "p2.power_recheck"


class OfferReply(BaseModel):
    offer: list[str]
    reason: str = ""


def _pairs(items: list[dict]) -> list[tuple[TopologyOption, DesignModel]]:
    return [(TopologyOption.model_validate(i["option"]), DesignModel.model_validate(i["model"])) for i in items]


def _dump(pairs) -> list[dict]:
    return [{"option": o.model_dump(mode="json"), "model": m.model_dump(mode="json")} for o, m in pairs]


def _rack_ids(racks: list[Rack]) -> list[str]:
    return sorted({x for r in racks for x in (r.id, r.row, *r.feeds)})


def run_p2(ctx: PhaseContext) -> PhaseOutcome:
    run_step(ctx, S_RESOLVE, lambda: _resolve_plan(ctx))
    racks = [Rack.model_validate(r) for r in run_step(ctx, S_PLACE, lambda: _place(ctx))["racks"]]
    with ThreadPoolExecutor(2) as pool:
        f_power = pool.submit(run_step, ctx, S_POWER, lambda: _power(ctx, racks))
        f_cool = pool.submit(run_step, ctx, S_COOL, lambda: _cooling(ctx, racks))
        power, cooling = f_power.result(), f_cool.result()
    ann = run_step(ctx, S_ANN, lambda: _annotate(ctx, power, cooling))
    run_step(ctx, S_RECHECK, lambda: _recheck(ctx, ann))
    return PhaseOutcome(gate="option", run_patch={"options": [i["option"] for i in ann["options"]]})


def _resolve_plan(ctx: PhaseContext) -> StepOutput:
    qs = [OpenQuestion.model_validate(q) for q in ctx.run().get("open_questions", [])]
    out, changed = [], False
    for q in qs:
        if q.resolution is None:
            q = q.model_copy(update={"resolution": q.default_resolution})
            changed = True
            ctx.ledger(S_RESOLVE, "orchestrator", "assumed",
                       f"{q.id} resolved to {q.default_resolution}: the main body governs over the appendix.")
        out.append(q)
    if changed:
        ctx.deps.store.update_doc(ctx.run_path, {"open_questions": [q.model_dump(mode="json") for q in out]})
    return StepOutput(data={"resolutions": {q.id: q.resolution for q in out}})


def _place(ctx: PhaseContext) -> StepOutput:
    scn, box = ctx.scenario(), {}

    def place_racks() -> dict:
        """Place every rack with the engine's deterministic default layout."""
        box["racks"] = ctx.deps.engine.place_racks(scn)
        return {"racks": len(box["racks"]), "rows": sorted({r.row for r in box["racks"]})}

    tool = ctx.tool(S_PLACE, "layout", place_racks)
    res = ctx.agent(LAYOUT, S_PLACE, "Place the racks for the hall, then narrate the result.", tools=[tool])
    if "racks" not in box:
        tool()
    ctx.narrate(S_PLACE, "layout", res.text if res else "", ctx.allowed(extra=_rack_ids(box["racks"])),
                "rack placement")
    return StepOutput(data={"racks": [r.model_dump(mode="json") for r in box["racks"]]})


def _power(ctx: PhaseContext, racks: list[Rack]) -> StepOutput:
    scn, box = ctx.scenario(), {}

    def enumerate_topologies() -> dict:
        """Enumerate the 2N, distributed-redundant and block-redundant options that pass R01 at minimum rating."""
        box["options"] = ctx.deps.engine.power_options(scn, racks)
        return {"options": [{"id": o.id, "installed_mva": o.installed_mva, "normal_loading_pct": o.normal_loading_pct,
                             "failover_loading_pct": o.failover_loading_pct, "cost": o.cost,
                             "spof_count": o.spof_count} for o, _ in box["options"]]}

    tool = ctx.tool(S_POWER, "power", enumerate_topologies)
    reply = ctx.agent_json(POWER, S_POWER, "Call enumerate_topologies, then decide which options to offer the "
                           'engineer. Reply with JSON {"offer": [option ids], "reason": one sentence}.',
                           OfferReply, tools=[tool])
    if "options" not in box:
        tool()
    ids = [o.id for o, _ in box["options"]]
    offer = [i for i in (reply.offer if reply else []) if i in ids] or ids
    options = [(o, m) for o, m in box["options"] if o.id in offer]
    ctx.narrate(S_POWER, "power", reply.reason if reply else "", ctx.allowed(*[m for _, m in options]),
                "topology options")
    return StepOutput(data={"options": _dump(options)})


def _cooling(ctx: PhaseContext, racks: list[Rack]) -> StepOutput:
    scn, box = ctx.scenario(), {}

    def size_cdus() -> dict:
        """Size the coolant distribution units per hydraulic zone with N+1 redundancy."""
        box["nodes"] = ctx.deps.engine.size_cooling(scn, racks)
        cdus = [n for n in box["nodes"] if n.kind == "cdu"]
        return {"cdus": len(cdus), "zones": sorted({n.zone for n in cdus})}

    def hydraulic_zones() -> dict:
        """List the hydraulic zones and the CDUs that serve each one."""
        if "nodes" not in box:
            size_cdus()
        zones: dict[str, list[str]] = {}
        for n in box["nodes"]:
            if n.kind == "cdu":
                zones.setdefault(n.zone, []).append(n.id)
        return {"zones": zones}

    t_size, t_zones = ctx.tool(S_COOL, "cooling", size_cdus), ctx.tool(S_COOL, "cooling", hydraulic_zones)
    res = ctx.agent(COOLING, S_COOL, "Size the CDUs and list the hydraulic zones, then narrate.",
                    tools=[t_size, t_zones])
    if "nodes" not in box:
        t_size()
    ids = [x for n in box["nodes"] for x in (n.id, n.zone)] + _rack_ids(racks)
    ctx.narrate(S_COOL, "cooling", res.text if res else "", ctx.allowed(extra=ids), "CDU sizing")
    return StepOutput(data={"cooling_nodes": [n.model_dump(mode="json") for n in box["nodes"]]})


def _annotate(ctx: PhaseContext, power: dict, cooling: dict) -> StepOutput:
    scn, erp, box = ctx.scenario(), ctx.erp(), {}
    nodes = [CoolingNode.model_validate(n) for n in cooling["cooling_nodes"]]
    options = [(o, m if m.cooling_nodes else m.model_copy(update={"cooling_nodes": nodes}))
               for o, m in _pairs(power["options"])]  # R20 guard

    def annotate_options() -> dict:
        """Check ERP lead times for every equipment line and apply the engine's in-stock swaps (rule R15)."""
        box["options"] = ctx.deps.engine.annotate_options(scn, options, erp)
        return {"options": [{"id": o.id, "max_lead_time_weeks": o.max_lead_time_weeks, "swaps": o.swaps}
                            for o, _ in box["options"]]}

    tool = ctx.tool(S_ANN, "procurement", annotate_options)
    res = ctx.agent(PROCUREMENT, S_ANN, "Check lead times against the tender limit and apply in-stock swaps, then "
                    "narrate the trade-off.", tools=[tool])
    if "options" not in box:
        tool()
    annotated = box["options"]
    for o, _ in annotated:
        for sw in o.swaps:
            ctx.ledger(S_ANN, "procurement", "did",
                       f"{o.id}: {sw.get('from')} replaced by {sw.get('to')} ({sw.get('reason', 'R15')})")
    rec = choose_option([o for o, _ in annotated], ctx.outputs(S_RESOLVE)["resolutions"], lead_limit_weeks(scn))
    ctx.narrate(S_ANN, "procurement", res.text if res else "", ctx.allowed(*[m for _, m in annotated]),
                "lead-time check")
    return StepOutput(data={"options": _dump(annotated), "recommended": rec.id if rec else None})


def _recheck(ctx: PhaseContext, ann: dict) -> StepOutput:
    scn, box = ctx.scenario(), {}
    swapped = [(o, m) for o, m in _pairs(ann["options"]) if o.swaps]

    def recheck_swapped_options() -> dict:
        """Re-run short circuit and rules R01, R04 and R04b on every option whose equipment was swapped."""
        summary = {}
        for o, m in swapped:
            fs = ctx.deps.engine.power_recheck(scn, m)
            summary[o.id] = {"pass": sum(f.status == "pass" for f in fs), "fail": sum(f.status == "fail" for f in fs),
                             "ikss_ka_before": max((float(s["ikss_ka_before"]) for s in o.swaps
                                                    if s.get("ikss_ka_before") is not None), default=None),
                             "ikss_ka_after": max((float(s["ikss_ka_after"]) for s in o.swaps
                                                   if s.get("ikss_ka_after") is not None), default=None)}
        box["summary"] = summary
        return {"options": summary}

    if swapped:
        tool = ctx.tool(S_RECHECK, "power", recheck_swapped_options)
        res = ctx.agent(POWER, S_RECHECK, "Re-check the swapped options with recheck_swapped_options, then "
                        "narrate the fault-level result.", tools=[tool])
        if "summary" not in box:
            tool()
        ctx.narrate(S_RECHECK, "power", res.text if res else "", ctx.allowed(*[m for _, m in swapped]),
                    "fault-level re-check")
        for oid, s in box["summary"].items():
            if s["fail"]:
                ctx.emit(S_RECHECK, "power", "status", f"{oid} fails a re-checked rule after the swap",
                         payload={"option": oid})
    else:
        box["summary"] = {}
        ctx.emit(S_RECHECK, "power", "status", "No swaps; nothing to re-check")
    ctx.emit(S_RECHECK, "procurement", "artifact", "Options ready",
             payload={"type": "options", "ref": ctx.run_path, "recommended": ann.get("recommended")})
    return StepOutput(data={"recheck": box["summary"]})
```


- [ ] **Step 6: Run tests**

Run: `cd services/api && uv run pytest tests/runs -q`
Expected: all runs tests pass (`34 passed, 1 skipped`).

- [ ] **Step 7: Run the live P1 smoke test against Vertex**

Run: `cd services/api && KIRCHHOFF_LIVE=1 KIRCHHOFF_RECORD_DIR=/tmp/kirchhoff-fixtures GOOGLE_GENAI_USE_VERTEXAI=true GOOGLE_CLOUD_PROJECT=ordinal-mep GOOGLE_CLOUD_QUOTA_PROJECT=ordinal-mep GOOGLE_CLOUD_LOCATION=global uv run pytest tests/runs/test_runs_live_p1.py -v -s`
Expected: 1 passed, with a printed JSON line of `elapsed_s` and the intake score. If a quote fails verification because Gemini paraphrased, tighten `TENDER_PROMPT` ("copy the characters exactly, including the % sign and spaces") and re-run. Keep the recorded fixtures in `/tmp/kirchhoff-fixtures` for debugging; do not commit them.

- [ ] **Step 8: Commit**

```bash
git add services/api/kirchhoff/runs services/api/tests/runs
git commit -m "feat(runs): P1 intake+plan and P2 layout/power/cooling/procurement/recheck phases, live P1 smoke

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 12: HTTP API — app wiring, production Deps, workspace create/reset, runs, plan/option gates, resume, limits (Tue 14 → Wed 15)

**Files:**
- Modify: `services/api/kirchhoff/api/app.py`
- Create: `services/api/kirchhoff/api/errors.py`, `services/api/kirchhoff/api/deps.py`, `services/api/kirchhoff/api/workspace_routes.py`, `services/api/kirchhoff/api/runs_routes.py`
- Create: `services/api/tests/api/conftest.py`, `services/api/tests/api/test_api_runs.py`, `services/api/tests/api/test_api_workspace.py`

**Interfaces:**
- Consumes: `make_current_uid`, `firebase_verify` (P0); `GET /api/whoami` (P0 fix wave; permanent, kept in the rewired app); `Deps`, `MemoryBlobStore`, `GcsBlobStore` (Task 8); `start_phase`, `resume_from_gate`, `resume_run`, `WrongState`, `GateExpired`, `LeaseBusy` (Task 10); `CapReached`, `lease_is_live`, `run_path` (Task 6); `Store.delete_tree`; `AdkRunner`, `GenaiRunner`, `RecordingRunner` (Task 5); `FakeEnterprise`, `build_fake_deps`, `load_erp_seed` (Tasks 7–8).
- Produces:
  - `create_app(store=None, verify_token=None, deps: Deps | None = None) -> FastAPI`. If `deps` is omitted, `build_production_deps(store)` is used. It includes WS4's router if `kirchhoff.api.enterprise_proxy.make_router(store, current_uid)` exists, and sets `app.state.deps`.
  - `build_production_deps(store=None) -> Deps` makes no network calls at construction. Env switches: `KIRCHHOFF_FAKES=1` (fake engine, replay agents, real store, in-process blobs served inline by `/api/files`), `KIRCHHOFF_AGENT_BACKEND=genai`, `KIRCHHOFF_RECORD_DIR`, `KIRCHHOFF_BLOBS=memory` (`MemoryBlobStore(public_base=None)`), `KIRCHHOFF_SCENARIOS_DIR` (default `/app/scenarios` in the image, else `<repo>/scenarios`) and `KIRCHHOFF_SEED_DIR` (default `/app/seed`, else `<repo>/apps/web/public/demo/projects`). The engine is `LazyModule("kirchhoff.engine.api")`. The enterprise client is `kirchhoff.enterprise.client.make_enterprise_client()` (WS4), or a `FakeEnterprise` over `erp_seed.yaml` with a logged warning.
  - `err(status, detail, **extra) -> JSONResponse`.
  - Routes (interfaces table): `GET /api/whoami` → `{uid}` (P0, unchanged); `POST /api/workspace` → `{uid, created}`; `POST /api/workspace/reset` → `{ok}` (409 `run_in_progress`); `POST /api/runs {project_id: "hall-b", autonomy}` → 202 `{run_id}` (429 `visitor_rate_limit` / `global_cap`+`offer`); `POST /api/runs/{rid}/gates/plan {answers, plan_notes}` → 202 `{ok}` (409 `wrong_state`/`gate_expired`; 422 `invalid_answer`); `POST /api/runs/{rid}/gates/option {option_id}` → 202 (422 `option_not_offered`); `POST /api/runs/{rid}/resume` → 202 `{resumed}`. Another visitor's run returns 404.

- [ ] **Step 1: Write the API test fixtures and failing tests**

`services/api/tests/api/conftest.py`:
```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kirchhoff.api.app import create_app
from kirchhoff.runs.fakes import CheckedStore, build_fake_deps, build_fake_scenarios

INTAKE_FIX = Path(__file__).resolve().parents[1] / "intake" / "fixtures"
GROUND_TRUTH = Path(__file__).resolve().parents[4] / "scenarios" / "hall_a" / "ground_truth.yaml"


@pytest.fixture(scope="session")
def scen_dir(tmp_path_factory):
    return build_fake_scenarios(tmp_path_factory.mktemp("scenarios"), INTAKE_FIX / "tender.yaml",
                                INTAKE_FIX / "geometry.yaml", GROUND_TRUTH)


@pytest.fixture
def deps(scen_dir, tmp_path):
    return build_fake_deps(CheckedStore(), scen_dir, seed_dir=tmp_path, spawn=lambda fn: fn(), heartbeat_s=3600.0)


@pytest.fixture
def client(deps):
    return TestClient(create_app(deps=deps, verify_token=lambda token: "u1"))


@pytest.fixture
def auth():
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def firestore_safe():
    def _check(store) -> None:
        assert isinstance(store, CheckedStore)
        assert not store.problems, store.problems[:3]
    return _check
```

`services/api/tests/api/test_api_runs.py`:
```python
import pytest
from fastapi.testclient import TestClient

from kirchhoff.api.app import create_app
from kirchhoff.runs.leases import LIVE_RUNS_DOC, run_path
from kirchhoff.runs.phase1 import run_p1
from kirchhoff.runs.phase2 import run_p2
from kirchhoff.runs.steps import PhaseOutcome

NEW_RUN = {"project_id": "hall-b", "autonomy": "ask"}


def review_stub(ctx):
    return PhaseOutcome(gate="review")


@pytest.fixture
def staged(deps):
    deps.phases = {"p1": run_p1, "p2": run_p2, "p3": review_stub}
    return deps


def _run(d, rid):
    return d.store.get_doc(run_path("u1", rid))


def _start(client, auth) -> str:
    r = client.post("/api/runs", json=NEW_RUN, headers=auth)
    assert r.status_code == 202, r.text
    return r.json()["run_id"]


def test_runs_require_a_token(client):
    assert client.post("/api/runs", json=NEW_RUN).status_code == 401


def test_create_run_starts_p1_and_parks_at_the_plan_gate(client, staged, auth):
    rid = _start(client, auth)
    run = _run(staged, rid)
    assert (run["status"], run["gate"], run["project_id"]) == ("at_gate", "plan", "hall-b")
    assert len(staged.store.get_doc("workspaces/u1")["run_starts"]) == 1


def test_only_hall_b_runs_live(client, auth):
    assert client.post("/api/runs", json={"project_id": "hall-a"}, headers=auth).status_code == 422


def test_visitor_rate_limit(client, staged, auth):
    now = staged.clock()
    staged.store.set_doc("workspaces/u1", {"created_at": now, "run_starts": [now - 60] * 5})
    r = client.post("/api/runs", json=NEW_RUN, headers=auth)
    assert r.status_code == 429 and r.json() == {"detail": "visitor_rate_limit"}


def test_global_cap_offers_replay_and_leaves_no_run(client, staged, auth):
    now = staged.clock()
    staged.store.set_doc(LIVE_RUNS_DOC, {"runs": {"a__1": now, "b__2": now, "c__3": now}})
    r = client.post("/api/runs", json=NEW_RUN, headers=auth)
    assert r.status_code == 429 and r.json() == {"detail": "global_cap", "offer": "replay"}
    assert staged.store.list_docs("workspaces/u1/runs") == []


def test_plan_gate_validates_then_starts_p2(client, staged, auth):
    rid = _start(client, auth)
    wrong = client.post(f"/api/runs/{rid}/gates/option", json={"option_id": "2N"}, headers=auth)
    assert wrong.status_code == 409 and wrong.json() == {"detail": "wrong_state"}
    bad = client.post(f"/api/runs/{rid}/gates/plan", json={"answers": {"Q-redundancy": "3N"}}, headers=auth)
    assert bad.status_code == 422 and bad.json()["detail"] == "invalid_answer"
    ok = client.post(f"/api/runs/{rid}/gates/plan", headers=auth,
                     json={"answers": {"Q-redundancy": "compare_all"},
                           "plan_notes": {"p2.place_racks": "Keep R1 close to room A"}})
    assert ok.status_code == 202
    run = _run(staged, rid)
    assert run["gate"] == "option" and run["open_questions"][0]["resolution"] == "compare_all"
    assert next(p for p in run["plan"] if p["id"] == "p2.place_racks")["note"] == "Keep R1 close to room A"


def test_option_gate_selects_and_starts_p3(client, staged, auth):
    rid = _start(client, auth)
    client.post(f"/api/runs/{rid}/gates/plan", json={}, headers=auth)
    assert client.post(f"/api/runs/{rid}/gates/option", json={"option_id": "XX"}, headers=auth).status_code == 422
    assert client.post(f"/api/runs/{rid}/gates/option", json={"option_id": "2N"}, headers=auth).status_code == 202
    run = _run(staged, rid)
    assert (run["gate"], run["selected_option"]) == ("review", "2N")


def test_resume_and_ownership(client, staged, auth):
    rid = _start(client, auth)
    assert client.post(f"/api/runs/{rid}/resume", headers=auth).json() == {"resumed": False}
    other = TestClient(create_app(deps=staged, verify_token=lambda token: "u2"))
    assert other.post(f"/api/runs/{rid}/resume", headers=auth).status_code == 404
    assert other.post(f"/api/runs/{rid}/gates/plan", json={}, headers=auth).status_code == 404


def test_gate_expiry(client, staged, auth):
    rid = _start(client, auth)
    run = _run(staged, rid)
    staged.store.set_doc(run_path("u1", rid), {**run, "metrics": {**run["metrics"],
                                                                 "gate_entered_at": staged.clock() - 90_000}})
    r = client.post(f"/api/runs/{rid}/gates/plan", json={}, headers=auth)
    assert r.status_code == 409 and r.json() == {"detail": "gate_expired"}
    assert _run(staged, rid)["status"] == "expired"
```

`services/api/tests/api/test_api_workspace.py`:
```python
from fastapi.testclient import TestClient

from kirchhoff.api.app import create_app
from kirchhoff.api.deps import LazyModule
from kirchhoff.runs.phase1 import run_p1
from kirchhoff.store.memory import MemoryStore


def test_workspace_create_is_idempotent(client, auth):
    assert client.post("/api/workspace", headers=auth).json() == {"uid": "u1", "created": True}
    assert client.post("/api/workspace", headers=auth).json() == {"uid": "u1", "created": False}


def test_whoami_survives_the_app_rewiring(client, auth):
    assert client.get("/api/whoami").status_code == 401  # infra/smoke.sh probes this
    assert client.get("/api/whoami", headers=auth).json() == {"uid": "u1"}


def test_reset_deletes_visitor_data(client, deps, auth):
    deps.phases = {"p1": run_p1}
    assert client.post("/api/runs", json={"project_id": "hall-b"}, headers=auth).status_code == 202
    deps.blobs.put("workspaces/u1/exports/x-r1/boq.csv", b"a,b", "text/csv")
    deps.enterprise.create_pr("u1", "hall-b", "x-r1", [], idempotency_key="k1")
    assert client.post("/api/workspace/reset", headers=auth).json() == {"ok": True}
    assert deps.store.list_docs("workspaces/u1/runs") == [] and deps.store.get_doc("workspaces/u1") is None
    assert not deps.blobs.blobs and not deps.enterprise.prs


def test_reset_refuses_while_a_run_holds_a_live_lease(client, deps, auth):
    deps.store.set_doc("workspaces/u1/runs/r1", {"id": "r1", "status": "running",
                                                  "lease": {"owner": "w", "attempt": 1, "heartbeat_at": deps.clock()}})
    r = client.post("/api/workspace/reset", headers=auth)
    assert r.status_code == 409 and r.json() == {"detail": "run_in_progress"}


def test_production_app_builds_without_network(monkeypatch):
    monkeypatch.delenv("KIRCHHOFF_FAKES", raising=False)
    app = create_app(store=MemoryStore(), verify_token=lambda token: "u1")
    assert TestClient(app).get("/api/health").json()["ok"] is True
    assert isinstance(app.state.deps.engine, LazyModule)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd services/api && uv run pytest tests/api -q`
Expected: FAIL with `ImportError` (`create_app()` has no `deps` parameter / `kirchhoff.api.deps` missing).

- [ ] **Step 3: Implement errors and production wiring**

`services/api/kirchhoff/api/errors.py`:
```python
from fastapi.responses import JSONResponse


def err(status: int, detail: str, **extra) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": detail, **extra})
```

`services/api/kirchhoff/api/deps.py`:
```python
"""Production wiring. Constructing Deps makes no network calls (clients are lazy)."""
import importlib
import logging
import os
from pathlib import Path

from kirchhoff.agents.adk_runner import AdkRunner
from kirchhoff.agents.genai_runner import GenaiRunner
from kirchhoff.agents.runner import RecordingRunner
from kirchhoff.runs.blobs import GcsBlobStore, MemoryBlobStore
from kirchhoff.runs.deps import Deps

log = logging.getLogger("kirchhoff")
_HERE = Path(__file__).resolve()


def _ancestor(n: int) -> Path:
    p = _HERE
    for _ in range(n + 1):
        p = p.parent
    return p


class LazyModule:
    """Imports the module on first attribute access (the WS1 engine may land after this code)."""

    def __init__(self, name: str) -> None:
        self._name = name
        self._mod = None

    def __getattr__(self, attr: str):
        if attr.startswith("_"):
            raise AttributeError(attr)
        if self._mod is None:
            self._mod = importlib.import_module(self._name)
        return getattr(self._mod, attr)


def _first(env: str, *candidates: Path) -> Path:
    if os.environ.get(env):
        return Path(os.environ[env])
    return next((c for c in candidates if c.exists()), candidates[0])


def scenarios_dir() -> Path:  # image: /app/scenarios; repo: <repo>/scenarios
    return _first("KIRCHHOFF_SCENARIOS_DIR", _ancestor(2) / "scenarios", _ancestor(4) / "scenarios")


def seed_dir() -> Path:  # image: /app/seed; repo: the static demo bundles WS4 generates
    return _first("KIRCHHOFF_SEED_DIR", _ancestor(2) / "seed", _ancestor(4) / "apps" / "web" / "public" / "demo" / "projects")


def _enterprise(scen: Path):
    try:
        from kirchhoff.enterprise.client import make_enterprise_client  # WS4
        return make_enterprise_client()
    except ImportError:
        from kirchhoff.agents.ports import load_erp_seed
        from kirchhoff.runs.fakes import FakeEnterprise

        seed = scen / "hall_a" / "erp_seed.yaml"
        log.warning("kirchhoff.enterprise.client unavailable; using the in-process sandbox")
        return FakeEnterprise(load_erp_seed(seed) if seed.exists() else None)


def _asset_engines() -> dict:
    def grid(d: Path) -> dict:
        return importlib.import_module("kirchhoff.engine.grid").evaluate_grid(d)

    def solar(d: Path) -> dict:
        return importlib.import_module("kirchhoff.engine.solar").evaluate_solar(d)

    return {"grid": grid, "solar": solar}


def build_production_deps(store=None) -> Deps:
    scen, seed = scenarios_dir(), seed_dir()
    if store is None:
        from kirchhoff.store.firestore import FirestoreStore
        store = FirestoreStore()
    if os.environ.get("KIRCHHOFF_FAKES") == "1":  # local UI development before WS1/WS4/Vertex are wired
        from kirchhoff.runs.fakes import build_fake_deps
        return build_fake_deps(store, scen, seed_dir=seed, blobs=MemoryBlobStore(public_base=None))
    runner = GenaiRunner() if os.environ.get("KIRCHHOFF_AGENT_BACKEND") == "genai" else AdkRunner()
    if os.environ.get("KIRCHHOFF_RECORD_DIR"):
        runner = RecordingRunner(runner, Path(os.environ["KIRCHHOFF_RECORD_DIR"]))
    blobs = MemoryBlobStore(public_base=None) if os.environ.get("KIRCHHOFF_BLOBS") == "memory" else GcsBlobStore()
    return Deps(store=store, engine=LazyModule("kirchhoff.engine.api"), runner=runner, enterprise=_enterprise(scen),
                blobs=blobs, scenarios_dir=scen, seed_dir=seed, voice_runner=GenaiRunner(),
                asset_engines=_asset_engines())
```

- [ ] **Step 4: Implement the workspace and runs routes**

`services/api/kirchhoff/api/workspace_routes.py`:
```python
from fastapi import APIRouter, Depends

from kirchhoff.runs.deps import Deps
from kirchhoff.runs.leases import lease_is_live

from .errors import err


def make_router(deps: Deps, current_uid) -> APIRouter:
    router = APIRouter()

    @router.post("/api/workspace")
    def ensure_workspace(uid: str = Depends(current_uid)):
        path = f"workspaces/{uid}"
        created = deps.store.get_doc(path) is None
        if created:
            deps.store.set_doc(path, {"created_at": deps.clock(), "last_run_at": None, "run_starts": []})
        return {"uid": uid, "created": created}

    @router.post("/api/workspace/reset")
    def reset_workspace(uid: str = Depends(current_uid)):
        now = deps.clock()
        if any(lease_is_live(r.get("lease"), now) for r in deps.store.list_docs(f"workspaces/{uid}/runs")):
            return err(409, "run_in_progress")
        deps.store.delete_tree(f"workspaces/{uid}")
        deps.blobs.delete_prefix(f"workspaces/{uid}/")
        deps.enterprise.reset_visitor(uid)
        return {"ok": True}

    return router
```

`services/api/kirchhoff/api/runs_routes.py`:
```python
import uuid
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from kirchhoff.contracts import OpenQuestion, PlanStep, RunRecord, TopologyId
from kirchhoff.runs.deps import Deps
from kirchhoff.runs.leases import CapReached, run_path
from kirchhoff.runs.orchestrator import (GateExpired, LeaseBusy, WrongState, resume_from_gate, resume_run,
                                        start_phase)

from .errors import err

RUNS_PER_HOUR = 5


class RunCreate(BaseModel):
    project_id: Literal["hall-b"]
    autonomy: Literal["ask", "auto"] = "ask"


class PlanGate(BaseModel):
    answers: dict[str, str] = {}
    plan_notes: dict[str, str] = {}


class OptionGate(BaseModel):
    option_id: TopologyId


def make_router(deps: Deps, current_uid) -> APIRouter:
    router = APIRouter()

    def advance(uid: str, rid: str, gate: str, patch: dict):
        try:
            resume_from_gate(deps, uid, rid, gate, patch)
        except WrongState:
            return err(409, "wrong_state")
        except GateExpired:
            return err(409, "gate_expired")
        except LeaseBusy:
            return err(409, "run_in_progress")
        except CapReached:
            return err(429, "global_cap", offer="replay")
        return {"ok": True}

    def at_gate(run: dict, gate: str) -> bool:
        return run.get("status") == "at_gate" and run.get("gate") == gate

    @router.post("/api/runs", status_code=202)
    def create_run(body: RunCreate, uid: str = Depends(current_uid)):
        now, ws_path = deps.clock(), f"workspaces/{uid}"
        ws = deps.store.get_doc(ws_path) or {}
        recent = [t for t in ws.get("run_starts", []) if now - t < 3600]
        if len(recent) >= RUNS_PER_HOUR:
            return err(429, "visitor_rate_limit")
        rid = uuid.uuid4().hex[:12]
        deps.store.set_doc(run_path(uid, rid), RunRecord(id=rid, project_id=body.project_id, status="running",
                                                         autonomy=body.autonomy, phase="p1",
                                                         started_at=now).model_dump(mode="json"))
        try:
            start_phase(deps, uid, rid, "p1")
        except CapReached:
            deps.store.delete_tree(run_path(uid, rid))
            return err(429, "global_cap", offer="replay")
        deps.store.update_doc(ws_path, {"created_at": ws.get("created_at", now), "last_run_at": now,
                                        "run_starts": recent + [now]})
        return {"run_id": rid}

    @router.post("/api/runs/{rid}/gates/plan", status_code=202)
    def gate_plan(rid: str, body: PlanGate, uid: str = Depends(current_uid)):
        run = deps.store.get_doc(run_path(uid, rid))
        if run is None:
            return err(404, "run_not_found")
        if not at_gate(run, "plan"):
            return err(409, "wrong_state")
        qs = {q["id"]: OpenQuestion.model_validate(q) for q in run.get("open_questions", [])}
        for qid, value in body.answers.items():
            if qid not in qs or value not in qs[qid].options:
                return err(422, "invalid_answer", question_id=qid)
        questions = [(q.model_copy(update={"resolution": body.answers[q.id]}) if q.id in body.answers else q)
                     .model_dump(mode="json") for q in qs.values()]
        plan = [PlanStep.model_validate(p) for p in run.get("plan", [])]
        plan = [(p.model_copy(update={"note": body.plan_notes[p.id]}) if p.id in body.plan_notes else p).model_dump()
                for p in plan]
        return advance(uid, rid, "plan", {"open_questions": questions, "plan": plan})

    @router.post("/api/runs/{rid}/gates/option", status_code=202)
    def gate_option(rid: str, body: OptionGate, uid: str = Depends(current_uid)):
        run = deps.store.get_doc(run_path(uid, rid))
        if run is None:
            return err(404, "run_not_found")
        if not at_gate(run, "option"):
            return err(409, "wrong_state")
        if body.option_id not in {o["id"] for o in run.get("options", [])}:
            return err(422, "option_not_offered")
        return advance(uid, rid, "option", {"selected_option": body.option_id})

    @router.post("/api/runs/{rid}/resume", status_code=202)
    def resume(rid: str, uid: str = Depends(current_uid)):
        if deps.store.get_doc(run_path(uid, rid)) is None:
            return err(404, "run_not_found")
        try:
            return {"resumed": resume_run(deps, uid, rid)}
        except CapReached:
            return err(429, "global_cap", offer="replay")

    return router
```

- [ ] **Step 5: Rewire the app factory**

Replace `services/api/kirchhoff/api/app.py` with (keep `GET /api/whoami` exactly as P0 wrote it: it is permanent and `infra/smoke.sh` probes it):
```python
import os
from typing import Callable

from fastapi import Depends, FastAPI

from kirchhoff.runs.deps import Deps
from kirchhoff.store import Store

from . import runs_routes, workspace_routes
from .auth import firebase_verify, make_current_uid
from .hello import make_router as hello_router

VERSION = os.environ.get("K_REVISION", "dev")


def create_app(store: Store | None = None, verify_token: Callable[[str], str] | None = None,
               deps: Deps | None = None) -> FastAPI:
    if deps is None:
        from .deps import build_production_deps
        deps = build_production_deps(store)
    store = deps.store
    current_uid = make_current_uid(verify_token or firebase_verify)
    app = FastAPI(title="Kirchhoff API")

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "version": VERSION}

    @app.get("/api/whoami")
    def whoami(uid: str = Depends(current_uid)) -> dict:  # permanent (P0 fix wave); smoke test probes it
        return {"uid": uid}

    app.include_router(hello_router(store, current_uid))  # removed in Task 18
    app.include_router(workspace_routes.make_router(deps, current_uid))
    app.include_router(runs_routes.make_router(deps, current_uid))
    try:
        from .enterprise_proxy import make_router as enterprise_router  # WS4-owned module
    except ImportError:
        enterprise_router = None
    if enterprise_router is not None:
        app.include_router(enterprise_router(store, current_uid))
    app.state.store, app.state.current_uid, app.state.deps = store, current_uid, deps
    return app
```

- [ ] **Step 6: Run the whole suite**

Run: `cd services/api && uv run pytest -q`
Expected: everything passes, including P0's `test_api_hello.py` (live tests skipped).

- [ ] **Step 7: Try the fakes locally against real Firestore (for WS3)**

Run: `cd services/api && KIRCHHOFF_FAKES=1 KIRCHHOFF_BLOBS=memory GOOGLE_CLOUD_PROJECT=ordinal-mep GOOGLE_CLOUD_QUOTA_PROJECT=ordinal-mep uv run uvicorn kirchhoff.api.app:create_app --factory --port 8080`
Then, in another shell, run `curl -s localhost:8080/api/health`. Expected: `{"ok":true,"version":"dev"}`. Tell WS3 that `make dev-api` with `KIRCHHOFF_FAKES=1` gives them a full P1→P4 flow with no engine or Vertex.

- [ ] **Step 8: Commit**

```bash
git add services/api/kirchhoff/api services/api/tests/api
git commit -m "feat(api): production deps, workspace create/reset, runs + plan/option gates, resume, limits

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 13: P3 — option selection, routing, clashes, BOQ, revisions, Checker, fix loop, Docs (stub exports) (Wed 15)

**Files:**
- Create: `services/api/kirchhoff/runs/revisions.py`, `services/api/kirchhoff/runs/phase3.py`, `services/api/kirchhoff/agents/docs_export.py`
- Test: `services/api/tests/runs/test_runs_p3.py`

**Interfaces:**
- Consumes: the P2 outputs (`p2.resolve_plan`, `p2.annotate_options`), `p1.intake` brief, `OWNER`, `choose_option`, `preferred_candidate`, `criterion`, `lead_limit_weeks` (Task 11), `POWER, COOLING, LAYOUT, DOCS` (Task 5), `sanitize` (Task 4), and the engine facade `route`, `detect_clashes`, `derive_pr_lines`, `check`, `fix_candidates`, `apply_fix`, `model_hash`, `ledger_not_checked`.
- Produces:
  - `kirchhoff.runs.revisions`: `LIVE_AUDIO_NOTE` (R13), `rev_id(rid, n)`, `model_blob_path(uid, rev)`, `gather_ledger(ctx) -> list[LedgerEntry]` (ledger events from committing or current attempts, deduplicated), and `build_revision(ctx, n, parent, model, findings, summary) -> tuple[Revision, docs]`. The model goes to the blob store (R7) and the revision doc gets `model=None`, `model_url="revisions/{rev}/model.json"` and `hash=engine.model_hash(model)` (R22); there is one finding doc per finding. Also `load_revision_model(deps, uid, rev_doc) -> DesignModel`, `diff_elements(old, new) -> list[str]`, `run_revisions(store, uid, rid) -> list[dict]` (ordered by n), `latest_revision(store, uid, rid) -> dict | None` and `with_citation_boxes(findings, tender_pdf) -> list[Finding]` (the engine's `tender_refs` carry page + verbatim quote but no box; this adds pdfplumber's `bbox` so the UI's tender chip highlights the clause, spec §12 screen 6).
  - `kirchhoff.agents.docs_export`: `SECTIONS`, the `Exporter` protocol `export(*, uid, rev: Revision, findings, fixes, brief, options, pr_lines, order, summary) -> list[{"name", "path", "status", ...}]`, and `StubExporter` (status `pending`, path `None`). Only files with a `path` get an `artifact {type: "export", ref: path, name, status}` event; pending stubs get a `status` event, so the UI never sees an empty export ref.
  - `phase3.run_p3(ctx) -> PhaseOutcome(gate="review", run_patch={"selected_option"})`. Steps: `p3.select_option`, `p3.route`, `p3.clashes`, `p3.boq`, `p3.check.{n}`, `p3.fix.{n}` (n ≤ 2) and `p3.docs`. Fix records on the failing revision's findings are `fix = {candidate, label, reason, criterion, agent, cost_delta, deltas}` and `rejected_fix = {candidate, label, cost_delta, deltas}`, where `deltas` is the candidate's engine metrics plus `cost_delta` (the UI's finding drawer lists `deltas`). Each check emits its `artifact {type: "revision", ref: "workspaces/{uid}/revisions/{rev}", changed: [element ids]}` event **first**, then one `finding {finding_id, rule_id, element_id, status, rev}` event per failure (WS3 ruling R8). Metric `time_to_clean_s` is set at the first all-pass revision. **UI rule (WS3):** Approve is disabled iff the latest revision's `check_summary.fail > 0`.

- [ ] **Step 1: Write the failing tests**

`services/api/tests/runs/test_runs_p3.py`:
```python
import pytest
import yaml

from kirchhoff.contracts import Citation, DesignModel, Finding
from kirchhoff.runs.fakes import FakeEngine
from kirchhoff.runs.leases import run_path
from kirchhoff.runs.orchestrator import resume_from_gate, start_phase
from kirchhoff.runs.outputs import load_outputs
from kirchhoff.runs.phase1 import run_p1
from kirchhoff.runs.phase2 import run_p2
from kirchhoff.runs.phase3 import run_p3
from kirchhoff.runs.revisions import latest_revision, run_revisions, with_citation_boxes


@pytest.fixture
def p123(deps):
    deps.phases = {"p1": run_p1, "p2": run_p2, "p3": run_p3}
    return deps


def _to_review(d, make_run, autonomy="ask", option="2N") -> str:
    rid = make_run(autonomy=autonomy)
    start_phase(d, "u1", rid, "p1")
    if autonomy == "ask":
        resume_from_gate(d, "u1", rid, "plan")
        resume_from_gate(d, "u1", rid, "option", {"selected_option": option})
    return rid


def _run(d, rid):
    return d.store.get_doc(run_path("u1", rid))


def _findings(d, rev):
    return {f["id"]: f for f in d.store.list_docs(f"workspaces/u1/revisions/{rev}/findings")}


def _events(d, rid):
    return d.store.list_docs(f"{run_path('u1', rid)}/events")


def test_golden_path_two_revisions_and_fix_choices(p123, make_run, firestore_safe):
    rid = _to_review(p123, make_run)
    run = _run(p123, rid)
    assert (run["status"], run["gate"], run["selected_option"]) == ("at_gate", "review", "2N")
    r1, r2 = run_revisions(p123.store, "u1", rid)
    assert r1["check_summary"]["fail"] == 2 and r2["check_summary"]["fail"] == 0 and r2["parent"] == r1["id"]
    assert r1["model"] is None and r2["model_url"] == f"revisions/{r2['id']}/model.json"
    model = DesignModel.model_validate_json(p123.blobs.get(f"workspaces/u1/{r2['model_url']}"))
    assert r2["hash"] == p123.engine.model_hash(model) != r1["hash"]
    f1 = _findings(p123, r1["id"])
    assert f1["R05:FA-01"]["fix"]["candidate"] == "FA-01:cable-CBL-240-8P"
    assert f1["R05:FA-01"]["rejected_fix"]["candidate"] == "FA-01:upsize-BW-2000"
    assert f1["R11:H-Z2"]["fix"]["candidate"] == "H-Z2:local-drop"
    assert f1["R11:H-Z2"]["fix"]["criterion"].startswith("fewest changed pipe segments")
    assert "fewest pipe segments" in f1["R11:H-Z2"]["fix"]["reason"]
    assert f1["R05:FA-01"]["fix"]["deltas"]["cost_delta"] == f1["R05:FA-01"]["fix"]["cost_delta"]
    assert "cost_delta" in f1["R05:FA-01"]["rejected_fix"]["deltas"]
    revs = [e["payload"] for e in _events(p123, rid) if e["kind"] == "artifact" and e["payload"]["type"] == "revision"]
    assert {"FA-01", "H-Z2"} <= set(revs[-1]["changed"])
    art = next(e for e in _events(p123, rid) if e["kind"] == "artifact" and e["step"] == "p3.check.1")
    fails = [e for e in _events(p123, rid) if e["kind"] == "finding" and e["step"] == "p3.check.1"]
    assert len(fails) == 2 and all(e["seq"] > art["seq"] and e["payload"]["rev"] == r1["id"] for e in fails)
    assert run["metrics"]["time_to_clean_s"] > 0
    assert latest_revision(p123.store, "u1", rid)["id"] == r2["id"]
    firestore_safe(p123.store)


def test_revision_ledger_and_stub_docs(p123, make_run):
    rid = _to_review(p123, make_run)
    r2 = latest_revision(p123.store, "u1", rid)
    texts = [e["text"] for e in r2["ledger"]]
    assert "2N: TX-2500 replaced by TX-3150 (R15)" in texts
    assert "Spoken Gemini Live audio is not digit-filtered; on-screen transcripts are." in texts
    assert any(e["kind"] == "not_checked" and e["text"] == "Selectivity" for e in r2["ledger"])
    docs = load_outputs(p123.store, p123.blobs, run_path("u1", rid), "p3.docs")
    assert [f["status"] for f in docs["files"]] == ["pending", "pending"] and docs["order"][0] == "summary"
    assert docs["summary"] == "The 2N design passes every check after fixes to FA-01 and H-Z2."
    evs = _events(p123, rid)
    assert not [e for e in evs if e["kind"] == "artifact" and e["payload"]["type"] == "export"]
    assert [e["title"] for e in evs if e["step"] == "p3.docs" and e["kind"] == "status"] == \
        ["calc-report.pdf pending", "boq.csv pending"]


def test_tender_refs_get_pdfplumber_boxes(deps):
    tender = yaml.safe_load((deps.scenarios_dir / "hall_a" / "tender.yaml").read_text(encoding="utf-8"))
    c = next(c for c in tender["clauses"] if c.get("quote"))
    f = Finding(id="R05:FA-01", rule_id="R05", element_id="FA-01", status="fail", title="Voltage drop",
                tender_refs=[Citation(doc_id="tender-hall-a", page=c["page"], quote=c["quote"], clause=c["id"]),
                             Citation(doc_id="tender-hall-a", page=1, quote="", clause="§2.3")])
    (out,) = with_citation_boxes([f], deps.inputs().tender_pdf)
    assert out.tender_refs[0].bbox is not None and out.tender_refs[1].bbox is None
    assert with_citation_boxes([f], deps.scenarios_dir / "missing.pdf") == [f]


def test_auto_picks_2n_by_the_resolved_clause(p123, make_run):
    rid = _to_review(p123, make_run, autonomy="auto")
    run = _run(p123, rid)
    assert (run["gate"], run["selected_option"]) == ("review", "2N")
    assert any(e["title"].startswith("Auto mode chose 2N") for e in _events(p123, rid) if e["kind"] == "ledger")


def test_invalid_agent_choice_falls_back_to_the_stated_criterion(p123, make_run):
    p123.runner.replies["power:p3.fix.1:R05:FA-01"] = {"text": {"candidate_id": "nope", "reason": "x"}}
    rid = _to_review(p123, make_run)
    fix = _findings(p123, run_revisions(p123.store, "u1", rid)[0]["id"])["R05:FA-01"]["fix"]
    assert fix["candidate"] == "FA-01:cable-CBL-240-8P"
    assert fix["reason"] == ("Power chose FA-01:cable-CBL-240-8P for R05:FA-01: largest voltage-drop margin per "
                             "dollar, that is the limit minus the resulting drop, divided by the cost delta.")


class NoFixEngine(FakeEngine):
    def apply_fix(self, model, candidate):
        self._log("apply_fix")
        return model


def test_fix_loop_exhaustion_stops_at_review_with_open_findings(p123, make_run):
    p123.engine = NoFixEngine()
    rid = _to_review(p123, make_run)
    revs = run_revisions(p123.store, "u1", rid)
    assert len(revs) == 3 and revs[-1]["check_summary"]["fail"] == 2
    ledger = [e["title"] for e in _events(p123, rid) if e["kind"] == "ledger"]
    assert any(t.startswith("Fix loop stopped after 2 iterations") for t in ledger)
    assert _run(p123, rid)["gate"] == "review"


class NoSwapEngine(FakeEngine):
    def annotate_options(self, scn, options, erp):
        self._log("annotate_options")
        return list(options)  # TX-2500 stays: 98 weeks breaks §2.3 for every option


def test_auto_parks_at_the_option_gate_when_no_option_qualifies(p123, make_run):
    p123.engine = NoSwapEngine()
    rid = make_run(autonomy="auto")
    start_phase(p123, "u1", rid, "p1")
    assert (_run(p123, rid)["status"], _run(p123, rid)["gate"]) == ("at_gate", "option")
    resume_from_gate(p123, "u1", rid, "option", {"selected_option": "2N"})
    assert _run(p123, rid)["gate"] == "review"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd services/api && uv run pytest tests/runs/test_runs_p3.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'kirchhoff.runs.phase3'`

- [ ] **Step 3: Implement revisions and the export stub**

`services/api/kirchhoff/runs/revisions.py`:
```python
"""Revisions (spec §14): model in Cloud Storage (R7), engine hash (R22), findings as subcollection docs."""
import threading
from pathlib import Path

from kirchhoff.contracts import Citation, DesignModel, Finding, LedgerEntry, Revision
from kirchhoff.intake.verify import PdfText
from kirchhoff.store import Store

from .deps import Deps
from .steps import PhaseContext

LIVE_AUDIO_NOTE = LedgerEntry(kind="not_checked", agent="copilot",
                              text="Spoken Gemini Live audio is not digit-filtered; on-screen transcripts are.")


def rev_id(rid: str, n: int) -> str:
    return f"{rid}-r{n}"


def model_blob_path(uid: str, rev: str) -> str:
    return f"workspaces/{uid}/revisions/{rev}/model.json"


def gather_ledger(ctx: PhaseContext) -> list[LedgerEntry]:
    ctx.events.flush()
    store = ctx.deps.store
    attempts = {d["id"]: d.get("attempt") for d in store.list_docs(f"{ctx.run_path}/steps")}
    seen, out = set(), []
    for e in store.list_docs(f"{ctx.run_path}/events"):
        if e.get("kind") != "ledger" or attempts.get(e.get("step")) != e.get("attempt"):
            continue
        entry = LedgerEntry.model_validate(e["payload"]["entry"])
        if entry.text not in seen:
            seen.add(entry.text)
            out.append(entry)
    return out


def build_revision(ctx: PhaseContext, n: int, parent: str | None, model: DesignModel, findings: list[Finding],
                   summary: str) -> tuple[Revision, list[tuple[str, dict]]]:
    rid = rev_id(ctx.rid, n)
    ctx.deps.blobs.put(model_blob_path(ctx.uid, rid), model.model_dump_json().encode("utf-8"), "application/json")
    counts = {s: sum(f.status == s for f in findings) for s in ("pass", "fail", "warn", "n/a")}
    ledger = gather_ledger(ctx) + [LedgerEntry(kind="not_checked", agent="checker", text=t)
                                   for t in ctx.deps.engine.ledger_not_checked()] + [LIVE_AUDIO_NOTE]
    rev = Revision(id=rid, project_id=ctx.run().get("project_id", "hall-b"), parent=parent, author="Kirchhoff agents",
                   hash=ctx.deps.engine.model_hash(model), model=None, model_url=f"revisions/{rid}/model.json",
                   summary=summary, check_summary=counts, status="checked", ledger=ledger, created_at=ctx.deps.clock())
    docs = [(f"{ctx.ws_path}/revisions/{rid}", rev.model_dump(mode="json"))]
    docs += [(f"{ctx.ws_path}/revisions/{rid}/findings/{f.id}", f.model_dump(mode="json")) for f in findings]
    return rev, docs


def load_revision_model(deps: Deps, uid: str, rev_doc: dict) -> DesignModel:
    if rev_doc.get("model"):
        return DesignModel.model_validate(rev_doc["model"])
    return DesignModel.model_validate_json(deps.blobs.get(f"workspaces/{uid}/{rev_doc['model_url']}"))


def diff_elements(old: DesignModel, new: DesignModel) -> list[str]:
    def index(m: DesignModel) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for group in (m.equipment, m.connections, m.pipes, m.cooling_nodes, m.racks):
            for x in group:
                out[x.id] = x.model_dump(mode="json")
        return out

    a, b = index(old), index(new)
    return sorted(k for k in a.keys() | b.keys() if a.get(k) != b.get(k))


_BOXES: dict[tuple[str, int, str], tuple[float, float, float, float] | None] = {}
_BOX_LOCK = threading.Lock()


def with_citation_boxes(findings: list[Finding], tender_pdf: Path) -> list[Finding]:
    """The engine cites (page, verbatim quote) without a box; add pdfplumber's box (cached per quote)."""
    path = Path(tender_pdf)
    want = {(r.page, r.quote) for f in findings for r in f.tender_refs if r.bbox is None and r.quote}
    if not want or not path.exists():
        return findings
    with _BOX_LOCK:
        missing = [k for k in want if (str(path), *k) not in _BOXES]
        if missing:
            with PdfText(path) as pdf:
                for page, quote in missing:
                    in_range = 1 <= page <= pdf.page_count
                    _BOXES[(str(path), page, quote)] = pdf.find_bbox(page, quote) if in_range else None
        boxes = {k: _BOXES[(str(path), *k)] for k in want}

    def boxed(r: Citation) -> Citation:
        b = boxes.get((r.page, r.quote)) if r.bbox is None and r.quote else None
        return r.model_copy(update={"bbox": b}) if b else r

    return [f.model_copy(update={"tender_refs": [boxed(r) for r in f.tender_refs]}) for f in findings]


def run_revisions(store: Store, uid: str, rid: str) -> list[dict]:
    prefix = f"{rid}-r"
    revs = [d for d in store.list_docs(f"workspaces/{uid}/revisions") if d.get("id", "").startswith(prefix)]
    return sorted(revs, key=lambda d: int(d["id"][len(prefix):]))


def latest_revision(store: Store, uid: str, rid: str) -> dict | None:
    revs = run_revisions(store, uid, rid)
    return revs[-1] if revs else None
```

`services/api/kirchhoff/agents/docs_export.py`:
```python
"""Docs exports. Wed: Exporter protocol + StubExporter. Thu (Task 18): BlobExporter (reportlab PDF + BOQ CSV)."""
from typing import Protocol

from kirchhoff.contracts import DesignBrief, Finding, PRLine, Revision, TopologyOption

SECTIONS = ["summary", "requirements", "options", "findings", "fixes", "ledger", "boq"]


class Exporter(Protocol):
    def export(self, *, uid: str, rev: Revision, findings: list[Finding], fixes: list[Finding],
               brief: DesignBrief | None, options: list[TopologyOption], pr_lines: list[PRLine], order: list[str],
               summary: str) -> list[dict]: ...


class StubExporter:
    def export(self, **_: object) -> list[dict]:
        return [{"name": "calc-report.pdf", "path": None, "status": "pending"},
                {"name": "boq.csv", "path": None, "status": "pending"}]
```

- [ ] **Step 4: Implement P3**

`services/api/kirchhoff/runs/phase3.py`:
```python
"""P3: select → route → clashes → BOQ → Checker → fix loop (≤ 2, one revision each) → Docs → REVIEW GATE."""
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel

from kirchhoff.agents.docs_export import SECTIONS, StubExporter
from kirchhoff.agents.specs import COOLING, DOCS, LAYOUT, POWER
from kirchhoff.agents.trust import sanitize
from kirchhoff.contracts import DesignBrief, DesignModel, Finding, PRLine, Revision, TopologyOption

from .policy import OWNER, choose_option, criterion, lead_limit_weeks, preferred_candidate
from .revisions import build_revision, diff_elements, load_revision_model, run_revisions, with_citation_boxes
from .steps import AGENT_LABEL, ParkAtGate, PhaseContext, PhaseOutcome, StepOutput, run_step

MAX_FIX_ITERATIONS = 2
S_SELECT, S_ROUTE, S_CLASH, S_BOQ, S_DOCS = "p3.select_option", "p3.route", "p3.clashes", "p3.boq", "p3.docs"


class FixChoice(BaseModel):
    candidate_id: str
    reason: str = ""


class DocsReply(BaseModel):
    order: list[str] = []
    summary: str = ""


def run_p3(ctx: PhaseContext) -> PhaseOutcome:
    sel = run_step(ctx, S_SELECT, lambda: _select(ctx))["option_id"]
    model = DesignModel.model_validate(run_step(ctx, S_ROUTE, lambda: _route(ctx, sel))["model"])
    run_step(ctx, S_CLASH, lambda: _clashes(ctx, model))
    lines = run_step(ctx, S_BOQ, lambda: _boq(ctx, model))["pr_lines"]
    chk = run_step(ctx, "p3.check.1", lambda: _check(ctx, 1, None, model, None, lines))
    n = 1
    while chk["fail_ids"] and n <= MAX_FIX_ITERATIONS:
        fix = run_step(ctx, f"p3.fix.{n}", lambda: _fix(ctx, n, chk["rev"], chk["fail_ids"]))
        if not fix["applied"]:
            break
        new_model = DesignModel.model_validate(fix["model"])
        chk = run_step(ctx, f"p3.check.{n + 1}", lambda: _check(ctx, n + 1, chk["rev"], new_model, model, None))
        model, n = new_model, n + 1
    run_step(ctx, S_DOCS, lambda: _docs(ctx, chk))
    return PhaseOutcome(gate="review", run_patch={"selected_option": sel})


def _select(ctx: PhaseContext) -> StepOutput:
    run = ctx.run()
    if run.get("selected_option"):
        return StepOutput(data={"option_id": run["selected_option"], "auto": False})
    options = [TopologyOption.model_validate(o) for o in run.get("options", [])]
    limit = lead_limit_weeks(ctx.scenario())
    opt = choose_option(options, ctx.outputs("p2.resolve_plan")["resolutions"], limit)
    if opt is None:
        raise ParkAtGate("option", "No option meets the resolved clauses with zero single points of failure and "
                                   "every lead time within the limit; choose one.")
    why = (f"Auto mode chose {opt.id}: it meets the resolved clauses with zero single points of failure and every "
           f"lead time within {limit} weeks, at the lowest cost.")
    res = ctx.agent(POWER, S_SELECT, f"{why} Explain this choice to the engineer in one sentence.")
    ctx.narrate(S_SELECT, "power", res.text if res else "", ctx.allowed(extra=[o.id for o in options]),
                "option selection", template=why)
    ctx.ledger(S_SELECT, "orchestrator", "did", why)
    ctx.deps.store.update_doc(ctx.run_path, {"selected_option": opt.id})
    return StepOutput(data={"option_id": opt.id, "auto": True})


def _route(ctx: PhaseContext, option_id: str) -> StepOutput:
    item = next(i for i in ctx.outputs("p2.annotate_options")["options"] if i["option"]["id"] == option_id)
    base, scn, box = DesignModel.model_validate(item["model"]), ctx.scenario(), {}

    def route_busways() -> dict:
        """Route feeders and row busways (and the default pipes) with the engine's default candidate routes."""
        box["model"] = ctx.deps.engine.route(scn, base)
        m = box["model"]
        return {"feeders": sorted(c.id for c in m.connections if c.kind != "internal" and c.route),
                "routed": sum(1 for c in m.connections if c.route)}

    tool = ctx.tool(S_ROUTE, "layout", route_busways)
    res = ctx.agent(LAYOUT, S_ROUTE, "Route the busways, then narrate the result.", tools=[tool])
    if "model" not in box:
        tool()
    m = box["model"]
    ctx.narrate(S_ROUTE, "layout", res.text if res else "", ctx.allowed(m), "busway routing")
    ctx.emit(S_ROUTE, "cooling", "tool_result", "route_pipes done",
             payload={"tool": "route_pipes", "summary": {"pipes": {p.id: p.tier for p in m.pipes}}})
    ctx.emit(S_ROUTE, "cooling", "message", f"Cooling routed {len(m.pipes)} headers and branches on the pipe tiers")
    return StepOutput(data={"model": m.model_dump(mode="json")})


def _clashes(ctx: PhaseContext, model: DesignModel) -> StepOutput:
    def detect_clashes() -> dict:
        """Detect solid intersections between routed elements."""
        rep = ctx.deps.engine.detect_clashes(model)
        return {"count": len(rep.clashes), "clashes": rep.clashes[:20]}

    summary = ctx.tool(S_CLASH, "layout", detect_clashes)()
    ctx.emit(S_CLASH, "layout", "message", f"{summary['count']} solid clashes found")
    return StepOutput(data=summary)


def _boq(ctx: PhaseContext, model: DesignModel) -> StepOutput:
    box = {}

    def derive_pr_lines() -> dict:
        """Derive the BOQ and draft purchase-requisition lines from the model."""
        box["lines"] = ctx.deps.engine.derive_pr_lines(ctx.scenario(), model, ctx.erp())
        return {"lines": len(box["lines"]),
                "total_usd": round(sum(x.qty * x.unit_price for x in box["lines"]), 2)}

    ctx.tool(S_BOQ, "procurement", derive_pr_lines)()
    return StepOutput(data={"pr_lines": [x.model_dump(mode="json") for x in box["lines"]]})


def _check(ctx: PhaseContext, n: int, parent: str | None, model: DesignModel, parent_model: DesignModel | None,
           lines: list[dict] | None) -> StepOutput:
    step, scn, erp, box = f"p3.check.{n}", ctx.scenario(), ctx.erp(), {}
    pr = ([PRLine.model_validate(x) for x in lines] if lines is not None
          else ctx.deps.engine.derive_pr_lines(scn, model, erp))

    def run_rule_pack() -> dict:
        """Run the deterministic rule pack R01 to R15 (incl. R04b) on the revision."""
        box["findings"] = ctx.deps.engine.check(scn, model, erp, pr_lines=pr)
        fs = box["findings"]
        return {"checks": len(fs), **{s: sum(f.status == s for f in fs) for s in ("pass", "fail", "warn", "n/a")}}

    summary = ctx.tool(step, "checker", run_rule_pack)()
    findings = with_citation_boxes(box["findings"], ctx.deps.inputs().tender_pdf)
    fails = [f for f in findings if f.status == "fail"]
    rev, docs = build_revision(ctx, n, parent, model, findings,
                               f"{summary['checks']} checks, {summary['fail']} failing")
    # WS3 ruling R8: the revision artifact comes before its finding events, and each finding names its revision.
    ctx.emit(step, "checker", "artifact", f"Revision {rev.id} checked",
             payload={"type": "revision", "ref": f"{ctx.ws_path}/revisions/{rev.id}",
                      "changed": diff_elements(parent_model, model) if parent_model is not None else []})
    for f in fails:
        ctx.emit(step, "checker", "finding", f.title, detail=f"{f.rule_id} on {f.element_id}",
                 payload={"finding_id": f.id, "rule_id": f.rule_id, "element_id": f.element_id, "status": f.status,
                          "rev": rev.id})
    if not fails:
        ctx.metrics.setdefault("time_to_clean_s", ctx.active_s())
    return StepOutput(data={"rev": rev.id, "hash": rev.hash, "fail_ids": [f.id for f in fails],
                            "pr_lines": [x.model_dump(mode="json") for x in pr]}, docs=docs)


def _fix(ctx: PhaseContext, n: int, rev: str, fail_ids: list[str]) -> StepOutput:
    step, store, scn, erp = f"p3.fix.{n}", ctx.deps.store, ctx.scenario(), ctx.erp()
    model = load_revision_model(ctx.deps, ctx.uid, store.get_doc(f"{ctx.ws_path}/revisions/{rev}"))
    findings = [Finding.model_validate(store.get_doc(f"{ctx.ws_path}/revisions/{rev}/findings/{fid}"))
                for fid in fail_ids]
    allowed = ctx.allowed(model)

    def decide(f: Finding):
        owner = OWNER.get(f.rule_id, "checker")
        cands = ctx.deps.engine.fix_candidates(scn, model, f, erp)
        ctx.emit(step, owner, "tool_result", "fix_candidates done", payload={"tool": "fix_candidates", "summary": {
            "finding_id": f.id, "candidates": [{"id": c.id, "label": c.label, "cost_delta": c.cost_delta,
                                                "metrics": c.metrics} for c in cands]}})
        if not cands:
            return f, owner, None, [], None
        reply = None
        if owner in ("power", "cooling"):
            lines = "\n".join(f"- {c.id}: {c.label}; cost delta USD {c.cost_delta:,.0f}; metrics {c.metrics}"
                              for c in cands)
            msg = (f"Finding {f.id}: {f.title} on {f.element_id} (rule {f.rule_id}). Each engine candidate clears it "
                   f"without creating a new failure:\n{lines}\nChoose one by your criterion: {criterion(owner)}. "
                   'Reply with JSON {"candidate_id": id, "reason": one sentence naming the criterion}.')
            reply = ctx.agent_json(POWER if owner == "power" else COOLING, step, msg, FixChoice,
                                   key=f"{step}:{f.id}")
        chosen = next((c for c in cands if reply is not None and c.id == reply.candidate_id), None)
        reason = reply.reason if chosen is not None else None
        chosen = chosen or preferred_candidate(owner, cands)
        return f, owner, chosen, [c for c in cands if c.id != chosen.id], reason

    with ThreadPoolExecutor(4) as pool:
        decisions = list(pool.map(decide, findings))
    docs, applied = [], []
    for f, owner, chosen, rejected, reason in decisions:
        if chosen is None:
            ctx.emit(step, "checker", "status", f"No engine candidate clears {f.id}")
            continue
        template = f"{AGENT_LABEL.get(owner, owner)} chose {chosen.id} for {f.id}: {criterion(owner)}."
        text = (sanitize(reason, allowed | {chosen.id, *(c.id for c in rejected)}, template) if reason else template)
        ctx.emit(step, owner, "message", text, payload={"finding_id": f.id, "candidate": chosen.id})
        alt = preferred_candidate(owner, rejected) if rejected else None
        f2 = f.model_copy(update={
            "fix": {"candidate": chosen.id, "label": chosen.label, "reason": text, "criterion": criterion(owner),
                    "agent": owner, "cost_delta": chosen.cost_delta,
                    "deltas": {**chosen.metrics, "cost_delta": chosen.cost_delta}},
            "rejected_fix": None if alt is None else {"candidate": alt.id, "label": alt.label,
                                                      "cost_delta": alt.cost_delta,
                                                      "deltas": {**alt.metrics, "cost_delta": alt.cost_delta}}})
        docs.append((f"{ctx.ws_path}/revisions/{rev}/findings/{f.id}", f2.model_dump(mode="json")))
        model = ctx.deps.engine.apply_fix(model, chosen)
        applied.append(chosen.id)
    return StepOutput(data={"applied": applied, "model": model.model_dump(mode="json")}, docs=docs)


def _docs(ctx: PhaseContext, chk: dict) -> StepOutput:
    store, ws = ctx.deps.store, ctx.ws_path
    rev_doc = store.get_doc(f"{ws}/revisions/{chk['rev']}")
    rev, model = Revision.model_validate(rev_doc), load_revision_model(ctx.deps, ctx.uid, rev_doc)
    findings = [Finding.model_validate(d) for d in store.list_docs(f"{ws}/revisions/{rev.id}/findings")]
    fixes = [Finding.model_validate(d) for r in run_revisions(store, ctx.uid, ctx.rid)
             for d in store.list_docs(f"{ws}/revisions/{r['id']}/findings") if d.get("fix")]
    if chk["fail_ids"]:
        ctx.ledger(S_DOCS, "checker", "did", f"Fix loop stopped after {MAX_FIX_ITERATIONS} iterations; open findings: "
                                             f"{', '.join(chk['fail_ids'])}. Approval is disabled.")
    msg = (f"Revision {rev.id}: {len(findings)} checks, {len(chk['fail_ids'])} failing, {len(fixes)} fixes applied. "
           f"Report sections: {', '.join(SECTIONS)}. "
           'Reply with JSON {"order": [section ids], "summary": one sentence for the review page}.')
    reply = ctx.agent_json(DOCS, S_DOCS, msg, DocsReply)
    order = [x for x in (reply.order if reply else []) if x in SECTIONS]
    order += [x for x in SECTIONS if x not in order]
    summary = ctx.narrate(S_DOCS, "docs", reply.summary if reply else "", ctx.allowed(model), "the calc report",
                          template=f"Docs prepared the calc report and BOQ for {rev.id}.")
    files = (ctx.deps.exporter or StubExporter()).export(
        uid=ctx.uid, rev=rev, findings=findings, fixes=fixes,
        brief=DesignBrief.model_validate(ctx.outputs("p1.intake")["brief"]),
        options=[TopologyOption.model_validate(o) for o in ctx.run().get("options", [])],
        pr_lines=[PRLine.model_validate(x) for x in chk["pr_lines"]], order=order, summary=summary)
    for f in files:
        if f.get("path"):  # storage path, served by GET /api/files/{path}
            ctx.emit(S_DOCS, "docs", "artifact", f"{f['name']} {f['status']}",
                     payload={"type": "export", "ref": f["path"], "name": f["name"], "status": f["status"]})
        else:
            ctx.emit(S_DOCS, "docs", "status", f"{f['name']} {f['status']}")
    return StepOutput(data={"rev": rev.id, "order": order, "summary": summary, "files": files})
```

- [ ] **Step 5: Run tests**

Run: `cd services/api && uv run pytest tests/runs -q`
Expected: all runs tests pass (`41 passed, 1 skipped`).

- [ ] **Step 6: Commit**

```bash
git add services/api/kirchhoff/runs services/api/kirchhoff/agents/docs_export.py services/api/tests/runs
git commit -m "feat(runs): P3 routing, checker, revisions with hashes + ledger, fix loop with criteria, docs stub

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 14: Review gate and P4 — sign, PRs via the enterprise client, R12 on submitted PRs, CRM overlay, audit; full live run (Wed 15)

**Files:**
- Create: `services/api/kirchhoff/runs/phase4.py`
- Modify: `services/api/kirchhoff/api/runs_routes.py` (review gate)
- Test: `services/api/tests/api/test_api_flow.py`, `services/api/tests/api/test_api_live_full.py`

**Interfaces:**
- Consumes: `EnterpriseClient`, `HALL_B_OPPORTUNITY_ID`, `STAGE_DESIGN_APPROVED` (Task 7; WS4 implements the client); `latest_revision`, `load_revision_model` (Task 13); `ensure_gate`, `resume_from_gate` (Task 10); the engine facade `derive_pr_lines` and `check(..., pr_lines=submitted)`.
- Produces:
  - `POST /api/runs/{rid}/gates/review {decision, comment}` → 202 `{ok}`. Errors: 409 `wrong_state`, `gate_expired` or `open_findings` (approve while the latest revision has fails); 404 for a missing run. It writes `approvals/{aid}` as `Approval(revision=<latest rev>, approver_name="You (Demo Reviewer)", role="Reviewer")`. Approved: the revision `status` becomes `signed` and P4 starts. Rejected: the run becomes `done` (R17).
  - `phase4.run_p4(ctx) -> PhaseOutcome(gate=None, metrics={"prs", "p4_blocked"})`. Steps: `p4.sign` (audit ledger), `p4.create_prs` (one PR per ERP vendor through `enterprise.create_pr(..., idempotency_key=f"{rid}:{rev}:{vendor}")`, mirrored to `workspaces/{uid}/prs/{prid}`), `p4.r12_recheck` (on failure: PRs `blocked` in the sandbox and the mirror, finding `R12:submitted-prs`, audit ledger; spec §6.2), `p4.crm` (only if not blocked: `set_opportunity_stage(uid, "opp-hall-b", "Design approved")`, mirrored to `workspaces/{uid}/crm/opp-hall-b`) and `p4.audit`.

- [ ] **Step 1: Write the failing flow tests**

`services/api/tests/api/test_api_flow.py`:
```python
from kirchhoff.runs.fakes import FakeEngine, FakeEnterprise
from kirchhoff.runs.leases import run_path
from kirchhoff.runs.revisions import latest_revision

NEW = {"project_id": "hall-b", "autonomy": "ask"}


def _run(d, rid):
    return d.store.get_doc(run_path("u1", rid))


def _ask_to_review(client, auth) -> str:
    rid = client.post("/api/runs", json=NEW, headers=auth).json()["run_id"]
    assert client.post(f"/api/runs/{rid}/gates/plan", json={"answers": {"Q-redundancy": "2N"}},
                       headers=auth).status_code == 202
    assert client.post(f"/api/runs/{rid}/gates/option", json={"option_id": "2N"}, headers=auth).status_code == 202
    return rid


def _review(client, auth, rid, decision="approved"):
    return client.post(f"/api/runs/{rid}/gates/review", json={"decision": decision, "comment": "ok"}, headers=auth)


def test_full_ask_flow_signs_creates_prs_and_moves_crm(client, deps, auth, firestore_safe):
    rid = _ask_to_review(client, auth)
    assert _run(deps, rid)["gate"] == "review"
    assert _review(client, auth, rid).status_code == 202
    run = _run(deps, rid)
    assert run["status"] == "done" and run["metrics"]["p4_blocked"] == 0.0
    rev = latest_revision(deps.store, "u1", rid)
    assert rev["status"] == "signed"
    (appr,) = deps.store.list_docs("workspaces/u1/approvals")
    assert (appr["revision"], appr["approver_name"], appr["decision"]) == (rev["id"], "You (Demo Reviewer)", "approved")
    prs = deps.store.list_docs("workspaces/u1/prs")
    assert prs and all(p["status"] == "submitted" and p["revision"] == rev["id"] for p in prs)
    vendors = {deps.erp().get(line["material_id"]).vendor for p in prs for line in p["lines"]}
    assert len(prs) == len(vendors)
    assert deps.store.get_doc("workspaces/u1/crm/opp-hall-b")["stage"] == "Design approved"
    events = deps.store.list_docs(f"{run_path('u1', rid)}/events")
    assert [e["seq"] for e in events] == list(range(1, len(events) + 1))
    assert any(e["kind"] == "ledger" and e["title"].startswith("Approval ") for e in events)
    firestore_safe(deps.store)


def test_auto_flow_waits_only_at_review(client, deps, auth):
    rid = client.post("/api/runs", json={"project_id": "hall-b", "autonomy": "auto"}, headers=auth).json()["run_id"]
    run = _run(deps, rid)
    assert (run["status"], run["gate"], run["selected_option"]) == ("at_gate", "review", "2N")
    assert _review(client, auth, rid).status_code == 202 and _run(deps, rid)["status"] == "done"


def test_reject_ends_the_run_without_p4(client, deps, auth):
    rid = _ask_to_review(client, auth)
    assert _review(client, auth, rid, "rejected").status_code == 202
    run = _run(deps, rid)
    assert (run["status"], run["gate"]) == ("done", None)
    assert deps.store.list_docs("workspaces/u1/prs") == []
    assert latest_revision(deps.store, "u1", rid)["status"] == "checked"


class NoFixEngine(FakeEngine):
    def apply_fix(self, model, candidate):
        return model


def test_approve_is_blocked_while_findings_are_open(client, deps, auth):
    deps.engine = NoFixEngine()
    rid = _ask_to_review(client, auth)
    r = _review(client, auth, rid)
    assert r.status_code == 409 and r.json() == {"detail": "open_findings"}
    assert deps.store.list_docs("workspaces/u1/approvals") == []


class LossyEnterprise(FakeEnterprise):
    """The sandbox changes quantities on submission, so R12 fails on the submitted PRs."""

    def create_pr(self, uid, project_id, revision, lines, idempotency_key):
        trimmed = [line.model_copy(update={"qty": max(0, line.qty - 1)}) for line in lines]
        return super().create_pr(uid, project_id, revision, trimmed, idempotency_key)


def test_r12_failure_blocks_submitted_prs(client, deps, auth):
    deps.enterprise = LossyEnterprise()
    rid = _ask_to_review(client, auth)
    assert _review(client, auth, rid).status_code == 202
    run = _run(deps, rid)
    assert run["status"] == "done" and run["metrics"]["p4_blocked"] == 1.0
    assert all(p["status"] == "blocked" for p in deps.store.list_docs("workspaces/u1/prs"))
    assert all(p.status == "blocked" for p in deps.enterprise.prs.values())
    rev = latest_revision(deps.store, "u1", rid)
    assert rev["status"] == "signed"
    assert deps.store.get_doc(f"workspaces/u1/revisions/{rev['id']}/findings/R12:submitted-prs")["status"] == "fail"
    (ev,) = [e for e in deps.store.list_docs(f"{run_path('u1', rid)}/events") if e["kind"] == "finding"
             and e["step"] == "p4.r12_recheck"]
    assert ev["payload"]["rev"] == rev["id"]
    assert deps.store.get_doc("workspaces/u1/crm/opp-hall-b") is None


def test_review_requires_the_review_gate(client, deps, auth):
    rid = client.post("/api/runs", json=NEW, headers=auth).json()["run_id"]
    r = _review(client, auth, rid)
    assert r.status_code == 409 and r.json() == {"detail": "wrong_state"}
```

`services/api/tests/api/test_api_live_full.py`:
```python
import importlib.util
import json
import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytestmark = [pytest.mark.live,
              pytest.mark.skipif(os.environ.get("KIRCHHOFF_LIVE") != "1", reason="set KIRCHHOFF_LIVE=1"),
              pytest.mark.skipif(importlib.util.find_spec("kirchhoff.engine") is None
                                 or importlib.util.find_spec("kirchhoff.engine.api") is None,
                                 reason="WS1 engine not landed")]
REPO = Path(__file__).resolve().parents[4]


def test_live_full_run_on_hall_b(tmp_path):
    import kirchhoff.engine.api as engine
    from kirchhoff.agents.adk_runner import AdkRunner
    from kirchhoff.agents.ports import load_erp_seed
    from kirchhoff.api.app import create_app
    from kirchhoff.runs.fakes import FakeEnterprise, build_fake_deps
    from kirchhoff.runs.revisions import run_revisions
    from kirchhoff.store.memory import MemoryStore

    scen = REPO / "scenarios"
    deps = build_fake_deps(MemoryStore(), scen, seed_dir=tmp_path, spawn=lambda fn: fn(), heartbeat_s=3600.0,
                           engine=engine, runner=AdkRunner(),
                           enterprise=FakeEnterprise(load_erp_seed(scen / "hall_a" / "erp_seed.yaml")))
    client, auth = TestClient(create_app(deps=deps, verify_token=lambda t: "u1")), {"Authorization": "Bearer t"}
    t0 = time.monotonic()
    rid = client.post("/api/runs", json={"project_id": "hall-b", "autonomy": "auto"}, headers=auth).json()["run_id"]
    run = deps.store.get_doc(f"workspaces/u1/runs/{rid}")
    assert (run["status"], run["gate"], run["selected_option"]) == ("at_gate", "review", "2N"), run
    revs = run_revisions(deps.store, "u1", rid)
    first = {f["id"] for f in deps.store.list_docs(f"workspaces/u1/revisions/{revs[0]['id']}/findings")
             if f["status"] == "fail"}
    assert first == {"R05:FA-01", "R11:H-Z2"}  # spec §9.6 golden first pass
    assert revs[-1]["check_summary"]["fail"] == 0 and len(revs) <= 3
    assert client.post(f"/api/runs/{rid}/gates/review", json={"decision": "approved"}, headers=auth).status_code == 202
    run = deps.store.get_doc(f"workspaces/u1/runs/{rid}")
    assert run["status"] == "done" and run["metrics"]["p4_blocked"] == 0.0
    print(json.dumps({"elapsed_s": round(time.monotonic() - t0, 1), **{k: run["metrics"].get(k) for k in
                      ("time_to_clean_s", "tokens_in", "tokens_out", "quotes_verified", "quotes_total")}}))
```

- [ ] **Step 2: Run to verify failure**

Run: `cd services/api && uv run pytest tests/api/test_api_flow.py -q`
Expected: FAIL. The review POST returns 404 (no route), and once the route exists, P4 fails with `ModuleNotFoundError: No module named 'kirchhoff.runs.phase4'`.

- [ ] **Step 3: Implement P4**

`services/api/kirchhoff/runs/phase4.py`:
```python
"""P4 (on approval): sign → PRs via the enterprise client → R12 on submitted PRs → CRM stage → audit (spec §6.2)."""
from collections import defaultdict

from kirchhoff.agents.ports import HALL_B_OPPORTUNITY_ID, STAGE_DESIGN_APPROVED
from kirchhoff.contracts import Approval, PurchaseRequisition

from .revisions import latest_revision, load_revision_model
from .steps import PhaseContext, PhaseOutcome, StepOutput, run_step

S_SIGN, S_PRS, S_R12, S_CRM, S_AUDIT = "p4.sign", "p4.create_prs", "p4.r12_recheck", "p4.crm", "p4.audit"


def run_p4(ctx: PhaseContext) -> PhaseOutcome:
    sign = run_step(ctx, S_SIGN, lambda: _sign(ctx))
    prs = run_step(ctx, S_PRS, lambda: _create_prs(ctx, sign))["prs"]
    blocked = run_step(ctx, S_R12, lambda: _r12(ctx, sign, prs))["blocked"]
    if not blocked:
        run_step(ctx, S_CRM, lambda: _crm(ctx))
    run_step(ctx, S_AUDIT, lambda: _audit(ctx, sign, prs, blocked))
    return PhaseOutcome(gate=None, metrics={"prs": float(len(prs)), "p4_blocked": float(blocked)})


def _model(ctx: PhaseContext, rev: str):
    return load_revision_model(ctx.deps, ctx.uid, ctx.deps.store.get_doc(f"{ctx.ws_path}/revisions/{rev}"))


def _sign(ctx: PhaseContext) -> StepOutput:
    rev = latest_revision(ctx.deps.store, ctx.uid, ctx.rid)
    approvals = [Approval.model_validate(a) for a in ctx.deps.store.list_docs(f"{ctx.ws_path}/approvals")
                 if a.get("revision") == rev["id"] and a.get("decision") == "approved"]
    appr = max(approvals, key=lambda a: a.ts)
    ctx.ledger(S_SIGN, "system", "did",
               f"{rev['id']} signed by {appr.approver_name} ({appr.role}); hash {rev['hash'][:12]}")
    return StepOutput(data={"rev": rev["id"], "hash": rev["hash"], "approval_id": appr.id})


def _create_prs(ctx: PhaseContext, sign: dict) -> StepOutput:
    scn, erp = ctx.scenario(), ctx.erp()
    lines = ctx.deps.engine.derive_pr_lines(scn, _model(ctx, sign["rev"]), erp)
    by_vendor = defaultdict(list)
    for line in lines:
        by_vendor[erp.get(line.material_id).vendor].append(line)
    project_id, prs = ctx.run().get("project_id", "hall-b"), []

    def erp_create_pr(vendor: str) -> dict:
        """Submit one purchase requisition per vendor to the ERP sandbox."""
        pr = ctx.deps.enterprise.create_pr(ctx.uid, project_id, sign["rev"], by_vendor[vendor],
                                           idempotency_key=f"{ctx.rid}:{sign['rev']}:{vendor}")
        prs.append(pr)
        return {"pr_id": pr.id, "lines": len(pr.lines), "status": pr.status}

    tool = ctx.tool(S_PRS, "procurement", erp_create_pr)
    for vendor in sorted(by_vendor):
        tool(vendor=vendor)
    ctx.emit(S_PRS, "procurement", "message", f"Procurement submitted {len(prs)} purchase requisitions to the ERP")
    return StepOutput(data={"prs": [pr.model_dump(mode="json") for pr in prs]},
                      docs=[(f"{ctx.ws_path}/prs/{pr.id}", pr.model_dump(mode="json")) for pr in prs])


def _r12(ctx: PhaseContext, sign: dict, prs: list[dict]) -> StepOutput:
    scn, erp, box = ctx.scenario(), ctx.erp(), {}
    submitted = [PurchaseRequisition.model_validate(p) for p in prs]
    lines = [line for pr in submitted for line in pr.lines]
    model = _model(ctx, sign["rev"])

    def check_submitted_prs() -> dict:
        """Re-run R12 (SLD = BOQ = PR lines) against the submitted purchase requisitions."""
        box["r12"] = [f for f in ctx.deps.engine.check(scn, model, erp, pr_lines=lines) if f.rule_id == "R12"]
        return {"r12": [{"id": f.id, "status": f.status} for f in box["r12"]]}

    ctx.tool(S_R12, "checker", check_submitted_prs)()
    failed = [f for f in box["r12"] if f.status == "fail"]
    if not failed:
        ctx.emit(S_R12, "checker", "message", "R12 passes on the submitted PRs")
        return StepOutput(data={"blocked": False})
    docs = []
    for pr in submitted:
        ctx.deps.enterprise.set_pr_status(ctx.uid, pr.id, "blocked")
        docs.append((f"{ctx.ws_path}/prs/{pr.id}", pr.model_copy(update={"status": "blocked"}).model_dump(mode="json")))
    finding = failed[0].model_copy(update={"id": "R12:submitted-prs", "element_id": "submitted-prs"})
    docs.append((f"{ctx.ws_path}/revisions/{sign['rev']}/findings/{finding.id}", finding.model_dump(mode="json")))
    ctx.emit(S_R12, "checker", "finding", finding.title, detail="R12 on submitted-prs",
             payload={"finding_id": finding.id, "rule_id": "R12", "element_id": "submitted-prs", "status": "fail",
                      "rev": sign["rev"]})
    ctx.ledger(S_R12, "system", "did",
               "PR submission blocked: R12 failed on the submitted PRs; the signed revision stays signed.")
    return StepOutput(data={"blocked": True}, docs=docs)


def _crm(ctx: PhaseContext) -> StepOutput:
    box = {}

    def update_crm_opportunity() -> dict:
        """Move the Hall B opportunity to Design approved in the CRM sandbox."""
        box["ov"] = ctx.deps.enterprise.set_opportunity_stage(ctx.uid, HALL_B_OPPORTUNITY_ID, STAGE_DESIGN_APPROVED)
        return {"opportunity_id": HALL_B_OPPORTUNITY_ID, "stage": STAGE_DESIGN_APPROVED}

    ctx.tool(S_CRM, "system", update_crm_opportunity)()
    ov = box["ov"]
    ctx.emit(S_CRM, "system", "message", f"CRM opportunity moved to {ov.stage}")
    return StepOutput(data={"stage": ov.stage},
                      docs=[(f"{ctx.ws_path}/crm/{ov.opportunity_id}", ov.model_dump(mode="json"))])


def _audit(ctx: PhaseContext, sign: dict, prs: list[dict], blocked: bool) -> StepOutput:
    text = (f"Approval {sign['approval_id']} recorded for {sign['rev']} (hash {sign['hash'][:12]}); {len(prs)} PRs "
            + ("blocked by R12; CRM unchanged." if blocked else "submitted; CRM moved to Design approved."))
    ctx.ledger(S_AUDIT, "system", "did", text)
    return StepOutput(data={"text": text})
```

- [ ] **Step 4: Add the review gate route**

In `services/api/kirchhoff/api/runs_routes.py`, extend the imports:
```python
from kirchhoff.contracts import Approval, OpenQuestion, PlanStep, RunRecord, TopologyId
from kirchhoff.runs.orchestrator import (GateExpired, LeaseBusy, WrongState, ensure_gate, resume_from_gate,
                                        resume_run, start_phase)
from kirchhoff.runs.revisions import latest_revision
```
Add these module-level definitions after `OptionGate`:
```python
REVIEWER_NAME, REVIEWER_ROLE = "You (Demo Reviewer)", "Reviewer"


class ReviewGate(BaseModel):
    decision: Literal["approved", "rejected"]
    comment: str = ""
```
Add this route inside `make_router`, just before `return router`:
```python
    @router.post("/api/runs/{rid}/gates/review", status_code=202)
    def gate_review(rid: str, body: ReviewGate, uid: str = Depends(current_uid)):
        try:
            ensure_gate(deps, uid, rid, "review")
        except KeyError:
            return err(404, "run_not_found")
        except WrongState:
            return err(409, "wrong_state")
        except GateExpired:
            return err(409, "gate_expired")
        rev = latest_revision(deps.store, uid, rid)
        if rev is None:
            return err(409, "wrong_state")
        if body.decision == "approved" and (rev.get("check_summary") or {}).get("fail", 0) > 0:
            return err(409, "open_findings")
        now = deps.clock()
        appr = Approval(id=uuid.uuid4().hex[:12], revision=rev["id"], approver_name=REVIEWER_NAME, role=REVIEWER_ROLE,
                        decision=body.decision, comment=body.comment, ts=now)
        deps.store.set_doc(f"workspaces/{uid}/approvals/{appr.id}", appr.model_dump(mode="json"))
        if body.decision == "rejected":
            deps.store.update_doc(run_path(uid, rid), {"status": "done", "gate": None, "finished_at": now})
            return {"ok": True}
        deps.store.update_doc(f"workspaces/{uid}/revisions/{rev['id']}", {"status": "signed"})
        return advance(uid, rid, "review", {})
```

- [ ] **Step 5: Run the whole suite**

Run: `cd services/api && uv run pytest -q`
Expected: everything passes (live tests skipped).

- [ ] **Step 6: Full live P1–P4 run (Wed, once WS1's facade is on the branch)**

Run: `cd services/api && KIRCHHOFF_LIVE=1 GOOGLE_GENAI_USE_VERTEXAI=true GOOGLE_CLOUD_PROJECT=ordinal-mep GOOGLE_CLOUD_QUOTA_PROJECT=ordinal-mep GOOGLE_CLOUD_LOCATION=global uv run pytest tests/api/test_api_live_full.py -v -s`
Expected: 1 passed, plus a JSON line with `elapsed_s`, `time_to_clean_s` and token counts; keep it for the spec §4 metrics. If the first revision does not fail exactly `{R05:FA-01, R11:H-Z2}`, stop and report it to the controller (an engine regression, not WS2's to patch). After WS4 deploys, do one Hall B run from the deployed UI, Ask mode, through all gates.

- [ ] **Step 7: Commit**

```bash
git add services/api/kirchhoff/runs/phase4.py services/api/kirchhoff/api/runs_routes.py services/api/tests/api
git commit -m "feat(runs): review gate, P4 PRs via enterprise client, R12 on submitted PRs, CRM overlay, audit

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 15: Co-pilot — `/api/what-if` and `/api/explain` on workspace and seed revisions (Thu 16)

**Files:**
- Create: `services/api/kirchhoff/agents/copilot.py`, `services/api/kirchhoff/api/copilot_routes.py`
- Modify: `services/api/kirchhoff/api/app.py` (include the router), `services/api/tests/api/conftest.py` (append the `seeded` fixture)
- Test: `services/api/tests/api/test_api_copilot.py`

**Interfaces:**
- Consumes: `load_revision_model` (Task 13); `COPILOT` (Task 5); `sanitize`, `fill_finding`, `allowed_ids_for` (Task 4); and the engine facade `what_if(scn, model, param, value, revision_ref, erp) -> WhatIfResult` (fail/warn findings only, R24).
- Produces (`kirchhoff.agents.copilot`):
  - `RevisionNotFound(KeyError)`.
  - `call_with_timeout(fn, timeout_s)`: shared pool; raises `concurrent.futures.TimeoutError`.
  - `load_seed_bundle(seed_dir, project_id) -> ProjectBundle` (cached by mtime). **WS4:** seed bundle revisions must inline `model`.
  - `load_revision(deps, uid, ref) -> tuple[DesignModel, list[Finding]]` for `ws:{rev}` and `seed:{pid}@{rev}`; raises `ValueError` for a bad ref.
  - `explain_text(deps, model, finding) -> str`: the Gemini explanation, sanitized with the rule's template sentence (`finding.explanation`) as fallback, then `{value}`, `{limit}` and `{unit}` filled from the engine record with `fill_finding` (no doubled units with WS1's templates).
- Routes: `POST /api/what-if {revision_ref, param, value}` → `WhatIfResult` (404 `revision_not_found`, 422 `bad_revision_ref`, 504 `timeout` after 8 s). `POST /api/explain {revision_ref, finding_id}` → `{text}` (404 `finding_not_found`).

- [ ] **Step 1: Append the seed-bundle fixture and write the failing tests**

Append to `services/api/tests/api/conftest.py`:
```python
from kirchhoff.contracts import Project, ProjectBundle, Revision


@pytest.fixture
def seeded(deps):
    """Writes seed:hall-a@r1 (2 fails) and seed:hall-a@r2 (all pass) as a static ProjectBundle."""
    eng, erp, scn = deps.engine, deps.erp(), deps.scenario()
    racks = eng.place_racks(scn)
    _, model = next(p for p in eng.annotate_options(scn, eng.power_options(scn, racks), erp) if p[0].id == "2N")
    r1 = eng.route(scn, model)
    f1 = eng.check(scn, r1, erp)
    r2 = r1
    for f in [f for f in f1 if f.status == "fail"]:
        r2 = eng.apply_fix(r2, eng.fix_candidates(scn, r2, f, erp)[0])
    bundle = ProjectBundle(
        project=Project(id="hall-a", name="Deccan AI Campus · Hall A", client="Deccan Compute", asset_pack="datahall",
                        state="signed", sample=True, updated_at=0.0),
        revisions=[Revision(id="r1", project_id="hall-a", author="Priya Raman", hash=eng.model_hash(r1), model=r1,
                            status="checked", created_at=0.0),
                   Revision(id="r2", project_id="hall-a", parent="r1", author="Priya Raman", hash=eng.model_hash(r2),
                            model=r2, status="signed", created_at=0.0)],
        findings={"r1": f1, "r2": eng.check(scn, r2, erp)})
    (deps.seed_dir / "hall-a.json").write_text(bundle.model_dump_json(), encoding="utf-8")
    return deps
```

`services/api/tests/api/test_api_copilot.py`:
```python
import time

from kirchhoff.agents.copilot import load_seed_bundle
from kirchhoff.api import copilot_routes
from kirchhoff.runs.fakes import FakeEngine


def _post(client, auth, path, body):
    return client.post(path, json=body, headers=auth)


def test_what_if_on_a_seed_revision(client, seeded, auth):
    r = _post(client, auth, "/api/what-if", {"revision_ref": "seed:hall-a@r2", "param": "rack_kw", "value": 200})
    assert r.status_code == 200
    body = r.json()
    assert body["revision_ref"] == "seed:hall-a@r2" and body["impact_chain"]
    assert {"R01", "R02", "R08"} <= {f["rule_id"] for f in body["findings"] if f["status"] == "fail"}


def test_what_if_on_a_workspace_revision(client, seeded, auth):
    model = load_seed_bundle(seeded.seed_dir, "hall-a").revisions[1].model
    seeded.store.set_doc("workspaces/u1/revisions/x-r2", {"id": "x-r2", "model": None,
                                                          "model_url": "revisions/x-r2/model.json"})
    seeded.blobs.put("workspaces/u1/revisions/x-r2/model.json", model.model_dump_json().encode(), "application/json")
    r = _post(client, auth, "/api/what-if", {"revision_ref": "ws:x-r2", "param": "rack_kw", "value": 150})
    assert r.status_code == 200 and r.json()["findings"] == []


def test_what_if_errors(client, seeded, auth):
    assert _post(client, auth, "/api/what-if", {"revision_ref": "foo", "param": "rack_kw", "value": 1}).json() == \
        {"detail": "bad_revision_ref"}
    assert _post(client, auth, "/api/what-if", {"revision_ref": "seed:hall-a@r9", "param": "rack_kw",
                                                "value": 1}).status_code == 404
    assert _post(client, auth, "/api/what-if", {"revision_ref": "ws:nope", "param": "rack_kw",
                                                "value": 1}).status_code == 404
    assert _post(client, auth, "/api/what-if", {"revision_ref": "seed:hall-a@r2", "param": "voltage",
                                                "value": 1}).status_code == 422


class SlowEngine(FakeEngine):
    def what_if(self, *args, **kwargs):
        time.sleep(0.3)
        return super().what_if(*args, **kwargs)


def test_what_if_times_out(client, seeded, auth, monkeypatch):
    seeded.engine = SlowEngine()
    monkeypatch.setattr(copilot_routes, "WHAT_IF_TIMEOUT_S", 0.05)
    r = _post(client, auth, "/api/what-if", {"revision_ref": "seed:hall-a@r2", "param": "rack_kw", "value": 200})
    assert r.status_code == 504 and r.json() == {"detail": "timeout"}


def test_explain_fills_placeholders_from_the_engine_record(client, seeded, auth):
    r = _post(client, auth, "/api/explain", {"revision_ref": "seed:hall-a@r1", "finding_id": "R05:FA-01"})
    assert r.json() == {"text": "FA-01 has a voltage drop of 2.16%, above the 2% limit in §4.6. It is the longest "
                                "A-side feeder from A1."}


def test_explain_with_free_numbers_uses_the_rule_template(client, seeded, auth):
    seeded.runner.replies["copilot:explain:R05:FA-01"] = {"text": "The drop is 2.16% because it is 82 m long."}
    r = _post(client, auth, "/api/explain", {"revision_ref": "seed:hall-a@r1", "finding_id": "R05:FA-01"})
    assert r.json() == {"text": "Voltage drop: 2.16% against a limit of 2%."}


def test_explain_survives_a_model_failure(client, seeded, auth):
    seeded.runner.replies["copilot:explain:R05:FA-01"] = {"raise": "vertex down"}
    r = _post(client, auth, "/api/explain", {"revision_ref": "seed:hall-a@r1", "finding_id": "R05:FA-01"})
    assert r.json() == {"text": "Voltage drop: 2.16% against a limit of 2%."}


def test_explain_unknown_finding(client, seeded, auth):
    r = _post(client, auth, "/api/explain", {"revision_ref": "seed:hall-a@r1", "finding_id": "R99:X"})
    assert r.status_code == 404 and r.json() == {"detail": "finding_not_found"}
```

- [ ] **Step 2: Run to verify failure**

Run: `cd services/api && uv run pytest tests/api/test_api_copilot.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'kirchhoff.agents.copilot'`

- [ ] **Step 3: Implement the co-pilot core**

`services/api/kirchhoff/agents/copilot.py`:
```python
"""Co-pilot (spec §6.4, §6.5): revision loading, finding explanations, push-to-talk voice (Task 16)."""
import functools
import json
import logging
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from kirchhoff.contracts import DesignModel, Finding, ProjectBundle
from kirchhoff.runs.revisions import load_revision_model

from .specs import COPILOT
from .trust import allowed_ids_for, fill_finding, sanitize

log = logging.getLogger("kirchhoff.copilot")
_POOL = ThreadPoolExecutor(max_workers=8)
SEED_REF = re.compile(r"^seed:([a-z0-9-]+)@([A-Za-z0-9_-]+)$")
WS_REF = re.compile(r"^ws:([A-Za-z0-9_-]+)$")


class RevisionNotFound(KeyError):
    """The revision (or its seed bundle) does not exist."""


def call_with_timeout(fn: Callable[[], Any], timeout_s: float) -> Any:
    return _POOL.submit(fn).result(timeout=timeout_s)


@functools.lru_cache(maxsize=16)
def _bundle(path: str, mtime: float) -> ProjectBundle:
    return ProjectBundle.model_validate_json(Path(path).read_text(encoding="utf-8"))


def load_seed_bundle(seed_dir: Path, project_id: str) -> ProjectBundle:
    p = Path(seed_dir) / f"{project_id}.json"
    if not p.exists():
        raise RevisionNotFound(project_id)
    return _bundle(str(p), p.stat().st_mtime)


def load_revision(deps, uid: str, ref: str) -> tuple[DesignModel, list[Finding]]:
    if m := WS_REF.match(ref):
        rev = m.group(1)
        doc = deps.store.get_doc(f"workspaces/{uid}/revisions/{rev}")
        if doc is None:
            raise RevisionNotFound(ref)
        findings = [Finding.model_validate(d)
                    for d in deps.store.list_docs(f"workspaces/{uid}/revisions/{rev}/findings")]
        return load_revision_model(deps, uid, doc), findings
    if m := SEED_REF.match(ref):
        bundle = load_seed_bundle(deps.seed_dir, m.group(1))
        r = next((r for r in bundle.revisions if r.id == m.group(2)), None)
        if r is None or r.model is None:
            raise RevisionNotFound(ref)
        return r.model, list(bundle.findings.get(r.id, []))
    raise ValueError(f"bad revision_ref {ref!r}")


def explain_text(deps, model: DesignModel, finding: Finding) -> str:
    template = finding.explanation or f"{finding.title}: {{value}} against a limit of {{limit}}."
    clauses = ", ".join(c.clause for c in finding.tender_refs if c.clause) or "none"
    standards = ", ".join(f"{c.standard} {c.clause or ''}".strip() for c in finding.clause_refs) or "none"
    msg = (f"Finding {finding.id}: {finding.title}. Rule {finding.rule_id} on element {finding.element_id}; "
           f"status {finding.status}. Formula: {finding.formula or 'n/a'}. Inputs: {json.dumps(finding.inputs)}. "
           f"Tender clauses: {clauses}. Standards: {standards}. "
           "Explain why in two sentences. Write {value} and {limit} instead of any number.")
    try:
        res = call_with_timeout(lambda: deps.runner.run(COPILOT, f"explain:{finding.id}", msg), COPILOT.timeout_s + 1)
        text = sanitize(res.text, allowed_ids_for(model, extra=[finding.element_id, *deps.erp().ids()]), template)
    except Exception as exc:
        log.warning("explain fallback for %s: %r", finding.id, exc)
        text = template
    return fill_finding(text, finding.value, finding.limit, finding.unit)
```

- [ ] **Step 4: Implement the routes and include them**

`services/api/kirchhoff/api/copilot_routes.py`:
```python
from concurrent.futures import TimeoutError as FuturesTimeout
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from kirchhoff.agents.copilot import RevisionNotFound, call_with_timeout, explain_text, load_revision
from kirchhoff.runs.deps import Deps

from .errors import err

WHAT_IF_TIMEOUT_S = 8.0


class WhatIfBody(BaseModel):
    revision_ref: str
    param: Literal["rack_kw", "liquid_fraction", "dv_limit_pct", "tx_loading_cap_pct"]
    value: float


class ExplainBody(BaseModel):
    revision_ref: str
    finding_id: str


def make_router(deps: Deps, current_uid) -> APIRouter:
    router = APIRouter()

    def load(uid: str, ref: str):
        try:
            return load_revision(deps, uid, ref), None
        except RevisionNotFound:
            return None, err(404, "revision_not_found")
        except ValueError:
            return None, err(422, "bad_revision_ref")

    @router.post("/api/what-if")
    def what_if(body: WhatIfBody, uid: str = Depends(current_uid)):
        loaded, error = load(uid, body.revision_ref)
        if error:
            return error
        model, _ = loaded
        try:
            res = call_with_timeout(lambda: deps.engine.what_if(deps.scenario(), model, body.param, body.value,
                                                                body.revision_ref, deps.erp()), WHAT_IF_TIMEOUT_S)
        except FuturesTimeout:
            return err(504, "timeout")
        return res.model_dump(mode="json")

    @router.post("/api/explain")
    def explain(body: ExplainBody, uid: str = Depends(current_uid)):
        loaded, error = load(uid, body.revision_ref)
        if error:
            return error
        model, findings = loaded
        finding = next((f for f in findings if f.id == body.finding_id), None)
        if finding is None:
            return err(404, "finding_not_found")
        return {"text": explain_text(deps, model, finding)}

    return router
```

In `services/api/kirchhoff/api/app.py`, change `from . import runs_routes, workspace_routes` to `from . import copilot_routes, runs_routes, workspace_routes`, and add after the runs router include:
```python
    app.include_router(copilot_routes.make_router(deps, current_uid))
```

- [ ] **Step 5: Run tests**

Run: `cd services/api && uv run pytest tests/api -q`
Expected: all API tests pass (live skipped).

- [ ] **Step 6: Commit**

```bash
git add services/api/kirchhoff/agents/copilot.py services/api/kirchhoff/api services/api/tests/api
git commit -m "feat(copilot): what-if on ws/seed revisions and allowlisted finding explanations

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 16: `/api/voice` push-to-talk fallback (google-genai, audio input, same tools) (Thu 16)

**Files:**
- Modify: `services/api/pyproject.toml` (add `python-multipart>=0.0.20`; FastAPI needs it for `UploadFile`/`Form`. This is a shared file, so the change is one line.)
- Modify: `services/api/kirchhoff/agents/copilot.py` (append), `services/api/kirchhoff/api/copilot_routes.py` (append the route)
- Test: `services/api/tests/api/test_api_voice.py`

**Interfaces:**
- Consumes: `load_revision`, `explain_text`, `call_with_timeout`, `RevisionNotFound` (Task 15); `COPILOT_VOICE` (Task 5); `run_json`, `Attachment` (Task 5); `Deps.voice_runner` (`GenaiRunner` in production: Vertex `gemini-3.8-flash` with audio input and automatic function calling).
- Produces:
  - `WHAT_IF_PARAMS`, `VoiceReply(transcript, answer)`, `engine_summary(tool_results) -> str` (code-authored from engine records).
  - `answer_voice(deps, uid, ref, audio: bytes, mime: str) -> {"transcript", "answer", "tool_results": [{name, args, result}]}` (WS3 ruling R9: the key is `name`; a `what_if` result is a full `WhatIfResult`). The tools are `what_if(param, value)`, `explain_finding(finding_id="", element_id="")` and `focus_element(element_id)`, the same names and parameters as WS3's Live `TOOL_DECLARATIONS`. `answer` is sanitized with `engine_summary` as its template (R13). A model or JSON failure falls back to the summary; a timeout raises.
  - `POST /api/voice` (multipart: file field `audio` (`audio/webm|ogg|wav|mp4|mpeg`, ≤ 2 MB), form field `revision_ref` (default `seed:hall-a@r2`)) → 200 body. Errors: 413 `audio_too_large`, 415 `unsupported_audio`, 404 `revision_not_found`, 422 `bad_revision_ref`, 504 `timeout`. The UI speaks `answer` with browser speech synthesis and applies `focus_element` results.

- [ ] **Step 1: Add the multipart dependency**

In `services/api/pyproject.toml` `dependencies`, add the line `"python-multipart>=0.0.20",` after `"httpx>=0.28",`, then run `cd services/api && uv sync`.

- [ ] **Step 2: Write the failing tests**

`services/api/tests/api/test_api_voice.py`:
```python
from kirchhoff.agents.runner import ReplayRunner

CLIP = {"audio": ("clip.webm", b"\x1aE\xdf\xa3fake-webm-bytes", "audio/webm")}


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
```

- [ ] **Step 3: Run to verify failure**

Run: `cd services/api && uv run pytest tests/api/test_api_voice.py -q`
Expected: FAIL with 404 Not Found for `/api/voice` (route missing).

- [ ] **Step 4: Implement voice answering**

Append to `services/api/kirchhoff/agents/copilot.py`:
```python
from pydantic import BaseModel

from .runner import Attachment, run_json
from .specs import COPILOT_VOICE
from .trust import fmt_number

WHAT_IF_PARAMS = ("rack_kw", "liquid_fraction", "dv_limit_pct", "tx_loading_cap_pct")
VOICE_TIMEOUT_S = 9.0
VOICE_PROMPT = ("The attached audio is the engineer's question about the current design revision. Use the tools "
                'to answer, then reply with JSON {"transcript": the words you heard, "answer": one or two sentences}.')
NO_MATCH = "I could not match that to a design question; try a what-if chip."


class VoiceReply(BaseModel):
    transcript: str = ""
    answer: str = ""


def engine_summary(results: list[dict]) -> str:
    parts = []
    for r in results:
        if r["name"] == "what_if":
            fails = sorted({f["rule_id"] for f in r["result"]["findings"] if f["status"] == "fail"})
            head = f"With {r['args']['param']} at {fmt_number(r['args']['value'])}, "
            parts.append(head + (f"these checks fail: {', '.join(fails)}." if fails else "every check still passes."))
        elif r["name"] == "explain_finding":
            parts.append(r["result"]["text"])
        elif r["name"] == "focus_element":
            parts.append(f"Showing {r['args']['element_id']}.")
    return " ".join(parts) or NO_MATCH


def answer_voice(deps, uid: str, ref: str, audio: bytes, mime: str) -> dict:
    model, findings = load_revision(deps, uid, ref)
    scn, erp, by_id = deps.scenario(), deps.erp(), {f.id: f for f in findings}
    results: list[dict] = []

    def what_if(param: str, value: float) -> dict:
        """Re-check the current design with one input changed (loads change, equipment stays frozen).
        param is one of rack_kw, liquid_fraction, dv_limit_pct, tx_loading_cap_pct."""
        if param not in WHAT_IF_PARAMS:
            return {"error": f"param must be one of {', '.join(WHAT_IF_PARAMS)}"}
        r = deps.engine.what_if(scn, model, param, float(value), ref, erp)
        results.append({"name": "what_if", "args": {"param": param, "value": float(value)},
                        "result": r.model_dump(mode="json")})
        return {"failing_rules": sorted({f.rule_id for f in r.findings if f.status == "fail"}),
                "impact_chain": r.impact_chain[:6]}

    def explain_finding(finding_id: str = "", element_id: str = "") -> dict:
        """Explain one checker finding, given its id such as R05:FA-01, or the element id such as FA-01."""
        f = by_id.get(finding_id)
        if f is None and element_id:
            on_el = [x for x in findings if x.element_id == element_id]
            f = next((x for x in on_el if x.status == "fail"), on_el[0] if on_el else None)
        if f is None:
            return {"error": "unknown finding"}
        text = explain_text(deps, model, f)
        results.append({"name": "explain_finding", "args": {"finding_id": f.id}, "result": {"text": text}})
        return {"text": text}

    def focus_element(element_id: str) -> dict:
        """Show an element such as FA-01, H-Z2 or CDU-4 on the canvas."""
        results.append({"name": "focus_element", "args": {"element_id": element_id},
                        "result": {"focused": element_id}})
        return {"focused": element_id}

    def ask() -> VoiceReply:
        reply, _ = run_json(deps.voice_runner, COPILOT_VOICE, "voice", VOICE_PROMPT, VoiceReply,
                            tools=[what_if, explain_finding, focus_element], attachments=[Attachment(audio, mime)])
        return reply

    try:
        reply = call_with_timeout(ask, VOICE_TIMEOUT_S)
    except TimeoutError:
        raise
    except Exception as exc:  # model or JSON failure: answer from what the engine produced
        log.warning("voice fallback: %r", exc)
        reply = VoiceReply()
    answer = sanitize(reply.answer, allowed_ids_for(model, extra=[*erp.ids(), *by_id]), engine_summary(results))
    return {"transcript": reply.transcript, "answer": answer, "tool_results": results}
```
Move the new imports (`BaseModel`, `Attachment`, `run_json`, `COPILOT_VOICE`, `fmt_number`) to the import block at the top of the module. `concurrent.futures.TimeoutError` is the builtin `TimeoutError` on Python 3.11+, so `except TimeoutError: raise` lets timeouts reach the route.

- [ ] **Step 5: Add the route**

In `services/api/kirchhoff/api/copilot_routes.py`, extend the imports:
```python
from fastapi import APIRouter, Depends, File, Form, UploadFile
from starlette.concurrency import run_in_threadpool

from kirchhoff.agents.copilot import (RevisionNotFound, answer_voice, call_with_timeout, explain_text,
                                      load_revision)
```
Add these module-level constants:
```python
VOICE_MIME = {"audio/webm", "audio/ogg", "audio/wav", "audio/x-wav", "audio/mp4", "audio/mpeg"}
VOICE_MAX_BYTES = 2_000_000
```
Add this route inside `make_router`, before `return router`:
```python
    @router.post("/api/voice")
    async def voice(audio: UploadFile = File(...), revision_ref: str = Form("seed:hall-a@r2"),
                    uid: str = Depends(current_uid)):
        data = await audio.read()
        if len(data) > VOICE_MAX_BYTES:
            return err(413, "audio_too_large")
        mime = (audio.content_type or "").split(";")[0].strip().lower()
        if mime not in VOICE_MIME:
            return err(415, "unsupported_audio")
        try:
            return await run_in_threadpool(answer_voice, deps, uid, revision_ref, data, mime)
        except RevisionNotFound:
            return err(404, "revision_not_found")
        except ValueError:
            return err(422, "bad_revision_ref")
        except FuturesTimeout:
            return err(504, "timeout")
```

- [ ] **Step 6: Run tests**

Run: `cd services/api && uv run pytest tests/api -q`
Expected: all API tests pass.

- [ ] **Step 7: Live check of audio input (one call)**

Record a 3-second clip saying "What if racks go to two hundred kilowatts?" as `/tmp/q.webm` (any recorder; `ffmpeg -f avfoundation -i ":0" -t 3 /tmp/q.webm` on macOS). Then run:
```bash
cd services/api && GOOGLE_GENAI_USE_VERTEXAI=true GOOGLE_CLOUD_PROJECT=ordinal-mep GOOGLE_CLOUD_QUOTA_PROJECT=ordinal-mep GOOGLE_CLOUD_LOCATION=global uv run python - <<'EOF'
from kirchhoff.agents.genai_runner import GenaiRunner
from kirchhoff.agents.runner import Attachment, AgentSpec
spec = AgentSpec("copilot", "Transcribe the question, then answer in one sentence.", timeout_s=20)
print(GenaiRunner().run(spec, "voice", "What was asked?", attachments=[Attachment(open("/tmp/q.webm", "rb").read(), "audio/webm")]).text)
EOF
```
Expected: a transcript that mentions racks and two hundred. If Vertex rejects `audio/webm`, have the UI record `audio/ogg` or `audio/wav` (tell WS3) and drop `audio/webm` from `VOICE_MIME`.

- [ ] **Step 8: Commit**

```bash
git add services/api/pyproject.toml services/api/uv.lock services/api/kirchhoff/agents/copilot.py services/api/kirchhoff/api/copilot_routes.py services/api/tests/api/test_api_voice.py
git commit -m "feat(copilot): /api/voice push-to-talk with what_if/explain_finding/focus_element tools

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 17: Asset agent — `/api/asset/{pack}` for grid and solar (Thu 16)

**Files:**
- Create: `services/api/kirchhoff/agents/asset.py`, `services/api/kirchhoff/api/asset_routes.py`
- Modify: `services/api/kirchhoff/api/app.py` (include the router)
- Test: `services/api/tests/api/test_api_asset.py`

**Interfaces:**
- Consumes: `Deps.asset_engines` (`{"grid": evaluate_grid, "solar": evaluate_solar}`; WS1's `kirchhoff/engine/grid.py` and `solar.py` return `{"options": [...], "recommended": str, "findings": list[Finding], "geometry": {...}}`. **WS1:** every option dict has an `"id"`). Also `ASSET` (Task 5), `run_json`, `sanitize`, and `call_with_timeout` (Task 15).
- Produces:
  - `AssetChoice(option, reason)` and `run_asset_pack(deps, pack) -> dict`: the engine result, plus `findings` serialized and `choice = {"option", "reason", "source": "agent" | "engine"}`. The agent may only pick an engine option id; otherwise the engine's `recommended` is kept with a template reason. The reason is sanitized with the option ids and finding element ids allowlisted.
  - `POST /api/asset/{pack}` with `pack ∈ {grid, solar}` → the dict above. Errors: 404 `unknown_pack`, 504 `timeout` after 9.5 s. Agent timeout is 5 s (spec §6.1 thinking level low).

- [ ] **Step 1: Write the failing tests**

`services/api/tests/api/test_api_asset.py`:
```python
import time

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
```

- [ ] **Step 2: Run to verify failure**

Run: `cd services/api && uv run pytest tests/api/test_api_asset.py -q`
Expected: FAIL with `ImportError: cannot import name 'asset_routes'`

- [ ] **Step 3: Implement**

`services/api/kirchhoff/agents/asset.py`:
```python
"""Asset agent (spec §10): chooses one engine option for the grid or solar pack and gives a reason."""
import json
import logging

from pydantic import BaseModel

from .copilot import call_with_timeout
from .runner import run_json
from .specs import ASSET
from .trust import sanitize

log = logging.getLogger("kirchhoff.asset")


class AssetChoice(BaseModel):
    option: str
    reason: str = ""


def _dump(f):
    return f.model_dump(mode="json") if hasattr(f, "model_dump") else f


def run_asset_pack(deps, pack: str) -> dict:
    result = deps.asset_engines[pack](deps.scenarios_dir / pack)
    options = result.get("options", [])
    ids = [str(o.get("id")) for o in options]
    findings = [_dump(f) for f in result.get("findings", [])]
    rec = result.get("recommended")
    choice = {"option": rec, "reason": f"Kept the engine recommendation {rec}.", "source": "engine"}
    msg = (f"Asset pack: {pack}. Engine options (JSON): {json.dumps(options, default=str)[:6000]}. "
           f"Engine recommendation: {rec}. Choose one option id. "
           'Reply with JSON {"option": id, "reason": one sentence}.')
    try:
        reply = call_with_timeout(lambda: run_json(deps.runner, ASSET, pack, msg, AssetChoice)[0], ASSET.timeout_s)
        if reply.option in ids:
            allowed = set(ids) | {f.get("element_id") for f in findings if f.get("element_id")}
            choice = {"option": reply.option, "source": "agent",
                      "reason": sanitize(reply.reason, allowed, f"Recommended {reply.option} on the engine's ranking.")}
    except Exception as exc:
        log.warning("asset agent fallback for %s: %r", pack, exc)
    return {**result, "findings": findings, "choice": choice}
```

`services/api/kirchhoff/api/asset_routes.py`:
```python
from concurrent.futures import TimeoutError as FuturesTimeout

from fastapi import APIRouter, Depends

from kirchhoff.agents.asset import run_asset_pack
from kirchhoff.agents.copilot import call_with_timeout
from kirchhoff.runs.deps import Deps

from .errors import err

ASSET_TIMEOUT_S = 9.5
PACKS = ("grid", "solar")


def make_router(deps: Deps, current_uid) -> APIRouter:
    router = APIRouter()

    @router.post("/api/asset/{pack}")
    def asset(pack: str, uid: str = Depends(current_uid)):
        if pack not in PACKS or pack not in deps.asset_engines:
            return err(404, "unknown_pack")
        try:
            return call_with_timeout(lambda: run_asset_pack(deps, pack), ASSET_TIMEOUT_S)
        except FuturesTimeout:
            return err(504, "timeout")

    return router
```

In `services/api/kirchhoff/api/app.py`, add `asset_routes` to the `from . import ...` line and include the router after the copilot router:
```python
    app.include_router(asset_routes.make_router(deps, current_uid))
```

- [ ] **Step 4: Run tests**

Run: `cd services/api && uv run pytest tests/api -q`
Expected: all API tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/api/kirchhoff/agents/asset.py services/api/kirchhoff/api services/api/tests/api/test_api_asset.py
git commit -m "feat(asset): asset agent and /api/asset/{pack} for grid and solar

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 18: Docs exports to Cloud Storage, `/api/files` signed URLs, retire the P0 hello route, drop the compat shim (Thu 16)

**Files:**
- Modify: `services/api/kirchhoff/agents/docs_export.py` (append `latin1`, `boq_csv`, `calc_report_pdf`, `BlobExporter`), `services/api/kirchhoff/api/deps.py` (production exporter), `services/api/kirchhoff/api/app.py` (files router; drop hello)
- Create: `services/api/kirchhoff/api/files_routes.py`
- Delete: `services/api/kirchhoff/api/hello.py`, `services/api/tests/test_api_hello.py` (P0 says WS2 removes them; its two `/api/whoami` tests are superseded by Task 12's `test_whoami_survives_the_app_rewiring`, and the `GET /api/whoami` route in `app.py` stays), and `services/api/kirchhoff/runs/compat.py` (once WS1's `contracts/extra.py` exists)
- Test: `services/api/tests/agents/test_agents_docs_export.py`, `services/api/tests/api/test_api_files.py`

**Interfaces:**
- Consumes: `Exporter`, `SECTIONS`, `StubExporter` (Task 13); `BlobStore.exists/put/signed_url` (Task 8); the P3 docs step, which calls `deps.exporter.export(...)`.
- Produces:
  - `latin1(s) -> str` (maps √ Δ φ ≤ ≥ ″ → – — η μ ≈ to ASCII for Helvetica), `boq_csv(lines) -> bytes` and `calc_report_pdf(*, rev, findings, fixes, brief, options, pr_lines, order, summary) -> bytes` (reportlab; sections in the Docs agent's order).
  - `BlobExporter(blobs)` writes `workspaces/{uid}/exports/{rev}/calc-report.pdf` and `.../boq.csv`, and returns `[{"name", "path": "exports/{rev}/…", "status": "ready", "content_type"}]`. Production `Deps.exporter` is a `BlobExporter`.
  - `GET /api/files/{path}` with `path` matching `^(exports|revisions)/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$` → 302 to a V4 signed URL (600 s) for `workspaces/{uid}/{path}`, or 404 `not_found`. With `?redirect=0` it returns `200 {"url", "expires_in": 600}` instead: the web client uses this form and then fetches the signed URL with a plain `fetch` (no auth headers, so no CORS preflight on the bucket). If the blob store cannot sign (`MemoryBlobStore(public_base=None)`, local fakes), both forms return the bytes inline (`200`, the file's media type, header `X-Kirchhoff-Inline: 1`). Revision models (R7) and exports are fetched this way.

- [ ] **Step 1: Write the failing tests**

`services/api/tests/agents/test_agents_docs_export.py`:
```python
import io

import pdfplumber

from kirchhoff.agents.docs_export import SECTIONS, BlobExporter, boq_csv, calc_report_pdf, latin1
from kirchhoff.contracts import (Citation, DesignBrief, Finding, LedgerEntry, PRLine, Requirement, Revision,
                                 TopologyOption)
from kirchhoff.runs.blobs import MemoryBlobStore

LINES = [PRLine(material_id="TX-3150", description="Transformer 3.15 MVA", qty=6, unit_price=118000.0,
                lead_time_weeks=12),
         PRLine(material_id="BW-1600", description="Busway 1,600 A", qty=410, unit_price=420.0, lead_time_weeks=8)]
FIX = Finding(id="R05:FA-01", rule_id="R05", element_id="FA-01", status="fail", title="Voltage drop", value=2.16,
              limit=2.0, unit="%", formula="ΔU% = 100·√3·I·L·(R cosφ + X sinφ)/U",
              fix={"candidate": "FA-01:cable-CBL-240-8P", "label": "Parallel cable feeder for FA-01", "agent": "power",
                   "reason": "Largest voltage-drop margin per dollar."},
              rejected_fix={"candidate": "FA-01:upsize-BW-2000", "label": "Upsize FA-01 to 2,000 A busway"})
REV = Revision(id="abc-r2", project_id="hall-b", parent="abc-r1", author="Kirchhoff agents", hash="f" * 64,
               check_summary={"pass": 40, "fail": 0, "warn": 0, "n/a": 2}, status="checked",
               ledger=[LedgerEntry(kind="not_checked", agent="checker", text="Selectivity")], created_at=0.0)
BRIEF = DesignBrief(project_id="hall-b", requirements=[Requirement(
    id="REQ-dv_max_pct", text="shall not exceed 2.0%", value=2.0, unit="%", verified=True,
    citation=Citation(doc_id="tender-hall-a", page=4, quote="shall not exceed 2.0%", clause="§4.6"))])
OPTS = [TopologyOption(id="2N", installed_mva=18.9, normal_loading_pct=38, failover_loading_pct=76, cost=4.1e6,
                       losses_kw=310, max_lead_time_weeks=16, spof_count=0)]


def _pdf_text(data: bytes) -> str:
    with pdfplumber.open(io.BytesIO(data)) as doc:
        return " ".join(p.extract_text(x_tolerance=1.5) or "" for p in doc.pages)


def test_latin1_maps_engineering_symbols():
    assert latin1("ΔU ≤ √3 · I") == "dU <= sqrt3 · I"


def test_boq_csv_has_header_lines_and_total():
    rows = boq_csv(LINES).decode().strip().split("\n")
    assert rows[0] == "material_id,description,qty,unit_price_usd,line_total_usd,lead_time_weeks"
    assert rows[1] == "TX-3150,Transformer 3.15 MVA,6,118000.00,708000.00,12"
    assert rows[-1] == "TOTAL,,416,,880200.00,12"


def test_calc_report_contains_every_section_in_order():
    data = calc_report_pdf(rev=REV, findings=[FIX], fixes=[FIX], brief=BRIEF, options=OPTS, pr_lines=LINES,
                           order=SECTIONS, summary="The 2N design passes every check.")
    text = _pdf_text(data)
    heads = ["Summary", "Requirements", "Topology options", "Checker findings", "Fixes", "Assumptions ledger",
             "Bill of quantities"]
    assert [text.index(h) for h in heads] == sorted(text.index(h) for h in heads)
    assert "Parallel cable feeder for FA-01" in text and "sqrt3" in text and "§4.6" in text


def test_blob_exporter_writes_both_files():
    blobs = MemoryBlobStore()
    files = BlobExporter(blobs).export(uid="u1", rev=REV, findings=[FIX], fixes=[FIX], brief=BRIEF, options=OPTS,
                                       pr_lines=LINES, order=SECTIONS, summary="ok")
    assert [f["path"] for f in files] == ["exports/abc-r2/calc-report.pdf", "exports/abc-r2/boq.csv"]
    assert blobs.get("workspaces/u1/exports/abc-r2/calc-report.pdf").startswith(b"%PDF")
    assert blobs.blobs["workspaces/u1/exports/abc-r2/boq.csv"][1] == "text/csv"
```

`services/api/tests/api/test_api_files.py`:
```python
from fastapi.testclient import TestClient

from kirchhoff.agents.docs_export import BlobExporter
from kirchhoff.api.app import create_app
from kirchhoff.runs.blobs import MemoryBlobStore
from kirchhoff.runs.revisions import latest_revision


def _to_review(client, auth) -> str:
    rid = client.post("/api/runs", json={"project_id": "hall-b", "autonomy": "auto"}, headers=auth).json()["run_id"]
    return rid


def test_exports_are_written_and_served_by_signed_url(client, deps, auth):
    deps.exporter = BlobExporter(deps.blobs)
    rid = _to_review(client, auth)
    rev = latest_revision(deps.store, "u1", rid)["id"]
    events = deps.store.list_docs(f"workspaces/u1/runs/{rid}/events")
    exports = [e["payload"] for e in events if e["kind"] == "artifact" and e["payload"]["type"] == "export"]
    assert [e["ref"] for e in exports] == [f"exports/{rev}/calc-report.pdf", f"exports/{rev}/boq.csv"]
    r = client.get(f"/api/files/exports/{rev}/calc-report.pdf", headers=auth, follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"].startswith(
        f"https://storage.example.test/workspaces/u1/exports/{rev}/calc-report.pdf")
    model = client.get(f"/api/files/revisions/{rev}/model.json", headers=auth, follow_redirects=False)
    assert model.status_code == 302
    as_json = client.get(f"/api/files/exports/{rev}/boq.csv?redirect=0", headers=auth)
    assert as_json.status_code == 200 and as_json.json()["url"].startswith(
        f"https://storage.example.test/workspaces/u1/exports/{rev}/boq.csv") and as_json.json()["expires_in"] == 600


def test_unsigned_blob_store_serves_bytes_inline(client, deps, auth):
    deps.blobs = MemoryBlobStore(public_base=None)  # local KIRCHHOFF_FAKES=1 / KIRCHHOFF_BLOBS=memory
    deps.blobs.put("workspaces/u1/revisions/x-r1/model.json", b'{"racks": []}', "application/json")
    for q in ("", "?redirect=0"):
        r = client.get(f"/api/files/revisions/x-r1/model.json{q}", headers=auth, follow_redirects=False)
        assert r.status_code == 200 and r.headers["x-kirchhoff-inline"] == "1" and r.json() == {"racks": []}


def test_files_are_scoped_and_validated(client, deps, auth):
    deps.blobs.put("workspaces/u1/exports/x-r1/boq.csv", b"a", "text/csv")
    assert client.get("/api/files/exports/x-r1/boq.csv", headers=auth, follow_redirects=False).status_code == 302
    other = TestClient(create_app(deps=deps, verify_token=lambda t: "u2"))
    assert other.get("/api/files/exports/x-r1/boq.csv", headers=auth, follow_redirects=False).status_code == 404
    for bad in ["exports/../u2/boq.csv", "secrets/x/y", "exports/x-r1"]:
        assert client.get(f"/api/files/{bad}", headers=auth, follow_redirects=False).status_code == 404


def test_hello_route_is_gone_and_whoami_stays(client, auth):
    assert client.post("/api/hello-run", headers=auth).status_code == 404
    assert client.get("/api/whoami").status_code == 401
    assert client.get("/api/whoami", headers=auth).json() == {"uid": "u1"}
```

- [ ] **Step 2: Run to verify failure**

Run: `cd services/api && uv run pytest tests/agents/test_agents_docs_export.py tests/api/test_api_files.py -q`
Expected: FAIL with `ImportError: cannot import name 'BlobExporter'`

- [ ] **Step 3: Implement the exports**

Append to `services/api/kirchhoff/agents/docs_export.py` (move the new imports to the top of the module):
```python
import csv
import io
from xml.sax.saxutils import escape

_SYMBOLS = {"√": "sqrt", "Δ": "d", "φ": "phi", "≤": "<=", "≥": ">=", "″": "''", "′": "'", "→": "->", "∥": "||",
            "–": "-", "—": "-", "η": "eta", "μ": "u", "Σ": "sum", "ṁ": "m_dot", "≈": "~", "Ω": "Ohm"}


def latin1(s: object) -> str:
    text = "".join(_SYMBOLS.get(ch, ch) for ch in str(s))
    return text.encode("latin-1", "replace").decode("latin-1")


def boq_csv(lines: list[PRLine]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["material_id", "description", "qty", "unit_price_usd", "line_total_usd", "lead_time_weeks"])
    for x in lines:
        w.writerow([x.material_id, x.description, x.qty, f"{x.unit_price:.2f}", f"{x.qty * x.unit_price:.2f}",
                    x.lead_time_weeks])
    w.writerow(["TOTAL", "", sum(x.qty for x in lines), "", f"{sum(x.qty * x.unit_price for x in lines):.2f}",
                max((x.lead_time_weeks for x in lines), default=0)])
    return buf.getvalue().encode("utf-8")


def calc_report_pdf(*, rev: Revision, findings: list[Finding], fixes: list[Finding], brief: DesignBrief | None,
                    options: list[TopologyOption], pr_lines: list[PRLine], order: list[str], summary: str) -> bytes:
    from reportlab import rl_config

    rl_config.invariant = 1
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=15, leading=19, spaceAfter=6)
    h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=11.5, leading=15, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("b", fontName="Helvetica", fontSize=9, leading=12)

    def para(s: object, style=body) -> Paragraph:
        return Paragraph(escape(latin1(s)), style)

    def table(rows: list[list[object]]) -> Table:
        t = Table([[latin1("" if c is None else c) for c in r] for r in rows], repeatRows=1)
        t.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), "Helvetica", 7.5),
                               ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 7.5),
                               ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return t

    reqs = brief.requirements if brief else []
    ordered = sorted(findings, key=lambda f: (f.status != "fail", f.rule_id, f.element_id))
    sections = {
        "summary": lambda: [para("Summary", h2), para(summary), para(
            f"Revision {rev.id} · hash {rev.hash} · " + ", ".join(f"{k} {v}" for k, v in rev.check_summary.items()))],
        "requirements": lambda: [para("Requirements (verified tender citations)", h2), table(
            [["Id", "Clause", "Page", "Value", "Unit", "Verified"]]
            + [[r.id, r.citation.clause, r.citation.page, r.value, r.unit, "yes" if r.verified else "no"]
               for r in reqs])],
        "options": lambda: [para("Topology options", h2), table(
            [["Option", "Installed MVA", "Normal %", "Failover %", "Cost USD", "Losses kW", "Max lead (wk)", "SPOF"]]
            + [[o.id, o.installed_mva, o.normal_loading_pct, o.failover_loading_pct, f"{o.cost:,.0f}", o.losses_kw,
                o.max_lead_time_weeks, o.spof_count] for o in options])],
        "findings": lambda: [para("Checker findings", h2), table(
            [["Rule", "Element", "Status", "Value", "Limit", "Unit", "Clauses"]]
            + [[f.rule_id, f.element_id, f.status, f.value, f.limit, f.unit,
                ", ".join(c.clause for c in f.tender_refs if c.clause)] for f in ordered])],
        "fixes": lambda: [para("Fixes", h2)] + ([para(
            f"{f.id}: {f.fix['label']} ({f.fix.get('agent', '')}). {f.fix.get('reason', '')} Formula: {f.formula}."
            + (f" Rejected: {f.rejected_fix['label']}." if f.rejected_fix else "")) for f in fixes]
            or [para("No fixes were needed.")]),
        "ledger": lambda: [para("Assumptions ledger", h2)] + [para(f"[{e.kind}] {e.text}") for e in rev.ledger],
        "boq": lambda: [para("Bill of quantities", h2), table(
            [["Material", "Description", "Qty", "Unit price USD", "Lead (wk)"]]
            + [[x.material_id, x.description, x.qty, f"{x.unit_price:,.2f}", x.lead_time_weeks] for x in pr_lines])],
    }
    story = [para("Kirchhoff calc report", h1),
             para("IEC-based, illustrative values, not for construction. Every number comes from the "
                  "deterministic engine; text was checked against the digit allowlist.")]
    for name in order:
        story += sections[name]()
        story.append(Spacer(1, 3 * mm))
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, title=f"Calc report {rev.id}", leftMargin=16 * mm, rightMargin=16 * mm,
                      topMargin=16 * mm, bottomMargin=16 * mm).build(story)
    return buf.getvalue()


class BlobExporter:
    def __init__(self, blobs) -> None:
        self.blobs = blobs

    def export(self, *, uid: str, rev: Revision, findings: list[Finding], fixes: list[Finding],
               brief: DesignBrief | None, options: list[TopologyOption], pr_lines: list[PRLine], order: list[str],
               summary: str) -> list[dict]:
        base = f"exports/{rev.id}"
        pdf = calc_report_pdf(rev=rev, findings=findings, fixes=fixes, brief=brief, options=options,
                              pr_lines=pr_lines, order=order, summary=summary)
        self.blobs.put(f"workspaces/{uid}/{base}/calc-report.pdf", pdf, "application/pdf")
        self.blobs.put(f"workspaces/{uid}/{base}/boq.csv", boq_csv(pr_lines), "text/csv")
        return [{"name": "calc-report.pdf", "path": f"{base}/calc-report.pdf", "status": "ready",
                 "content_type": "application/pdf"},
                {"name": "boq.csv", "path": f"{base}/boq.csv", "status": "ready", "content_type": "text/csv"}]
```

In `services/api/kirchhoff/api/deps.py`, import `from kirchhoff.agents.docs_export import BlobExporter` and pass `exporter=BlobExporter(blobs)` in the final `Deps(...)` call of `build_production_deps`.

- [ ] **Step 4: Implement the files route, retire hello and wire the app**

`services/api/kirchhoff/api/files_routes.py`:
```python
import mimetypes
import re

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse, Response

from kirchhoff.runs.deps import Deps

from .errors import err

FILE_RE = re.compile(r"^(exports|revisions)/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")
SIGNED_URL_TTL_S = 600


def make_router(deps: Deps, current_uid) -> APIRouter:
    router = APIRouter()

    @router.get("/api/files/{path:path}")
    def files(path: str, redirect: bool = True, uid: str = Depends(current_uid)):
        if not FILE_RE.match(path) or ".." in path:
            return err(404, "not_found")
        full = f"workspaces/{uid}/{path}"
        if not deps.blobs.exists(full):
            return err(404, "not_found")
        try:
            url = deps.blobs.signed_url(full, SIGNED_URL_TTL_S)
        except NotImplementedError:  # local in-process blobs: serve the bytes
            media = mimetypes.guess_type(path)[0] or "application/octet-stream"
            return Response(deps.blobs.get(full), media_type=media, headers={"X-Kirchhoff-Inline": "1"})
        if not redirect:  # web client: fetch the signed URL without auth headers (no CORS preflight)
            return {"url": url, "expires_in": SIGNED_URL_TTL_S}
        return RedirectResponse(url, status_code=302)

    return router
```

Run: `git rm services/api/kirchhoff/api/hello.py services/api/tests/test_api_hello.py`

In `services/api/kirchhoff/api/app.py`: delete the line `from .hello import make_router as hello_router` and the `app.include_router(hello_router(...))` line (keep the `GET /api/whoami` route), change the router import to `from . import asset_routes, copilot_routes, files_routes, runs_routes, workspace_routes`, and add after the asset router:
```python
    app.include_router(files_routes.make_router(deps, current_uid))
```

- [ ] **Step 5: Grant Cloud Run the right to sign URLs (one-time, infra)**

Signed URLs on Cloud Run are signed through IAM `signBlob`. Ask the controller or WS4 to run this once (infra is WS4-owned):
```bash
PN=$(gcloud projects describe ordinal-mep --format='value(projectNumber)')
gcloud iam service-accounts add-iam-policy-binding "${PN}-compute@developer.gserviceaccount.com" --project=ordinal-mep \
  --member="serviceAccount:${PN}-compute@developer.gserviceaccount.com" --role=roles/iam.serviceAccountTokenCreator
```
Expected: the updated policy is printed. Local development uses `KIRCHHOFF_BLOBS=memory` (user credentials cannot sign).

- [ ] **Step 6: Drop the compat shim once WS1's contracts land**

If `services/api/kirchhoff/contracts/extra.py` exists, run:
```bash
cd services/api
grep -rl "kirchhoff.runs.compat\|from .compat import" kirchhoff tests | xargs sed -i '' -e 's/from \.compat import/from kirchhoff.contracts.extra import/' -e 's/kirchhoff\.runs\.compat/kirchhoff.contracts.extra/'
git rm kirchhoff/runs/compat.py
```
If the file does not exist yet, skip this step and tell the controller the shim is still in place.

- [ ] **Step 7: Run everything**

Run: `cd services/api && uv run pytest -q`
Expected: all tests pass (live tests skipped). Then run the three live suites once with `KIRCHHOFF_LIVE=1` (Tasks 5, 11, 14) and paste the printed metrics JSON into the commit message.

- [ ] **Step 8: Check the smoke test still holds**

`infra/smoke.sh` (WS4) already probes `GET /api/whoami` → 401 (P0 fix wave), which this task keeps. Run `bash infra/smoke.sh http://localhost:8080` against a local `make dev-api` and expect `smoke OK` (the `/` HTML probe needs the web build; skip it locally if it fails for that reason only).

- [ ] **Step 9: Commit**

```bash
git add -A services/api
git commit -m "feat(docs): calc report PDF + BOQ CSV to Cloud Storage, /api/files signed URLs; retire hello route

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

## Notes for other workstreams (send with this plan)

**WS1 (engine + scenario)**
- `tender.yaml` and `geometry.yaml` are used exactly as authored in the P1 plan (R1, R2); WS2's fixtures are verbatim copies and drift tests compare them. If you edit either file, tell WS2 so the fixture, `ground_truth.yaml` and `FAKE_REPLIES` quotes can be re-synced.
- WS2 calls the facade by name through `Deps.engine`: `load_scenario("hall_a", <repo>/scenarios)`, `place_racks`, `size_cooling`, `power_options`, `annotate_options`, `power_recheck`, `route` (once per option), `detect_clashes`, `derive_pr_lines`, `check` (also with `pr_lines=` submitted PR lines), `fix_candidates`, `apply_fix`, `what_if`, `model_hash`, `ledger_not_checked`, plus `engine.grid.evaluate_grid(dir)` and `engine.solar.evaluate_solar(dir)` (every option dict needs `"id"`).
- WS2 relies on: R05 candidate metrics `dv_pct` and `dv_limit_pct`, and R11 metrics `changed_pipes` (fix criteria R23); swap records with `from`, `to`, `reason`, `ikss_ka_before` and `ikss_ka_after`; and Finding ids `"{rule}:{element}"`.
- Until `kirchhoff/contracts/extra.py` lands, WS2 uses `kirchhoff/runs/compat.py` with identical shapes; Task 18 deletes the shim.

**WS3 (web)**
- Event visibility: show an event iff `steps/{event.step}.attempt == event.attempt` (R4). Gates are steps `pN.gate.{gate}` carrying a `gate` event `{gate, auto}`.
- The brief is at `workspaces/{uid}/runs/{rid}/outputs/p1.intake`, field `json` (a JSON string), key `brief`; the `artifact {type: "brief"}` ref is exactly that Firestore path. The event can arrive before the step commits the doc, so retry the read when it is missing. Options are on `runs/{rid}.options`, and `artifact {type: "options"}` carries `recommended`.
- Revision docs have `model: null` and `model_url: "revisions/{rev}/model.json"`; fetch the model with `GET /api/files/revisions/{rev}/model.json?redirect=0` → `{url}`, then a plain `fetch(url)` (or the bytes inline when the response carries `X-Kirchhoff-Inline: 1`, local fakes). Exports use the same route with `exports/{rev}/calc-report.pdf` and `exports/{rev}/boq.csv` (from `artifact {type: "export", ref, name, status}`, emitted only when the file exists).
- `artifact {type: "revision"}` carries `changed: [element ids]` for the diff recolour and precedes that revision's `finding` events, whose payload carries `rev`. Approve is disabled iff the latest revision's `check_summary.fail > 0`; the API also returns 409 `open_findings`. The review gate always signs the latest revision. Finding `fix`/`rejected_fix` have `deltas` (metrics + `cost_delta`); finding `tender_refs` carry pdfplumber `bbox`es.
- Error shapes are in R18 (`429 global_cap` carries `offer: "replay"`; `409 run_in_progress` on reset while a lease is live). Plan answers must be one of the question's `options` (R34).
- Voice: `POST /api/voice` takes multipart field `audio` and form field `revision_ref`, and returns `{transcript, answer, tool_results: [{name, args, result}]}`. Show `transcript` as "You said", and show and speak `answer`. Live mode uses `LIVE_SYSTEM_INSTRUCTION` from `kirchhoff/agents/specs.py` verbatim, `new AgentPlatformBackend('us-central1')` (Firebase JS SDK 13's name for the spec's `VertexAIBackend`) and the same three tool names. There is no tender upload route (R15).
- Explanations: fill `{value}`/`{limit}` with the unit only when the template does not already write it (R30).
- Asset packs: `POST /api/asset/{pack}` → `{options, recommended, findings, geometry, choice}`; show `choice.reason` as the Asset agent's narration and mark `choice.option` (R33).
- For local development before WS1/Vertex: run `KIRCHHOFF_FAKES=1 make dev-api` for a full P1→P4 flow on fakes (real Firestore, in-process blobs served inline by `/api/files`).

**WS4 (enterprise, demo world, infra)**
- Provide `kirchhoff/enterprise/client.py: make_enterprise_client() -> EnterpriseClient` (protocol in `kirchhoff/agents/ports.py`). It must make no network calls at construction. It needs `create_pr` with `idempotency_key` deduplication, `set_pr_status`, `set_opportunity_stage` and `reset_visitor(uid)`, with all visitor data scoped by uid. The Hall B opportunity id is `opp-hall-b`.
- WS2 mirrors visitor PRs to `workspaces/{uid}/prs/{prid}` (`PurchaseRequisition.model_dump()`, `project_id: "hall-b"`) and the CRM overlay to `workspaces/{uid}/crm/opp-hall-b` (`CrmOverlay.model_dump()`). Your `/api/enterprise/*` proxy (auto-included if `kirchhoff/api/enterprise_proxy.py` exports `make_router(store, current_uid)`) can read them. The full list of WS4 obligations is `docs/superpowers/plans/2026-10-13-ws4-obligations.md`.
- Image: copy `scenarios/` to `/app/scenarios` and `apps/web/public/demo/projects/*.json` to `/app/seed` (or set `KIRCHHOFF_SCENARIOS_DIR` / `KIRCHHOFF_SEED_DIR`). Seed bundle revisions must inline `model` (what-if and explain on `seed:` refs read it).
- `capture.py`: revision models are in GCS (`workspaces/{uid}/revisions/{rev}/model.json`; R7) and the brief is in the `p1.intake` outputs doc; recompute hashes with `engine.model_hash` (R22).
- Infra: grant the runtime service account `roles/iam.serviceAccountTokenCreator` on itself (Task 18 Step 5). `infra/smoke.sh` keeps probing `GET /api/whoami` → 401 (permanent). Bucket CORS must allow `GET` from https://kirchhoff.web.app (the browser fetches signed URLs directly). `services/api/pyproject.toml` gains `python-multipart` (Task 16).

## Self-review

- **Spec coverage.**
  - §1 (model, ADK 2.11, < 10 s, Live in us-central1): Global Constraints and Tasks 5, 12, 15–17.
  - §6.1 agents and deciders: Intake (Task 9), Orchestrator choosing questions for the human (Task 11), Layout narration (Tasks 11, 13), Power offering options, rechecking and choosing fixes (Tasks 11, 13), Cooling sizing and fixes (Tasks 11, 13), Procurement narrating swaps and creating PRs (Tasks 11, 14), deterministic Checker (Task 13), Docs ordering and summary (Tasks 13, 18), Co-pilot (Tasks 15, 16), Asset agent (Task 17).
  - §6.1 Auto rules: plan gate defaults to the main body (Task 11); option gate filter and lowest cost (Task 11 policy, Task 13); engine-only fix candidates with an agent choice and reason (Task 13, R23); exhaustion after 2 iterations disables approve (Tasks 13–14).
  - §6.2 v4.1 phases, steps including `p2.power_recheck`, transactional start and commit on `lease.attempt`, streamed events, `seq` continuity, resume, 24 h expiry, live cap and P4 consistency failure: Tasks 6, 8, 10, 11, 13, 14.
  - §6.3 trust: digit allowlist (Task 4) applied to every narration, reason, explanation and answer; verified quotes with bbox and "N/M quotes verified" (Tasks 3, 9, 11); drawing cross-check (Tasks 2, 11); ledger (Tasks 11, 13, 14).
  - §6.4 what-if on `ws:` and `seed:` refs without saving: Task 15.
  - §6.5 push-to-talk, Live instruction and ledger note: Tasks 5, 13, 16.
  - §7: API auth (P0) and App Check flag unchanged; Firestore, Cloud Storage and Vertex: Tasks 8, 12, 18.
  - §11 limits, retries, structured-output repair and Firestore discipline: Tasks 5, 6, 8, 12.
  - §14 paths and security (client reads only; all writes through `/api`): every write is server-side.
  - §16 agent schema tests with recorded responses plus one live smoke per day: Tasks 5, 11, 14.
  - §17 schedule: see the mapping above.
- **Placeholder scan.** Every code step contains complete code. Shared files touched outside WS2 ownership are listed explicitly (`pyproject.toml`, deletion of P0 hello). Infra commands are flagged as WS4-coordinated.
- **Type consistency.** `ctx.agent(spec, step, message, tools=(), attachments=(), key=None)` and `ctx.agent_json(spec, step, message, schema, ...)` are used the same way in Tasks 8, 11 and 13. `build_fake_deps(store, scenarios_dir, seed_dir=None, replies=None, **overrides)` is the same in Tasks 8, 11, 12 and 14. Replay keys are `"{agent}:{key}"`, with fix keys `"p3.fix.{n}:{finding_id}"`, explain keys `"explain:{finding_id}"`, voice key `"voice"` and asset keys `"{pack}"`. Revision ids are `{rid}-r{n}` everywhere. The `Exporter.export` keyword set (`uid, rev, findings, fixes, brief, options, pr_lines, order, summary`) matches across `StubExporter`, `BlobExporter` and the P3 docs step.
- **Reconciliation (13 Oct).** Rulings R25–R34 and the "Reconciliation log (13 Oct)" in `2026-10-13-interfaces.md` record the cross-plan changes: P0 fix-wave store/event APIs and the EventWriter hardening (Tasks 6, 8, 10, 12), `/api/whoami` kept (Tasks 12, 18), revision-artifact-first finding events with `rev` (Tasks 13, 14), export artifacts only for written files, `deltas` with `cost_delta`, tender-ref boxes (Task 13), unit-aware `fill_finding` (Tasks 4, 15), voice `tool_results[].name` and `explain_finding(element_id)` (Task 16), `/api/files?redirect=0` and inline local blobs (Tasks 8, 12, 18). These edits were made in the plan text and have not been executed yet; each task's test step covers them. WS4's side is in `2026-10-13-ws4-obligations.md`.
