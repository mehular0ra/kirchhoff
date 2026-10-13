# Kirchhoff — cross-workstream interfaces (binding for plans P1–P4)

Spec: `docs/superpowers/specs/2026-10-13-kirchhoff-design.md` (v4). Contracts: `services/api/kirchhoff/contracts/` as defined in `docs/superpowers/plans/2026-10-13-p0-foundation.md` Task 2 (frozen; plans may only **add** optional fields or **new** models in `kirchhoff/contracts/extra.py`).

## Ownership

| Workstream | Plan file | Owns (create/modify only these) |
|---|---|---|
| WS1 engine + scenario | `2026-10-13-p1-engine.md` | `services/api/kirchhoff/engine/**`, `services/api/tests/engine/**`, `scenarios/hall_a/{tender.yaml,catalogue.yaml,geometry.yaml,erp_seed.yaml}`, `scenarios/grid/**`, `scenarios/solar/**`, `services/api/kirchhoff/contracts/extra.py` |
| WS2 agents + API | `2026-10-13-p2-agents-api.md` | `services/api/kirchhoff/agents/**`, `services/api/kirchhoff/runs/**`, `services/api/kirchhoff/api/**` (except `enterprise_proxy.py`), `services/api/kirchhoff/intake/**`, `scenarios/hall_a/{render_tender_pdf.py,render_drawing.py,ground_truth.yaml}`, generated `scenarios/hall_a/out/*`, `services/api/tests/{agents,runs,api,intake}/**` |
| WS3 web UI | `2026-10-13-p3-web.md` | `apps/web/**` |
| WS4 enterprise + demo world + infra | `2026-10-13-p4-enterprise-demo-infra.md` | `services/api/kirchhoff/enterprise/**`, `services/api/kirchhoff/api/enterprise_proxy.py`, `scenarios/demo_world/**`, `scenarios/hall_a/capture.py`, `infra/**`, `services/api/tests/enterprise/**`, Playwright tests in `e2e/**` |

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

- `scenarios/hall_a/tender.yaml` (WS1, Monday): clause list `[{id: "§4.6", title, text, page, limits: {...}}]` — single source for the tender PDF (WS2 renders it) and for engine limits. Includes the deliberate contradiction (§4.2 vs Appendix B) and §2.3 (26 weeks).
- `scenarios/hall_a/erp_seed.yaml` (WS1): the Hall A materials (incl. 2.5 MVA: stock 0, 98 weeks; 3.15 MVA: stock 6). WS4's demo-world generator includes these verbatim in the ~60-material ERP.
- `scenarios/hall_a/out/` (WS2 generates): `tender-hall-a.pdf`, `hall-a.dxf`, `hall-a-plan.pdf`.

## HTTP API (WS2 produces except /api/enterprise/*; WS3 consumes)

All under `/api`, Firebase ID token required except `/api/health`; JSON bodies; every call returns < 10 s.

| Method | Path | Body → Response |
|---|---|---|
| GET | `/api/health` | → `{ok, version}` |
| POST | `/api/workspace` | → `{uid, created: bool}` |
| POST | `/api/workspace/reset` | → `{ok}` |
| POST | `/api/runs` | `{project_id: "hall-b", autonomy: "ask"\|"auto"}` → 202 `{run_id}` (starts P1) |
| POST | `/api/runs/{rid}/gates/plan` | `{answers: {question_id: resolution}, plan_notes: {step_id: note}}` → 202 (starts P2) |
| POST | `/api/runs/{rid}/gates/option` | `{option_id: "2N"\|"DR"\|"BLOCK"}` → 202 (starts P3) |
| POST | `/api/runs/{rid}/gates/review` | `{decision: "approved"\|"rejected", comment}` → 202 (starts P4 if approved) |
| POST | `/api/runs/{rid}/resume` | → 202 `{resumed: bool}` |
| POST | `/api/what-if` | `{revision_ref, param, value}` → `WhatIfResult` |
| POST | `/api/explain` | `{revision_ref, finding_id}` → `{text}` |
| POST | `/api/voice` | multipart audio (webm/ogg) → `{transcript, answer, tool_results}` |
| POST | `/api/asset/{pack}` | `pack ∈ {grid, solar}` → asset-pack result dict |
| GET | `/api/enterprise/erp/materials` | (WS4) → `Material[]` |
| GET | `/api/enterprise/erp/prs` | (WS4) → `PurchaseRequisition[]` (seed + visitor) |
| GET | `/api/enterprise/crm/opportunities` | (WS4) → `Opportunity[]` with visitor overlay applied |
| GET | `/api/files/{path}` | → 302 to a signed URL for the visitor's export |

Firestore paths written by WS2 (read by WS3 via onSnapshot): spec §14 (`workspaces/{uid}/runs/{rid}`, `/steps/{stepId}`, `/events/{seq:06d}`, `workspaces/{uid}/revisions/{rev}`, `/findings/{fid}`, `workspaces/{uid}/approvals/{aid}`, `workspaces/{uid}/prs/{prid}`, `workspaces/{uid}/crm/{oid}`).

Static demo files (WS4 generates; WS3 consumes): `apps/web/public/demo/world.json` (`{org, people, projects: Project[], activity: [...]}`), `apps/web/public/demo/projects/{pid}.json` (`ProjectBundle`), `apps/web/public/demo/integrations.json` (`{erp: {materials, prs}, crm: {opportunities}, documents: [...], notifications: [...]}`).

## Event vocabulary (WS2 emits; WS3 renders)

`RunEvent.kind` values and payload shapes:
- `status`: `{}` — lane status line.
- `plan`: `{plan: PlanStep[], open_questions: OpenQuestion[]}`.
- `tool_call`: `{tool: str, args: dict}`; `tool_result`: `{tool: str, summary: dict}`.
- `artifact`: `{type: "brief"|"options"|"revision"|"export", ref: str}` — UI fetches/reads the referenced doc.
- `finding`: `{finding_id, rule_id, element_id, status}`.
- `gate`: `{gate: "plan"|"option"|"review"}`.
- `ledger`: `{entry: LedgerEntry}`.
- `message`: `{}` — narration text in `title`/`detail` (digits only via allowlist, spec §6.3).
