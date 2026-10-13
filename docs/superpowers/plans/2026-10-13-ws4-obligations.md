# WS4 obligations — what the enterprise sandbox, demo world, infra, capture and e2e must provide (13 Oct)

Input for the WS4 plan (`2026-10-13-p4-enterprise-demo-infra.md`, not written yet). Collected from the P1 engine plan, the P2 agents/API plan, the P3 web plan and the reconciliation log in `2026-10-13-interfaces.md`. Where this file and a plan disagree, the reconciliation log decides; raise anything else with the controller.

WS4 owns (interfaces doc): `services/api/kirchhoff/enterprise/**`, `services/api/kirchhoff/api/enterprise_proxy.py`, `scenarios/demo_world/**`, `scenarios/hall_a/capture.py`, `infra/**`, `services/api/Dockerfile`, `.dockerignore`, `.gcloudignore`, `Makefile` deploy targets, `services/api/tests/enterprise/**`, `e2e/**`, and the generated files under `apps/web/public/demo/` listed in section 3 (never other `apps/web/**` files, and never `apps/web/public/demo/docs/`, which P3's `scripts/sync-demo-docs.mjs` fills and `.gitignore` excludes).

Contract rules that apply to everything below: Firestore documents and JSON files are Pydantic `model_dump()` output (snake_case), timestamps are unix seconds (float), finding ids are `"{rule}:{element}"`, and every number shown comes from the engine.

---

## 1. Enterprise sandbox client (consumed by P2)

**File:** `services/api/kirchhoff/enterprise/client.py` exporting `make_enterprise_client() -> EnterpriseClient`. P2 imports it lazily (`kirchhoff/api/deps.py`) and falls back to an in-process fake with a logged warning when the import fails.

**Protocol** (verbatim from P2 `kirchhoff/agents/ports.py`):
```python
class EnterpriseClient(Protocol):
    """WS4 provides kirchhoff.enterprise.client.make_enterprise_client() -> EnterpriseClient (no network at
    construction). All visitor data is scoped by uid."""

    def list_materials(self) -> list[Material]: ...
    def create_pr(self, uid: str, project_id: str, revision: str, lines: list[PRLine],
                  idempotency_key: str) -> PurchaseRequisition: ...
    def set_pr_status(self, uid: str, pr_id: str, status: str) -> None: ...
    def set_opportunity_stage(self, uid: str, opportunity_id: str, stage: str) -> CrmOverlay: ...
    def reset_visitor(self, uid: str) -> None: ...
```

Behaviour P2 relies on:
- No network call at construction (P2's `create_app` builds dependencies at import time; tests build the production app offline).
- `list_materials()` returns every ERP material (~60, section 3.3) as `Material` (`id, category, description, rating, unit, voltage, stock, lead_time_weeks, unit_price, vendor`). P2 caches it for 300 s per process and builds the engine's `ErpView` from it, so material ids must equal the catalogue ids the engine emits (`scenarios/hall_a/erp_seed.yaml` verbatim). Returns in < 3 s.
- `create_pr(...)` returns a `PurchaseRequisition` with `status="submitted"`, `project_id` and `revision` as passed (`"hall-b"`, `"{rid}-r{n}"`), ids `PR-2026-NNNN`, `created_at` unix seconds. **Idempotent by `idempotency_key`** (P2 passes `"{rid}:{rev}:{vendor}"`; a resumed P4 step must get the same PR back). P2 creates one PR per ERP vendor and mirrors each to `workspaces/{uid}/prs/{prid}`.
- `set_pr_status(uid, pr_id, "blocked")` is called when R12 fails on the submitted PRs (spec §6.2 P4 consistency failure).
- `set_opportunity_stage(uid, "opp-hall-b", "Design approved")` returns `CrmOverlay(opportunity_id, stage, updated_at)`; P2 mirrors it to `workspaces/{uid}/crm/opp-hall-b`.
- `reset_visitor(uid)` removes that visitor's PRs, idempotency keys and stage overlays (P2's `POST /api/workspace/reset` calls it, after deleting `workspaces/{uid}` and the visitor's blobs itself).
- All visitor data is keyed by uid; seed data is read-only.
- If the sandbox runs as the separate Cloud Run service `kirchhoff-enterprise` (spec §7: same image, min 0, max 2, Firestore-backed), the client makes HTTP calls with short timeouts (≤ 3 s each, P4 and `/api/enterprise/*` must stay < 10 s; a cold start of a min-0 service can exceed that — prefer reading seed data from Firestore directly, or min 1), the URL comes from an env var WS4 names, and the API's runtime service account gets `roles/run.invoker` on it if it is private.

Constants P2 uses: `HALL_B_OPPORTUNITY_ID = "opp-hall-b"`, `STAGE_DESIGN_APPROVED = "Design approved"`.

## 2. `/api/enterprise/*` proxy (consumed by P3)

**File:** `services/api/kirchhoff/api/enterprise_proxy.py` exporting `make_router(store, current_uid) -> fastapi.APIRouter`. P2's `create_app` includes it automatically when the module imports (`store` is the P0 `Store`; `current_uid` is the FastAPI dependency that verifies the Firebase ID token and, with `KIRCHHOFF_REQUIRE_APPCHECK=1`, the App Check token).

| Method | Path | Response (JSON) |
|---|---|---|
| GET | `/api/enterprise/erp/materials` | `Material[]` |
| GET | `/api/enterprise/erp/prs` | `PurchaseRequisition[]`: the ~15 seed PRs (incl. Hall A's) plus the calling visitor's PRs (`project_id: "hall-b"`, status `submitted` or `blocked`) |
| GET | `/api/enterprise/crm/opportunities` | `Opportunity[]` (`id, account, name, stage, value, next_step`) with the visitor's overlay applied (`opp-hall-b` → `"Design approved"` after their P4) |

Each call < 10 s (P3 aborts after 12 s). If any of the three fails, P3 renders `/demo/integrations.json` with "API unreachable — showing cached snapshot", so the shapes must equal the snapshot's `erp.materials`, `erp.prs` and `crm.opportunities`. The visitor overlay can be read from WS2's mirrors (`workspaces/{uid}/prs/*`, `workspaces/{uid}/crm/{oid}`) or from the sandbox; both must agree. P3's "Latest handoff" strip shows PRs whose `project_id` is `hall-a` or `hall-b`.

## 3. Static demo world (consumed by P3 in the browser and by P2 as seed bundles)

All files live under `apps/web/public/demo/` and are produced by deterministic generators in `scenarios/demo_world/` (fixed seed; same input → same JSON hash, spec §16).

### 3.1 `apps/web/public/demo/world.json`

Exactly P3's `World` type (`apps/web/src/lib/types.ts`):
```ts
/** Static demo world (`public/demo/world.json`, generated by WS4). */
export interface WorldPerson {
  id: string
  name: string
  role: string
  initials?: string
}
export interface WorldActivity {
  id: string
  ts: number // unix seconds
  actor: string
  project_id?: string | null
  text: string
}
export interface World {
  org: { name: string; tagline?: string }
  people: WorldPerson[]
  projects: Project[]
  activity: WorldActivity[]
}
```
`Project` is the contract (`kirchhoff/contracts/bundle.py`): `{id, name, client, asset_pack: "datahall"|"grid"|"solar", state: "not_started"|"running"|"in_review"|"checked"|"draft"|"signed"|"archived", sample: bool, updated_at}`.

Required content (spec §13): org "Meridian Power Engineering"; people Priya Raman (Lead Electrical Engineer, Reviewer), Arjun Mehta (Design Engineer), Kavya Iyer (Cooling Engineer), Rohan Das (Procurement Lead), Neha Kapoor (Account Manager); activity over the past 6 weeks. Projects, with these exact ids:

| id | name | client | asset_pack | state |
|---|---|---|---|---|
| `hall-a` | Deccan AI Campus · Hall A | Deccan Compute | datahall | signed |
| `hall-b` | Deccan AI Campus · Hall B | Deccan Compute | datahall | not_started |
| `pune-edge-1` | Konkan Cloud · Pune Edge Phase 1 | Konkan Cloud | datahall | signed |
| `grid-132kv` | Deccan campus · 132 kV intake | Narmada Transmission | grid | checked |
| `solar-5mwp` | Deccan campus · 5 MWp solar | Suryodaya Renewables | solar | draft |
| `vindhya-lv` | Vindhya Steel · Mill LV upgrade | Vindhya Steel | datahall (the contract has no "none") | archived |

### 3.2 `apps/web/public/demo/integrations.json`

Exactly P3's `IntegrationsSnapshot`:
```ts
/** Static integrations snapshot (`public/demo/integrations.json`, generated by WS4). */
export interface DocumentRecord {
  id: string
  project_id: string
  name: string
  kind: string // "tender" | "drawing" | "calc_report" | "boq" | ...
  url: string // public URL (e.g. /demo/docs/tender-hall-a.pdf)
  updated_at: number
}
export interface NotificationRecord {
  id: string
  ts: number
  kind: string // "approval" | "finding" | ...
  title: string
  body?: string
  project_id?: string | null
}
export interface IntegrationsSnapshot {
  synced_at?: number
  erp: { materials: Material[]; prs: PurchaseRequisition[] }
  crm: { opportunities: Opportunity[] }
  documents: DocumentRecord[]
  notifications: NotificationRecord[]
}
```
Content (spec §13.3): ~60 materials (incl. `erp_seed.yaml` verbatim: `TX-2500` stock 0 / 98 weeks, `TX-3150` stock 6, …), ~15 historical PRs including Hall A's (same ids as the Hall A bundle's `prs`, `project_id: "hall-a"`, `revision: "r2"`), 5 CRM accounts (Deccan Compute, Narmada Transmission, Suryodaya Renewables, Konkan Cloud, Vindhya Steel) and 9 opportunities across stages including `opp-hall-a` (`"Design approved"`) and `opp-hall-b` (a pre-approval stage such as `"Design in progress"`). Document URLs are public: the tender and drawing plot are `/demo/docs/tender-hall-a.pdf` and `/demo/docs/hall-a-plan.pdf` (P3 copies `scenarios/hall_a/out/*.pdf` there at build time); put any other published document (calc reports, BOQs) under `/demo/files/{pid}/…` (committed under `apps/web/public/demo/files/`).

### 3.3 Seed ERP/CRM for the API

Firestore `seed/erp_materials/{mid}`, `seed/erp_prs/{prid}`, `seed/crm_opportunities/{oid}` (spec §14; API read-only, not client-readable — the current `infra/firestore.rules` already deny it), loaded from the same generator output as `integrations.json`, so the API and the snapshot agree.

### 3.4 `apps/web/public/demo/projects/{pid}.json` — `ProjectBundle`

One file per world project except `hall-b` (P3 shows the start panel for Hall B). Contract (`kirchhoff/contracts/bundle.py`, generated into `apps/web/src/contracts/generated.ts`):
```python
class ProjectBundle(Strict):          # Strict = extra="forbid"
    project: Project
    brief: DesignBrief | None = None
    runs: list[RunRecord] = []
    steps: list[StepRecord] = []
    events: list[RunEvent] = []
    revisions: list[Revision] = []
    findings: dict[str, list[Finding]] = {}  # revision id -> findings
    approvals: list[Approval] = []
    prs: list[PurchaseRequisition] = []
    crm: CrmOverlay | None = None
    what_ifs: list[WhatIfResult] = []
```
Every bundle must validate with `ProjectBundle.model_validate_json` (strict: no extra keys anywhere): P2 loads the same files as seed bundles for `seed:{pid}@{rev}` what-ifs and explanations (section 4). Add a test in `services/api/tests/enterprise/` that validates every generated bundle.

**Hall A (`hall-a.json`, from `capture.py`, section 5):**
- `project` = the world's `hall-a` record; `runs` = one `RunRecord` (`id` e.g. `run-hall-a`, `project_id: "hall-a"`, `status: "done"`, `gate: null`, `lease: null`, `plan`, `open_questions` with `options: ["2N", "compare_all"]`, `options` (TopologyOption with `swaps`), `selected_option: "2N"`, `metrics`).
- `revisions`: `r1` (2 fails: `R05:FA-01`, `R11:H-Z2`) and `r2` (0 fails, `parent: "r1"`, `status: "signed"`), each with **`model` inline** (`model_url: null`), `hash = engine.model_hash(model)`, `check_summary`, `ledger`; sorted by `created_at`.
- `findings`: `{"r1": [...], "r2": [...]}`, every finding of the rule pack (passes included), with `fix`/`rejected_fix` (`{candidate, label, reason, criterion, agent, cost_delta, deltas}`) on r1's failing findings and `tender_refs` with pdfplumber `bbox` (WS2 writes both).
- `approvals`: one `Approval` with `revision: "r2"`, `approver_name: "Priya Raman"`, `role: "Lead Electrical Engineer (Reviewer)"`, `decision: "approved"`.
- `prs`: Hall A's PRs (`project_id: "hall-a"`, `revision: "r2"`), ids equal to the seed ERP PRs; `crm`: `{opportunity_id: "opp-hall-a", stage: "Design approved", updated_at}`.
- `brief`: the `DesignBrief` (requirements with verified citations `doc_id: "tender-hall-a"` and `bbox`, open question, `intake_score`, `drawing_check`).
- `steps` and `events`: the run's, with every event visible under the rule `steps/{event.step}.attempt == event.attempt` (drop the others) and `seq` renumbered 1…n. Artifact payloads: revision refs whose last path segment is the revision id (`r1`, `r2`), finding payloads with `rev`, export refs as public URLs (`/demo/files/hall-a/…`, files copied from GCS); the brief artifact ref is irrelevant for static bundles (the brief is inline).
- `what_ifs`: the five chips, computed with `engine.what_if(scn, r2_model, param, value, "seed:hall-a@r2", erp)` (P1 `engine/whatif.py: CHIP_WHAT_IFS`, `chip_what_ifs`): `("rack_kw", 200)`, `("rack_kw", 150)`, `("liquid_fraction", 0.9)`, `("dv_limit_pct", 1.5)`, `("tx_loading_cap_pct", 35)`; `revision_ref` exactly `"seed:hall-a@r2"`; `findings` are fail/warn only (P1 ruling 14).
- P3 also relies on: the earliest revision with a failing finding exists (tour step 3, cold-open shot needs an `R11` fail on r1 and its child r2), agents counted from `events` (tour step 4), `Revision.model.racks` etc. for the SLD and 3D views.

**Pune Edge (`pune-edge-1.json`):** a signed data-hall bundle (another captured run, rewritten to `project_id: "pune-edge-1"`, signed "2 weeks ago", PRs issued and present in the seed ERP PRs).

**Grid and solar (`grid-132kv.json`, `solar-5mwp.json`)** (P3 ruling R5, WS2 ruling R33): `project`, one `StepRecord` (e.g. `id: "asset.evaluate"`, `phase: "p1"`, `status: "done"`, `attempt: 1`) and events on that step: a `tool_call` (`payload {tool: "evaluate_grid"|"evaluate_solar", args: {}}`), then the **last** `tool_result` with `payload {tool: "evaluate_grid"|"evaluate_solar", summary: <the dict that POST /api/asset/{pack} returns>}` = `{options, recommended, findings (model_dump), geometry, choice: {option, reason, source}}` (generate it with `kirchhoff.agents.asset.run_asset_pack(deps, pack)` or the engine plus a template choice), then an `asset` `message` event whose title is the choice reason. Optional `summary.sld = {nodes: [{id, kind, label}], edges: [{src, dst, label?}]}`; without it P3 derives the grid's mini SLD from `geometry.nodes/edges`.

**Vindhya (`vindhya-lv.json`):** archived, read-only; a minimal valid bundle (project plus whatever history the generator authors). P3 shows explanatory empty states for missing parts.

P3's TypeScript for the asset result (for reference):
```ts
export interface AssetResult {
  options: Record<string, unknown>[]
  recommended: string
  findings: Finding[]
  geometry: Record<string, unknown>
  sld?: { nodes: { id: string; kind: string; label: string }[]; edges: { src: string; dst: string; label?: string }[] }
  /** The Asset agent's pick (WS2 ruling R33); `source: 'engine'` when the agent fell back to `recommended`. */
  choice?: { option: string; reason: string; source: 'agent' | 'engine' }
}
```

## 4. API image, env vars and deploy (consumed by P1/P2 at runtime)

**Image contents** (`services/api/Dockerfile`; today it builds from `services/api` only, so the build context or deploy script must change):
- `/app/kirchhoff` (code) and `/app/.venv` built inside the image (`uv sync --frozen --no-dev`); never upload a local `.venv` (`.gcloudignore`/`.dockerignore`).
- `/app/scenarios` = repo `scenarios/`: `hall_a/{tender,catalogue,geometry,erp_seed}.yaml`, `hall_a/ground_truth.yaml`, `hall_a/out/{tender-hall-a.pdf, hall-a.dxf, hall-a-plan.pdf}` (P2 reads these for every Hall B run; there is no upload route), `grid/grid.yaml`, `solar/solar.yaml`.
- `/app/seed/{pid}.json` = copies of `apps/web/public/demo/projects/*.json` (P2 `load_seed_bundle(seed_dir, pid)`).
- P2's defaults resolve `/app/scenarios` and `/app/seed` from the code location; set `KIRCHHOFF_SCENARIOS_DIR` / `KIRCHHOFF_SEED_DIR` only if the layout differs.

**Cloud Run `kirchhoff-api` env:** `GOOGLE_CLOUD_PROJECT=ordinal-mep`, `GOOGLE_GENAI_USE_VERTEXAI=true`, `GOOGLE_CLOUD_LOCATION=global` (already in `infra/deploy_api.sh`); `KIRCHHOFF_REQUIRE_APPCHECK=1` in production (see section 7 for e2e). Never set `KIRCHHOFF_FAKES`, `KIRCHHOFF_BLOBS`, `KIRCHHOFF_RECORD_DIR` in production (local development only); `KIRCHHOFF_AGENT_BACKEND=genai` is P2's fallback switch if ADK misbehaves. Keep `--no-cpu-throttling --min-instances=1 --max-instances=3 --concurrency=20 --cpu=2 --memory=2Gi` (phases run in background threads after the 202).

**Dependencies:** P2 adds `python-multipart>=0.0.20` to `services/api/pyproject.toml` (Task 16); request any WS4 additions through the controller.

**Deploy guard:** deploy only when no run holds a live lease: `ops/live_runs` has no `runs` entry with `now - heartbeat_at < 60` (spec §6.2, §11). Freeze Thu 16 Oct 22:00 IST.

**Smoke (`infra/smoke.sh`, unchanged):** `GET /api/health` → `{"ok":true,…}`, `/` contains `<div id="root">`, `GET /api/whoami` → 401 without a token (permanent route; P2 keeps it).

## 5. `scenarios/hall_a/capture.py` (golden capture, spec §11)

Reads one completed Hall B run (visitor `uid`, run `rid`) and writes the Hall A bundle (section 3.4) plus the inputs the demo-world generator needs:
- Run doc `workspaces/{uid}/runs/{rid}`, `…/steps/*`, `…/events/*` (ordered by `seq`).
- Brief: **`workspaces/{uid}/runs/{rid}/outputs/p1.intake`** = `{step, json}`; `json.loads(doc["json"])["brief"]` (a `{step, blob, sha256}` doc means the JSON is in GCS at `doc["blob"]`).
- Revisions: `workspaces/{uid}/revisions/*` whose id starts with `{rid}-r` (`{rid}-r1`, `{rid}-r2`, …), their `findings/*` subcollections; models from GCS **`workspaces/{uid}/revisions/{rev}/model.json`** (bucket `ordinal-mep.firebasestorage.app`; revision docs carry `model: null`, `model_url: "revisions/{rev}/model.json"`).
- Approvals `workspaces/{uid}/approvals/*` (`revision` = the signed revision), PRs `workspaces/{uid}/prs/*`, CRM `workspaces/{uid}/crm/opp-hall-b`, exports `workspaces/{uid}/exports/{rev}/{calc-report.pdf, boq.csv}`.
- Rewrites: `project_id` `hall-b` → `hall-a`; revision ids `{rid}-rN` → `rN` everywhere (`Revision.id/parent`, `findings` keys, `Approval.revision`, `PurchaseRequisition.revision`, event `artifact` refs and `finding` `rev`); run id; approver Priya Raman / "Lead Electrical Engineer (Reviewer)"; `opp-hall-b` → `opp-hall-a`; all timestamps shifted onto Hall A's timeline; inline every `model`; recompute every `hash` with `engine.model_hash` (P2 ruling R22: P2 already uses it, so the values must match); compute the five `what_ifs`.
- Deterministic: the same Hall B run gives the same Hall A bundle and integrations snapshot hash (spec §16).

## 6. Infra: IAM, Storage CORS, Firestore, Hosting, monitoring

**IAM for the API runtime service account** (default `${PROJECT_NUMBER}-compute@developer.gserviceaccount.com` unless WS4 creates a dedicated one):
- `roles/iam.serviceAccountTokenCreator` **on itself** (V4 signed URLs are signed through IAM `signBlob` on Cloud Run; P2 Task 18 Step 5 has the command).
- `roles/datastore.user` (Firestore), `roles/storage.objectAdmin` on `ordinal-mep.firebasestorage.app` (models, outputs > 400 KB, exports, `delete_prefix` on reset), `roles/aiplatform.user` (Vertex Gemini via ADK/google-genai).
- `roles/run.invoker` on `kirchhoff-enterprise` if the client calls it over private HTTP.

**Storage CORS** (P3 ruling R19: the browser calls `GET /api/files/{path}?redirect=0` → `{url}`, then a plain `fetch(url)` with no custom headers, so no preflight, but the response needs `Access-Control-Allow-Origin`), e.g. `infra/storage-cors.json`:
```json
[{"origin": ["https://kirchhoff.web.app", "https://kirchhoff.firebaseapp.com", "http://localhost:5173"],
  "method": ["GET"], "responseHeader": ["Content-Type", "Content-Disposition"], "maxAgeSeconds": 3600}]
```
`gcloud storage buckets update gs://ordinal-mep.firebasestorage.app --cors-file=infra/storage-cors.json --project=ordinal-mep`

**Firestore:** rules as in `infra/firestore.rules` (clients read only `workspaces/{uid}/**`; `seed/*` and `ops/*` server-only; all client writes denied). P3's queries need only automatic single-field indexes: `runs/{rid}/events` ordered by `seq`, `revisions` where `project_id ==`, `prs` where `project_id ==`. Server-only docs: `ops/live_runs` (`{runs: {"{uid}__{rid}": heartbeat_at}}`, global cap of 3).

**Hosting** (`infra/firebase.json`): keep the `/api/**` → `kirchhoff-api` (asia-south1) rewrite, the SPA fallback and the `/demo/**` cache header; `public_dist` must be the web build including `public/demo/**` (WS4 files plus P3's synced `demo/docs/*.pdf`).

**Monitoring:** uptime checks on `/` and `/api/health`; budget USD 200 with 50%/90% alerts.

## 7. Playwright e2e (`e2e/**`, spec §16)

Flow on the deployed URL (https://kirchhoff.web.app): welcome → tour → Hall A finding → what-if → Integrations → Hall B live run through all gates → sign-off → PR visible. Each browser context signs in anonymously as a new visitor; respect the limits (≤ 3 concurrent live runs globally, 5 runs per visitor per hour).

**App Check:** `apps/web/src/firebase.ts` (WS3) enables the debug token only in `DEV` builds (`VITE_APPCHECK_DEBUG_TOKEN`). For e2e on the production build either agree a production-safe switch with WS3 through the controller (e.g. honour `VITE_APPCHECK_DEBUG_TOKEN` in a dedicated e2e build), or run e2e against a deployment with `KIRCHHOFF_REQUIRE_APPCHECK` unset. Register the debug token in the Firebase console (App Check → Manage debug tokens).

**Selectors P3 guarantees** (accessible names are exact):
- Landing `/`: link "Enter the demo workspace (no login)"; "Run it live"; "Replay a recorded run".
- Every `/app` page: `role=note` "Demo workspace — all companies, people and data are fictional".
- Welcome dialog: buttons "Take the 2-minute tour", "Explore on my own". Tour: buttons "Next", "Skip tour"; anchors `[data-tour="projects"]`, `"matrix-row"`, `"tender-chip"`, `"lanes"`, `"whatif-chip"`, `"integrations-prs"`, `"hall-b"`; also `"plan-gate"`, `"options"`, `"autonomy"`, `"sign-off"`, `"tab-hall"|"tab-sld"|"tab-matrix"|"tab-options"|"tab-docs"`. Checklist region "Getting started".
- Workspace `/app/p/hall-a`: `table[aria-label="Compliance matrix"]`; matrix cell buttons named `"{rule} {element}: {Status}"` (e.g. "R05 FA-01: Fail"); tender chips "Open tender {clause} · p.{page}" (e.g. "Open tender §4.6 · p.4"); PDF highlight `[data-testid="citation-highlight"]`; value bar `role=img` "Value {v} against limit {l}: {Status}"; what-if chip "Racks → 200 kW" (first chip carries `data-tour="whatif-chip"`), lists "What-if failures" and "Impact chain"; replay `/app/p/hall-a?replay=1` with "Time-compressed replay of a recorded run" and buttons "Pause replay"/"Play replay".
- Integrations `/app/integrations`: region "Latest handoff" (`data-tour="integrations-prs"`); status "API unreachable — showing cached snapshot" when the proxy fails.
- Hall B `/app/p/hall-b`: autonomy radios "Ask: pause at every gate" / "Auto: resolve plan and option gates by the tender's rules"; button "Start live run" (URL becomes `?run={rid}`); run bar text "Waiting for you · plan gate"; `section[aria-label="Plan"]` with radios named by option ("2N", "Compare all three topologies") and button "Approve plan"; option cards `article[aria-label="Option 2N"]` with button "Select 2N"; header button "Review and sign" (`data-tour="sign-off"`).
- Review `/app/p/hall-b/review/{rev}?run={rid}`: textbox "Review comment"; button "Approve and sign as You (Demo Reviewer)" (enabled only on the latest revision with no failing finding); `figure[aria-label="Approval stamp"]` reading "You (Demo Reviewer)" / "Reviewer"; region "Handoff" listing the PR ids and "CRM opportunity moved to Design approved".
- Grid/solar `/app/p/grid-132kv`, `/app/p/solar-5mwp`: `table[aria-label="Asset options"]`, button "Re-run with the engine", region "Mini SLD" (grid).
- Do not use `?present=1` in e2e (it hides onboarding chrome).

## 8. Summary checklist

- [ ] `kirchhoff/enterprise/client.py: make_enterprise_client()` — protocol, idempotent `create_pr`, uid scoping, `reset_visitor`, no network at construction.
- [ ] `kirchhoff/api/enterprise_proxy.py: make_router(store, current_uid)` — three GET routes, visitor overlay, < 10 s.
- [ ] `scenarios/demo_world/` generators → `world.json`, `integrations.json`, `projects/{hall-a,pune-edge-1,grid-132kv,solar-5mwp,vindhya-lv}.json`, Firestore `seed/*`; deterministic; every bundle passes strict `ProjectBundle` validation.
- [ ] `scenarios/hall_a/capture.py` — brief from the `p1.intake` outputs doc, models from GCS, id/author/timestamp rewrites, recomputed hashes, five chip what-ifs, PR ids shared with the ERP seed.
- [ ] Image with `/app/scenarios` and `/app/seed`; env as section 4; deploy guard on `ops/live_runs`.
- [ ] IAM (token creator on self, Firestore, Storage, Vertex), bucket CORS, Firestore/Storage rules, Hosting rewrites, uptime checks, budget.
- [ ] Playwright e2e with an agreed App Check approach and the selectors above.
