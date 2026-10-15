# Kirchhoff — cross-workstream interfaces (binding for plans P1–P4)

Spec: `docs/superpowers/specs/2026-10-13-kirchhoff-design.md` (v4). Contracts: `services/api/kirchhoff/contracts/` as defined in `docs/superpowers/plans/2026-10-13-p0-foundation.md` Task 2 (frozen; plans may only **add** optional fields or **new** models in `kirchhoff/contracts/extra.py`).

## Ownership

| Workstream | Plan file | Owns (create/modify only these) |
|---|---|---|
| WS1 engine + scenario | `2026-10-13-p1-engine.md` | `services/api/kirchhoff/engine/**`, `services/api/tests/engine/**`, `scenarios/hall_a/{tender.yaml,catalogue.yaml,geometry.yaml,erp_seed.yaml}`, `scenarios/grid/**`, `scenarios/solar/**`, `services/api/kirchhoff/contracts/extra.py` |
| WS2 agents + API | `2026-10-13-p2-agents-api.md` | `services/api/kirchhoff/agents/**`, `services/api/kirchhoff/runs/**`, `services/api/kirchhoff/api/**` (except `enterprise_proxy.py`), `services/api/kirchhoff/intake/**`, `scenarios/hall_a/{render_tender_pdf.py,render_drawing.py,ground_truth.yaml}`, generated `scenarios/hall_a/out/*`, `services/api/tests/{agents,runs,api,intake}/**` |
| WS3 web UI | `2026-10-13-p3-web.md` | `apps/web/**` |
| WS4 enterprise + demo world + infra | `2026-10-13-p4-enterprise-demo-infra.md` | `services/api/kirchhoff/enterprise/**`, `services/api/kirchhoff/api/enterprise_proxy.py`, `scenarios/demo_world/**`, `scenarios/hall_a/capture.py`, `infra/**`, `services/api/tests/enterprise/**`, Playwright tests in `e2e/**` |

### Shared files (added after the P0 final review, 13 Oct)

| File | Owner | Rule |
|---|---|---|
| `services/api/kirchhoff/store/**` | P0 (fix wave), then WS2 | WS2 owns it after the fix wave (P2 Task 6 hardens `EventWriter`; no `storeops.py` is needed); changes to the `Store` protocol or `EventWriter` signatures are announced to all workstreams |
| `services/api/kirchhoff/contracts/{common,design,run,checks,enterprise,bundle}.py` | frozen | only optional fields may be added, by WS2, announced to all |
| `services/api/kirchhoff/contracts/extra.py` | WS1 | new models only |
| `services/api/kirchhoff/contracts/export_schema.py` (`TOP_LEVEL`) + `apps/web/src/contracts/generated.ts` | whoever changes contracts | run `make gen-types` and commit `generated.ts` in the same commit; `make check-types` must pass |
| `services/api/pyproject.toml`, `uv.lock` | WS2 | other workstreams request dependency additions through the controller |
| `services/api/Dockerfile`, `.dockerignore`, `.gcloudignore`, `infra/**`, `Makefile` deploy targets | WS4 | image must contain `/app/scenarios` (repo `scenarios/`) and `/app/seed` (demo bundles); never upload `.venv` |
| `infra/smoke.sh` | WS4 | probes `GET /api/whoami` (permanent, 401 without token) |
| `apps/web/src/firebase.ts`, `apps/web/src/api.ts` | WS3 | WS4 coordinates App Check debug-token changes through the controller |

### Conventions (binding)

- Firestore documents are `model_dump()` output: **snake_case** field names (e.g. `parent`, `model_url`, `approver_name`), timestamps in **unix seconds**. The camelCase names in spec §14 are descriptive only.
- `RunRecord.lease` is `{"owner": str, "attempt": int, "heartbeat_at": float}`. A step is done when `steps/{id}.status == "done"` (there is no separate `done` field).
- Design models are never stored inline in Firestore (nested arrays such as `Geometry.columns` are rejected): revisions carry `model_url`, served by `/api/files`.
- Store API (P0 fix wave): `Store.transact(read_paths, fn) -> list[(path, data|None)]`, `Store.delete_tree(path) -> int`, `Store.list_docs(collection, order_by=None, descending=False, limit=None)`, deep-merge `update_doc`; `kirchhoff.store.validate.firestore_safe_problems(value)` and `json_size_bytes(value)`.
- EventWriter (P0 fix wave): `emit(agent, kind, title, detail="", payload=None, step=None)` (per-event step override, shared seq), trailing-edge timer flush, `ValueError` on unsafe or > 10 KB events (no seq consumed), `fence()` on lease loss. Never subclass it or touch private attributes.
- `GET /api/whoami` → `{uid}` is permanent.

## Engine facade (WS1 produces; WS2 consumes) — `kirchhoff/engine/api.py`

```python
from kirchhoff.contracts import (DesignModel, Rack, CoolingNode, Finding, TopologyOption, WhatIfResult,
                                 PRLine, Material)
from kirchhoff.contracts.extra import FixCandidate, ClashReport

class ErpView(Protocol):
    def get(self, material_id: str) -> Material: ...
    def search(self, category: str) -> list[Material]: ...

@dataclass(frozen=True)
class Scenario:
    name: str                      # "hall_a"
    tender: dict                   # parsed tender.yaml (clauses with ids, text, limits)
    catalogue: dict                # parsed catalogue.yaml
    geometry: dict                 # parsed geometry.yaml

def load_scenario(name: str = "hall_a", root: Path | None = None) -> Scenario
def place_racks(scn: Scenario) -> list[Rack]                                   # deterministic default (candidate #1)
def size_cooling(scn: Scenario, racks: list[Rack]) -> list[CoolingNode]          # CDUs per zone (N+1) + manifolds
def power_options(scn: Scenario, racks: list[Rack]) -> list[tuple[TopologyOption, DesignModel]]
    # one entry per topology in {"2N","DR","BLOCK"} that passes R01 at its minimum rating; models have
    # equipment + connections (no routes yet); TopologyOption.max_lead_time_weeks/cost filled from catalogue
def annotate_options(scn: Scenario, options: list[tuple[TopologyOption, DesignModel]], erp: ErpView
                     ) -> list[tuple[TopologyOption, DesignModel]]
    # applies r15_swap to every line failing R15, re-runs short circuit, recomputes metrics; records swaps
def route(scn: Scenario, model: DesignModel) -> DesignModel                      # busway feeders + pipes, default candidates
def detect_clashes(model: DesignModel) -> ClashReport                           # solid intersections only
def check(scn: Scenario, model: DesignModel, erp: ErpView, pr_lines: list[PRLine] | None = None) -> list[Finding]
    # full rule pack R01–R15 incl. R04b; one Finding per (rule, element) incl. passes; status pass|fail|warn|n/a
def fix_candidates(scn: Scenario, model: DesignModel, finding: Finding, erp: ErpView) -> list[FixCandidate]
    # only candidates that clear `finding` and create no new failure
def apply_fix(model: DesignModel, candidate: FixCandidate) -> DesignModel
def what_if(scn: Scenario, model: DesignModel, param: str, value: float, revision_ref: str, erp: ErpView
            ) -> WhatIfResult                                                    # < 3 s, no LLM, not saved
def derive_pr_lines(scn: Scenario, model: DesignModel, erp: ErpView) -> list[PRLine]
def model_hash(model: DesignModel) -> str                                        # sha256 of canonical JSON
def ledger_not_checked() -> list[str]                                            # spec §8.4 items
```

`kirchhoff/contracts/extra.py` (WS1 creates):
```python
class FixCandidate(Strict):
    id: str                 # "FA-01:upsize-2000"
    finding_id: str         # "R05:FA-01"
    label: str              # "Upsize FA-01 to 2,000 A busway"
    cost_delta: float       # USD
    metrics: dict[str, float]  # e.g. {"dv_pct": 1.66}
    patch: dict[str, Any]   # engine-internal description consumed by apply_fix

class ClashReport(Strict):
    clashes: list[dict[str, Any]]  # [{"a": "H-Z2", "b": "B-03", "kind": "solid", "at": [x, y, z]}]
```

Grid and solar (WS1 produces, WS2's Asset agent consumes): `kirchhoff/engine/grid.py: evaluate_grid(scn_dir) -> dict` and `kirchhoff/engine/solar.py: evaluate_solar(scn_dir) -> dict`, each returning `{"options": [...], "recommended": str, "findings": list[Finding], "geometry": {...}}`.

## Scenario files

- `scenarios/hall_a/tender.yaml` (WS1, Tuesday): clause list `[{id: "§4.6", title, text, page, limits: {...}}]` — single source for the tender PDF (WS2 renders it) and for engine limits. Includes the deliberate contradiction (§4.2 vs Appendix B) and §2.3 (26 weeks).
- `scenarios/hall_a/erp_seed.yaml` (WS1): the Hall A materials (incl. 2.5 MVA: stock 0, 98 weeks; 3.15 MVA: stock 6). WS4's demo-world generator includes these verbatim in the ~60-material ERP.
- `scenarios/hall_a/out/` (WS2 generates): `tender-hall-a.pdf`, `hall-a.dxf`, `hall-a-plan.pdf`.

## HTTP API (WS2 produces except /api/enterprise/*; WS3 consumes)

All under `/api`, Firebase ID token required except `/api/health`; JSON bodies; every call returns < 10 s.

| Method | Path | Body → Response |
|---|---|---|
| GET | `/api/health` | → `{ok, version}` |
| GET | `/api/whoami` | → `{uid}` (permanent; `infra/smoke.sh` probes it → 401 without a token) |
| POST | `/api/workspace` | → `{uid, created: bool}` |
| POST | `/api/workspace/reset` | → `{ok}`; 409 `{detail: "run_in_progress"}` while a run holds a live lease |
| POST | `/api/runs` | `{project_id: "hall-b", autonomy: "ask"\|"auto"}` → 202 `{run_id}` (starts P1); 429 `{detail: "visitor_rate_limit"}` or `{detail: "global_cap", offer: "replay"}` |
| POST | `/api/runs/{rid}/gates/plan` | `{answers: {question_id: resolution}, plan_notes: {step_id: note}}` → 202 `{ok}` (starts P2); each resolution ∈ that question's `options`, else 422 `invalid_answer` |
| POST | `/api/runs/{rid}/gates/option` | `{option_id: "2N"\|"DR"\|"BLOCK"}` → 202 `{ok}` (starts P3) |
| POST | `/api/runs/{rid}/gates/review` | `{decision: "approved"\|"rejected", comment}` → 202 `{ok}` (starts P4 if approved; signs the latest revision; 409 `open_findings` if its `check_summary.fail > 0`) |
| POST | `/api/runs/{rid}/resume` | → 202 `{resumed: bool}` |
| POST | `/api/what-if` | `{revision_ref, param, value}` → `WhatIfResult` |
| POST | `/api/explain` | `{revision_ref, finding_id}` → `{text}` |
| POST | `/api/voice` | multipart: file `audio` (webm/ogg) + form `revision_ref` → `{transcript, answer, tool_results: [{name, args, result}]}`. An `explain_finding` result is `{text}` plus an optional `revision`: the id of the earlier revision the answer cites (where the check failed), present only when it differs from `revision_ref`'s (issue #36). |
| POST | `/api/asset/{pack}` | `pack ∈ {grid, solar}` → `{options, recommended, findings, geometry, choice: {option, reason, source}}` (no events written) |
| GET | `/api/enterprise/erp/materials` | (WS4) → `Material[]` |
| GET | `/api/enterprise/erp/prs` | (WS4) → `PurchaseRequisition[]` (seed + visitor) |
| GET | `/api/enterprise/crm/opportunities` | (WS4) → `Opportunity[]` with visitor overlay applied |
| GET | `/api/files/{path}` | `path` = `exports/{rev}/{file}` or `revisions/{rev}/model.json` → 302 to a signed URL; `?redirect=0` → `{url, expires_in}` (what the web client uses); inline bytes + `X-Kirchhoff-Inline: 1` when blobs cannot be signed (local fakes) |

Firestore paths written by WS2 (read by WS3 via onSnapshot): spec §14 (`workspaces/{uid}/runs/{rid}`, `/steps/{stepId}`, `/events/{seq:06d}`, `workspaces/{uid}/revisions/{rev}`, `/findings/{fid}`, `workspaces/{uid}/approvals/{aid}`, `workspaces/{uid}/prs/{prid}`, `workspaces/{uid}/crm/{oid}`).

Static demo files (WS4 generates; WS3 consumes): `apps/web/public/demo/world.json` (`{org, people, projects: Project[], activity: [...]}`), `apps/web/public/demo/projects/{pid}.json` (`ProjectBundle`), `apps/web/public/demo/integrations.json` (`{erp: {materials, prs}, crm: {opportunities}, documents: [...], notifications: [...]}`).

## Event vocabulary (WS2 emits; WS3 renders)

`RunEvent.kind` values and payload shapes:
- `status`: `{}` — lane status line.
- `plan`: `{plan: PlanStep[], open_questions: OpenQuestion[]}`.
- `tool_call`: `{tool: str, args: dict}`; `tool_result`: `{tool: str, summary: dict}`.
- `artifact`: `{type: "brief"|"options"|"revision"|"export", ref: str}` — UI fetches/reads the referenced doc. `brief` ref = `workspaces/{uid}/runs/{rid}/outputs/p1.intake` (doc `{step, json}`; parse `json`, read `brief`); `options` ref = the run doc (+ `recommended`); `revision` ref = `workspaces/{uid}/revisions/{rev}` (+ `changed: [element ids]`); `export` ref = storage path `exports/{rev}/{file}` (+ `name`, `status`; emitted only once the file exists).
- `finding`: `{finding_id, rule_id, element_id, status, rev}` — emitted after its revision's artifact; one per failing finding.
- `gate`: `{gate: "plan"|"option"|"review", auto: bool}` — gates are steps `pN.gate.{gate}`.
- `ledger`: `{entry: LedgerEntry}`.
- `message`: `{}` — narration text in `title`/`detail` (digits only via allowlist, spec §6.3).
- Visibility: the UI shows an event iff `steps/{event.step}.attempt == event.attempt` (steps without a doc: latest attempt).

## Reconciliation log (13 Oct)

Cross-plan pass over P2 (agents/API) and P3 (web) against this doc, the spec and P1's facade. One line per decision: what · plan changed · why. WS4's side is collected in `2026-10-13-ws4-obligations.md`.

**Store / events / infra**
1. Store ops use `Store.transact/delete_tree/list_docs(order_by, descending, limit)`; `storeops.py` and every touch of `MemoryStore._docs/_lock` or `FirestoreStore._db` removed · P2 T6, T8, T10, T12 · P0 fix-wave APIs are binding; private access breaks on store changes.
2. `firestore_safe_problems` comes from `kirchhoff.store.validate`; test fixtures use `CheckedStore` (in `runs/fakes.py`) instead of reading `store._docs`; `run_step` rejects unsafe `StepOutput.docs` before commit · P2 T8, T12 · one validator, no private access.
3. `PhaseEventWriter` subclass removed: one plain `EventWriter` per phase, every event `emit(..., step=...)`, `next_seq` via `list_docs(order_by="seq", descending=True, limit=1)` · P2 T8, T10 · fix-wave API; parallel steps never rely on `set_step`.
4. Lease loss fences the writer (`PhaseContext.emit`, `run_step` begin/commit, worker `except LeaseLost`) · P2 T8, T10 · a stale worker writes no further events.
5. `PhaseContext.emit` normalises payloads (`json` round-trip: tuples → lists, numpy → str) before the strict writer · P2 T8 · engine summaries must not fail a step on tuple data.
6. EventWriter hardening (coordinator request): `RLock` + flush-and-assign `set_step` in one critical section; failed timer flush re-arms with backoff `min(interval·2ⁿ, 5 s)`, ≤ 5 attempts, each logged; `close()` sets a closed flag under the lock (later `emit` raises) · P2 T6 (`kirchhoff/store/events.py`, `tests/test_events.py`) · TOCTOU on step tags; stranded events; timers armed after close.
7. `GET /api/whoami` kept in P2's rewired `app.py` (T12) and after the hello removal (T18), with tests replacing those in the deleted `test_api_hello.py`; T18 no longer asks WS4 to probe `POST /api/runs` · P2 T12, T18, notes · whoami is permanent and `infra/smoke.sh` probes it.
8. `/api/files/{path}?redirect=0` → `{url, expires_in}`; the web client fetches the signed URL with a plain `fetch`; unsigned blob stores (`MemoryBlobStore(public_base=None)`, `KIRCHHOFF_FAKES=1`, `KIRCHHOFF_BLOBS=memory`) serve bytes inline with `X-Kirchhoff-Inline: 1` · P2 T8, T12, T18; P3 T3 (`fileBlob`, R19); table row updated · a 302 followed by `fetch` with auth/App Check headers forces a cross-origin preflight on the bucket; fake signed URLs broke local live runs.
9. `KIRCHHOFF_FAKES=1 make dev-api` is the documented local live backend for WS3 · P2 notes, P3 T11 · full P1→P4 on fakes with real Firestore.

**Artifacts, findings, revisions**
10. Brief artifact ref stays WS2's outputs doc `workspaces/{uid}/runs/{rid}/outputs/p1.intake` (`{step, json}`); P3's live adapter parses `json` → `brief` instead of expecting a `runs/{rid}/artifacts/brief` DesignBrief doc · P3 T4 (R7), P2 R26 · cheaper on the reader; no second copy of the brief in Firestore.
11. P3 retries brief/model reads when the doc is missing or the read fails (on the next steps/events snapshot) · P3 T4 · events flush before the step commit, so the brief artifact can arrive before its doc exists.
12. Revision artifact is emitted before that revision's `finding` events, and every `finding` payload carries `rev` (incl. P4's `R12:submitted-prs`) · P2 T13, T14 (R27); event vocabulary updated · P3 ruling R8 (replay attribution).
13. Export artifacts only for files that exist (`ref` = `exports/{rev}/{file}`); pending stub exports emit a `status` event · P2 T13 · P3 rendered a button with an empty ref.
14. `fix.deltas` / `rejected_fix.deltas` = engine metrics + `cost_delta` (top-level `cost_delta` kept) · P2 T13 (R31) · P3's drawer lists `deltas` only.
15. Finding `tender_refs` get pdfplumber `bbox`es from the rendered tender PDF (`with_citation_boxes`) before revisions are written · P2 T13 (R32) · the engine cites page + quote without a box; spec §12 screen 6 needs the highlight.
16. P3 keeps computing the diff from the two models; the revision artifact's `changed` list is informational · no change · both are engine-derived and equivalent.
17. Approve: the review gate signs the latest revision; P3 enables Approve only on the latest revision and only if its `check_summary.fail` (fallback: counted findings) is 0 · P3 T15 (R22); table row updated · matches P2's 409 `open_findings` rule.

**HTTP shapes and UI text**
18. `/api/voice` `tool_results` items use key `name` (was `tool`); `explain_finding` accepts `finding_id` or `element_id` like P3's Live declarations · P2 T16 (R29); table row updated · P3 ruling R9.
19. P3's Live session uses P2's `LIVE_SYSTEM_INSTRUCTION` verbatim (exported constant in `liveVoice.ts`) · P3 T17 (R24) · P2 told WS3 to copy it; P3 had its own wording.
20. Firebase AI Logic: the browser uses `new AgentPlatformBackend('us-central1')` (Firebase JS SDK 13's name for spec §6.5's `VertexAIBackend`), model `gemini-live-2.5-flash-native-audio` · P2 T5 comment + notes; P3 R1 unchanged · same Vertex backend and region; the spec text is read through P3 R1.
21. Plan-gate answers must be one of `OpenQuestion.options` (`[main-body value, "compare_all"]`); P3 drops the free-text answer, labels `compare_all` "Compare all three topologies" and aligns its fixture · P3 T2 fixture, T12 (R21); P2 R34; table row updated · P2 rejects anything else with 422 `invalid_answer`.
22. WS2 error `detail` codes map to sentences through `describeApiError` (start panel, plan gate, review, reset) · P3 T3, T11, T12, T14, T15 (R23) · the UI showed raw codes such as `global_cap`.
23. Reset: a 409 `run_in_progress` keeps local state and explains why; only an unreachable backend still clears local progress · P3 T14 · the error was swallowed and the overlay silently kept.
24. Placeholders: `{value}`/`{limit}` are filled with the unit only when the text right after them does not already write it (`fill_finding` in P2 T4/T15, `fillPlaceholders` in P3 T1, R20/R30) · both · P1's templates write units ("{value}% against a limit of {limit}%"), so both readers printed "2.16%%".
25. Asset packs: `POST /api/asset/{pack}` returns `{options, recommended, findings, geometry, choice}` and writes no events; the static grid/solar bundles' `evaluate_grid`/`evaluate_solar` `tool_result` events are WS4's; P3 marks `choice.option ?? recommended` and narrates `choice.reason` · P2 R33, P3 T1/T18 (R5); table row updated · there is no live asset run for WS2 to emit into.
26. Grid mini SLD: P3 derives it from WS1's `geometry.nodes/edges` when the result has no `sld` key · P3 T18 · `evaluate_grid` returns exactly four keys.
27. `WhatIfResult.findings` holds `fail` and `warn` findings (P1 ruling 14); P3 lists both with badges and its summaries count fails; P2's voice summary counts fails · P3 T16 prose, P2 R24 · the brief said "only failing".
28. R11's crossed element is `inputs.above` (P1 ruling 6); P3 already scans every string input, its WS1 note is corrected · P3 cross-workstream section · P3 asked for `inputs.over`.

**Verified, no change needed**
29. Approval `approver_name: "You (Demo Reviewer)"`, `role: "Reviewer"`; 429 bodies carry `detail`; `Citation.doc_id = "tender-hall-a"` (P2 `DOC_ID`, P1 `tender.yaml`); snake_case `model_url`, `check_summary`, `approver_name`, `heartbeat_at`; P3's `visibleEvents` implements the attempt rule; chips `rack_kw` 200/150, `liquid_fraction` 0.9, `dv_limit_pct` 1.5, `tx_loading_cap_pct` 35; option ids `2N/DR/BLOCK`; gates `plan/option/review`; project ids `hall-a, hall-b, pune-edge-1, grid-132kv, solar-5mwp, vindhya-lv`; opportunity `opp-hall-b`; revision refs `ws:{rev}` / `seed:{pid}@{rev}`.

**Open (not resolvable inside P2/P3)**
30. App Check for Playwright on the deployed build: `firebase.ts` enables the debug token only in `DEV`; WS4 and WS3 agree a production-safe switch through the controller, or e2e runs with `KIRCHHOFF_REQUIRE_APPCHECK` unset (see WS4 obligations).
31. The P4 plan file (`2026-10-13-p4-enterprise-demo-infra.md`) does not exist yet; `2026-10-13-ws4-obligations.md` is its input.

## Controller rulings after reconciliation (13 Oct)

- **App Check debug token for Playwright on the production build:** no change to `firebase.ts`. Playwright injects `self.FIREBASE_APPCHECK_DEBUG_TOKEN = '<registered debug token>'` with `page.addInitScript` before the app loads; the Firebase JS SDK honours that global in any build mode. WS4 registers the debug token via the App Check API and keeps it out of the repo (env var in the e2e runner).
- **`vindhya-lv` asset pack:** `datahall` (the contract has no "none"); the project is archived and read-only.
