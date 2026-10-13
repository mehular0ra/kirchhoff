# Kirchhoff P0 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A scaffolded monorepo with frozen shared contracts (Pydantic → TypeScript) and a hello-world that runs end to end in production: browser (Firebase Hosting, anonymous auth) → `/api` (Cloud Run) → Firestore event stream rendered live in the browser.

**Architecture:** Python 3.12 FastAPI service in `services/api` (package `kirchhoff`) deployed to Cloud Run `kirchhoff-api` (asia-south1); React + Vite + TypeScript app in `apps/web` deployed to Firebase Hosting site `kirchhoff` with `/api/**` rewritten to Cloud Run. All cross-workstream data shapes live in `kirchhoff/contracts/` and are exported to `apps/web/src/contracts/generated.ts`.

**Tech Stack:** Python 3.12, uv, FastAPI 0.141, pydantic 2.14, firebase-admin 7.7, google-cloud-firestore 2.34, pytest; Node 26, Vite 8, React 19, TypeScript, Firebase JS SDK 13, vitest 5, json-schema-to-typescript 16.

**Spec:** `docs/superpowers/specs/2026-10-13-kirchhoff-design.md` (v4). Read sections 6.2, 7, 13.4 and 14 before starting.

## Global Constraints

- GCP project `ordinal-mep`. Always pass `--project=ordinal-mep` to gcloud; never run `gcloud config set project` (the user's default project is another project).
- Every process that calls Google APIs locally sets: `GOOGLE_CLOUD_PROJECT=ordinal-mep GOOGLE_CLOUD_QUOTA_PROJECT=ordinal-mep GOOGLE_GENAI_USE_VERTEXAI=true GOOGLE_CLOUD_LOCATION=global`.
- Cloud Run region `asia-south1`; Firestore `(default)` in asia-south1 (exists); bucket `ordinal-mep.firebasestorage.app` (exists).
- Hosting site id `kirchhoff` (→ https://kirchhoff.web.app, exists). Firebase web appId `1:1015632998221:web:c98110f2fc88424da81104`. App Check reCAPTCHA Enterprise site key `6LdBw-wtAAAAALNbcALgFtPxNx9lcvnK_q2HuERk`.
- Fresh code only: everything in this repo is written from scratch during the hackathon. Do not copy code from other repositories.
- Git identity: use the machine's global git config (do not pass `-c user.*`). End commit messages with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Every `/api` call must return in < 10 s (Firebase Hosting rewrites time out at 60 s). Long work runs in background threads.
- Clients never write Firestore directly; all mutations go through `/api`.
- Do not spawn subagents from inside a task.

---

## File Structure

```
kirchhoff/
  README.md                         project overview + how to run
  .gitignore
  Makefile                          dev, test, gen-types, deploy-api, deploy-web targets
  services/api/
    pyproject.toml                  uv project, deps, pytest config
    Dockerfile                      Cloud Run image
    kirchhoff/__init__.py
    kirchhoff/contracts/__init__.py re-exports all models
    kirchhoff/contracts/common.py   literals, Citation, ClauseRef
    kirchhoff/contracts/design.py   DesignModel and parts (engine ↔ UI)
    kirchhoff/contracts/run.py      RunEvent, PlanStep, OpenQuestion, Requirement, DesignBrief, TopologyOption, RunRecord, StepRecord
    kirchhoff/contracts/checks.py   Finding, LedgerEntry, Revision, WhatIfResult
    kirchhoff/contracts/enterprise.py  Material, PRLine, PurchaseRequisition, Opportunity, CrmOverlay
    kirchhoff/contracts/bundle.py   Project, Approval, ProjectBundle
    kirchhoff/contracts/export_schema.py  writes JSON Schema for TS generation
    kirchhoff/store/__init__.py
    kirchhoff/store/events.py       EventWriter (batched, seq-assigning) over a Store protocol
    kirchhoff/store/firestore.py    Firestore implementation of Store
    kirchhoff/store/memory.py       in-memory Store for tests
    kirchhoff/api/__init__.py
    kirchhoff/api/app.py            FastAPI app factory, /api/health
    kirchhoff/api/auth.py           Firebase ID token (+ optional App Check) verification dependency
    kirchhoff/api/hello.py          /api/hello-run (P0 only; removed in P2 plan)
    tests/test_contracts.py
    tests/test_events.py
    tests/test_api_hello.py
  apps/web/
    package.json, vite.config.ts, tsconfig.json, index.html
    src/main.tsx, src/App.tsx
    src/firebase.ts                 app, auth (anonymous), firestore, app check init
    src/contracts/generated.ts      GENERATED — do not edit
    src/hello/HelloRun.tsx          P0 demo screen
    src/hello/HelloRun.test.tsx
  infra/
    firebase.json                   hosting (site kirchhoff) + rewrites; firestore/storage rules paths
    .firebaserc
    firestore.rules
    storage.rules
    deploy_api.sh
    deploy_web.sh
```

---

### Task 1: Repository skeleton and toolchains

**Files:**
- Create: `README.md`, `.gitignore`, `Makefile`, `services/api/pyproject.toml`, `services/api/kirchhoff/__init__.py`, `services/api/tests/test_smoke.py`, `apps/web/*` (Vite React TS scaffold)

**Interfaces:**
- Produces: `make test` runs `pytest` in `services/api` and `vitest run` in `apps/web`; `uv run` works in `services/api`.

- [ ] **Step 1: Create the Python project**

`services/api/pyproject.toml`:
```toml
[project]
name = "kirchhoff"
version = "0.1.0"
requires-python = ">=3.12,<3.13"
dependencies = [
  "fastapi==0.141.1",
  "uvicorn[standard]==0.54.0",
  "pydantic==2.14.1",
  "firebase-admin==7.7.0",
  "google-cloud-firestore==2.34.1",
  "google-cloud-storage>=2.18",
  "google-adk==2.11.0",
  "google-genai>=2.30.0",
  "pandapower==3.5.6",
  "networkx==3.7",
  "shapely==2.2.0",
  "numpy>=2.1",
  "pyyaml==6.0.3",
  "pdfplumber==0.11.10",
  "reportlab==5.0.1",
  "ezdxf==1.4.4",
  "httpx>=0.28",
]

[dependency-groups]
dev = ["pytest>=8.3", "pytest-asyncio>=0.25"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["kirchhoff"]
```

`services/api/kirchhoff/__init__.py`:
```python
"""Kirchhoff: AI designs. Physics checks. An engineer signs."""
```

`services/api/tests/test_smoke.py`:
```python
import kirchhoff


def test_package_imports():
    assert kirchhoff.__doc__.startswith("Kirchhoff")
```

- [ ] **Step 2: Sync and run the Python smoke test**

Run: `cd services/api && uv sync --python 3.12 && uv run pytest -q`
Expected: `1 passed`

- [ ] **Step 3: Scaffold the web app**

Run: `cd apps && npm create vite@8 web -- --template react-ts && cd web && npm i && npm i firebase@13 && npm i -D vitest@5 @testing-library/react @testing-library/jest-dom jsdom json-schema-to-typescript@16`

Add to `apps/web/package.json` scripts: `"test": "vitest run"`, `"gen-types": "json2ts -i ../../services/api/build/schema.json -o src/contracts/generated.ts --bannerComment '/* GENERATED from services/api/kirchhoff/contracts — do not edit */'"`.

`apps/web/vite.config.ts`:
```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://localhost:8080' } },
  test: { environment: 'jsdom', globals: true, setupFiles: ['./src/test-setup.ts'] },
})
```

`apps/web/src/test-setup.ts`:
```ts
import '@testing-library/jest-dom/vitest'
```

- [ ] **Step 4: Root files**

`.gitignore`:
```
node_modules/
dist/
.venv/
__pycache__/
*.pyc
services/api/build/
.env*
!.env.example
.firebase/
*.log
```

`Makefile`:
```make
.PHONY: test gen-types dev-api dev-web
test:
	cd services/api && uv run pytest -q
	cd apps/web && npm test
gen-types:
	cd services/api && uv run python -m kirchhoff.contracts.export_schema build/schema.json
	cd apps/web && npm run gen-types
dev-api:
	cd services/api && GOOGLE_CLOUD_PROJECT=ordinal-mep GOOGLE_CLOUD_QUOTA_PROJECT=ordinal-mep GOOGLE_GENAI_USE_VERTEXAI=true GOOGLE_CLOUD_LOCATION=global uv run uvicorn kirchhoff.api.app:create_app --factory --port 8080 --reload
dev-web:
	cd apps/web && npm run dev
```

`README.md`: one paragraph describing Kirchhoff (copy the spec's one-liner and tagline), then "Run locally: `make dev-api` and `make dev-web`; tests: `make test`".

- [ ] **Step 5: Run all tests**

Run: `make test`
Expected: pytest `1 passed`; vitest reports "No test files found" is acceptable at this step only if the command exits 0 — add `"test": "vitest run --passWithNoTests"` until Task 4 adds a test.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "chore: scaffold monorepo (api + web)

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Shared contracts (frozen) and TypeScript generation

These models are the single source of truth for every workstream. Field names are final; later plans may only **add optional fields** with defaults.

**Files:**
- Create: `services/api/kirchhoff/contracts/{__init__,common,design,run,checks,enterprise,bundle,export_schema}.py`
- Create: `services/api/tests/test_contracts.py`
- Create (generated): `apps/web/src/contracts/generated.ts`

**Interfaces:**
- Produces: every class below, importable as `from kirchhoff.contracts import <Name>`; TS interfaces of the same names in `apps/web/src/contracts/generated.ts`.

- [ ] **Step 1: Write the failing contract tests**

`services/api/tests/test_contracts.py`:
```python
import json
from pathlib import Path

from kirchhoff.contracts import (
    Citation, ClauseRef, DesignModel, Equipment, Connection, Rack, Point3, Geometry,
    CoolingNode, Pipe, RunEvent, Finding, Revision, LedgerEntry, ProjectBundle, Project,
    TopologyOption, RunRecord, WhatIfResult, PurchaseRequisition, PRLine, Material,
)
from kirchhoff.contracts.export_schema import build_schema


def _model() -> DesignModel:
    return DesignModel(
        topology="2N",
        racks=[Rack(id="R1-01", row="R1", x=6.0, y=15.9, kw=132.0, liquid_fraction=0.8, feeds=("A-01", "B-01"))],
        equipment=[Equipment(id="A1", kind="lv_board", rating=3150.0, unit="kVA", system="A", room="A")],
        connections=[Connection(id="FA-01", src="A1", dst="A-01", kind="busway", length_m=82.0,
                                route=[Point3(x=66, y=4, z=3.2), Point3(x=6, y=2, z=3.2)])],
        cooling_nodes=[CoolingNode(id="CDU-1", kind="cdu", zone="Z1", capacity_kw=1200.0, x=8.0, y=30.0)],
        pipes=[Pipe(id="H-Z1", kind="header", zone="Z1", dn=200, tier="pipe_high",
                    route=[Point3(x=8, y=30, z=3.8), Point3(x=8, y=22, z=3.8)])],
        geometry=Geometry(hall=(60.0, 36.0), columns=[(0.0, 0.0)], keepouts=[(10.0, 10.0, 18.0, 26.0)],
                          rooms={"A": (60.0, 0.0, 72.0, 10.0)}, tiers={"pipe_low": 2.6, "busway": 3.2, "pipe_high": 3.8}),
        loads={"rack_kw": 132.0, "liquid_fraction": 0.8, "aux_mw": 0.30, "pumps_kw": 135.0},
    )


def test_design_model_round_trip():
    m = _model()
    again = DesignModel.model_validate_json(m.model_dump_json())
    assert again == m


def test_finding_requires_rule_and_status():
    f = Finding(id="R05:FA-01", rule_id="R05", element_id="FA-01", status="fail", title="Voltage drop",
                clause_refs=[ClauseRef(standard="IEC 60364-5-52", clause="§525")],
                tender_refs=[Citation(doc_id="tender-hall-a", page=4, quote="shall not exceed 2.0%", clause="§4.6")],
                formula="ΔU% = 100·√3·I·L·(R cosφ + X sinφ)/U", inputs={"I_A": 1546.0, "L_m": 82.0},
                value=2.16, limit=2.0, unit="%", explanation="{value} exceeds {limit}")
    assert f.status == "fail"


def test_bundle_round_trip_and_defaults():
    b = ProjectBundle(project=Project(id="hall-a", name="Deccan AI Campus · Hall A", client="Deccan Compute",
                                      asset_pack="datahall", state="signed", sample=True, updated_at=0.0))
    again = ProjectBundle.model_validate_json(b.model_dump_json())
    assert again.events == [] and again.revisions == [] and again.what_ifs == []


def test_schema_export_contains_all_top_level_models(tmp_path: Path):
    out = tmp_path / "schema.json"
    build_schema(out)
    schema = json.loads(out.read_text())
    for name in ["ProjectBundle", "DesignModel", "RunEvent", "Finding", "Revision", "RunRecord",
                 "TopologyOption", "WhatIfResult", "PurchaseRequisition", "Material"]:
        assert name in schema["$defs"], name
```

- [ ] **Step 2: Run to verify failure**

Run: `cd services/api && uv run pytest tests/test_contracts.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'kirchhoff.contracts'`

- [ ] **Step 3: Implement the contracts**

`services/api/kirchhoff/contracts/common.py`:
```python
from typing import Literal

from pydantic import BaseModel, ConfigDict

AgentName = Literal["intake", "orchestrator", "layout", "power", "cooling", "procurement",
                    "checker", "docs", "copilot", "asset", "system"]
Phase = Literal["p1", "p2", "p3", "p4"]
EventKind = Literal["plan", "tool_call", "tool_result", "message", "artifact", "finding", "gate",
                    "ledger", "status"]
FindingStatus = Literal["pass", "fail", "warn", "n/a"]
TopologyId = Literal["2N", "DR", "BLOCK"]
AssetPack = Literal["datahall", "grid", "solar"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Citation(Strict):
    doc_id: str
    page: int
    quote: str
    bbox: tuple[float, float, float, float] | None = None  # pdfplumber coords: x0, top, x1, bottom (points)
    clause: str | None = None  # e.g. "§4.6"


class ClauseRef(Strict):
    standard: str  # e.g. "IEC 60364-5-52"
    clause: str | None = None  # e.g. "§525"
```

`services/api/kirchhoff/contracts/design.py`:
```python
from typing import Literal

from .common import Strict, TopologyId


class Point3(Strict):
    x: float
    y: float
    z: float


class Rack(Strict):
    id: str  # "R1-01"
    row: str  # "R1"
    x: float  # centre, metres
    y: float
    w: float = 0.6
    d: float = 1.2
    kw: float
    liquid_fraction: float
    feeds: tuple[str, str]  # (A busway id, B busway id)


EquipmentKind = Literal["mv_board", "transformer", "lv_board", "ups", "critical_board", "sts",
                        "busway", "rack_group"]


class Equipment(Strict):
    id: str  # "T-A1", "A1", "UPS-A1", "CB-A1", "A-01"
    kind: EquipmentKind
    rating: float | None = None
    unit: str | None = None  # "kVA", "A", "kW"
    catalogue_id: str | None = None
    system: str | None = None  # "A"/"B" (2N), "S1".."S4" (DR), "K1".."K3","KR" (BLOCK)
    room: str | None = None  # "A" | "B"
    params: dict[str, float | str] = {}


class Connection(Strict):
    id: str  # feeders "FA-01", internal links "L-T-A1-A1"
    src: str
    dst: str
    kind: Literal["cable", "busway", "internal"]
    length_m: float = 0.0
    catalogue_id: str | None = None
    route: list[Point3] = []


class CoolingNode(Strict):
    id: str  # "CDU-1", "M-R1"
    kind: Literal["cdu", "manifold"]
    zone: str  # "Z1".."Z3"
    capacity_kw: float | None = None
    x: float
    y: float


class Pipe(Strict):
    id: str  # "H-Z2", "BR-R3"
    kind: Literal["header", "branch"]
    zone: str
    dn: int
    tier: Literal["pipe_low", "pipe_high"]
    route: list[Point3]
    flow_lps: float = 0.0


class Geometry(Strict):
    hall: tuple[float, float]  # (60, 36)
    columns: list[tuple[float, float]]
    keepouts: list[tuple[float, float, float, float]]  # (x0, y0, x1, y1)
    rooms: dict[str, tuple[float, float, float, float]]
    tiers: dict[str, float]  # {"pipe_low": 2.6, "busway": 3.2, "pipe_high": 3.8}


class DesignModel(Strict):
    topology: TopologyId
    racks: list[Rack]
    equipment: list[Equipment]
    connections: list[Connection]
    cooling_nodes: list[CoolingNode]
    pipes: list[Pipe]
    geometry: Geometry
    loads: dict[str, float]  # rack_kw, liquid_fraction, aux_mw, pumps_kw
```

`services/api/kirchhoff/contracts/run.py`:
```python
from typing import Any, Literal

from .common import AgentName, Citation, EventKind, Phase, Strict, TopologyId


class Requirement(Strict):
    id: str  # "REQ-4.6"
    text: str
    value: float | str | None = None
    unit: str | None = None
    citation: Citation
    verified: bool


class OpenQuestion(Strict):
    id: str  # "Q-redundancy"
    text: str
    options: list[str]
    citations: list[Citation]
    default_resolution: str  # used by Auto mode (main body beats appendix)
    resolution: str | None = None


class DesignBrief(Strict):
    project_id: str
    requirements: list[Requirement]
    open_questions: list[OpenQuestion] = []
    intake_score: dict[str, float] = {}  # extracted, verified, recall_vs_ground_truth
    drawing_check: dict[str, Any] = {}  # {"agrees": bool, "differences": [...]}


class PlanStep(Strict):
    id: str
    agent: AgentName
    title: str
    note: str = ""  # engineer's edit


class TopologyOption(Strict):
    id: TopologyId
    installed_mva: float
    normal_loading_pct: float
    failover_loading_pct: float
    cost: float
    losses_kw: float
    max_lead_time_weeks: int
    spof_count: int
    swaps: list[dict[str, Any]] = []  # [{"line": "T", "from": "TX-2500", "to": "TX-3150", "reason": "R15"}]


RunStatus = Literal["running", "at_gate", "done", "expired", "failed"]


class RunRecord(Strict):
    id: str
    project_id: str
    status: RunStatus
    autonomy: Literal["ask", "auto"]
    phase: Phase | None = None
    gate: Literal["plan", "option", "review"] | None = None
    plan: list[PlanStep] = []
    open_questions: list[OpenQuestion] = []
    options: list[TopologyOption] = []
    selected_option: TopologyId | None = None
    metrics: dict[str, float] = {}
    lease: dict[str, Any] | None = None  # {"owner": str, "attempt": int, "heartbeat_at": float}
    started_at: float
    finished_at: float | None = None


class StepRecord(Strict):
    id: str  # "p2.place_racks"
    phase: Phase
    status: Literal["running", "done", "failed"]
    attempt: int
    outputs_ref: str | None = None
    started_at: float
    finished_at: float | None = None


class RunEvent(Strict):
    seq: int
    phase: Phase
    step: str
    attempt: int = 1
    agent: AgentName
    kind: EventKind
    title: str
    detail: str = ""
    payload: dict[str, Any] = {}
    ts: float
```

`services/api/kirchhoff/contracts/checks.py`:
```python
from typing import Any, Literal

from .common import AgentName, Citation, ClauseRef, FindingStatus, Strict
from .design import DesignModel


class Finding(Strict):
    id: str  # f"{rule_id}:{element_id}"
    rule_id: str  # "R05"
    element_id: str  # "FA-01"
    status: FindingStatus
    title: str
    clause_refs: list[ClauseRef] = []
    tender_refs: list[Citation] = []
    formula: str = ""
    inputs: dict[str, float | str] = {}
    value: float | None = None
    limit: float | None = None
    unit: str | None = None
    explanation: str = ""  # may contain {value}/{limit} placeholders
    fix: dict[str, Any] | None = None  # {"candidate": "...", "reason": "...", "deltas": {...}}
    rejected_fix: dict[str, Any] | None = None


class LedgerEntry(Strict):
    kind: Literal["did", "assumed", "not_checked"]
    agent: AgentName
    text: str


class Revision(Strict):
    id: str  # "r1"
    project_id: str
    parent: str | None = None
    author: str
    hash: str  # sha256 of canonical model JSON
    model: DesignModel | None = None
    model_url: str | None = None
    summary: str = ""
    check_summary: dict[str, int] = {}  # {"pass": n, "fail": n, "warn": n, "n/a": n}
    status: Literal["draft", "checked", "signed"]
    ledger: list[LedgerEntry] = []
    created_at: float


class WhatIfResult(Strict):
    revision_ref: str  # "seed:hall-a@r2" | "ws:r2"
    param: Literal["rack_kw", "liquid_fraction", "dv_limit_pct", "tx_loading_cap_pct"]
    value: float
    findings: list[Finding]
    impact_chain: list[list[str]]  # ordered element-id paths, e.g. [["R1-01","A-01","A1","T-A1"], ...]
```

`services/api/kirchhoff/contracts/enterprise.py`:
```python
from typing import Literal

from .common import Strict


class Material(Strict):
    id: str  # "TX-3150"
    category: str  # "transformer", "busway", "ups_module", "sts", "cdu", "pipe", "breaker", "cable"
    description: str
    rating: float | None = None
    unit: str | None = None
    voltage: str | None = None
    stock: int
    lead_time_weeks: int
    unit_price: float  # USD
    vendor: str


class PRLine(Strict):
    material_id: str
    description: str
    qty: int
    unit_price: float
    lead_time_weeks: int


class PurchaseRequisition(Strict):
    id: str  # "PR-2026-0142"
    project_id: str
    revision: str
    lines: list[PRLine]
    status: Literal["draft", "submitted", "blocked"]
    created_at: float


class Opportunity(Strict):
    id: str
    account: str
    name: str
    stage: str
    value: float
    next_step: str = ""


class CrmOverlay(Strict):
    opportunity_id: str
    stage: str
    updated_at: float
```

`services/api/kirchhoff/contracts/bundle.py`:
```python
from typing import Literal

from .checks import Finding, Revision, WhatIfResult
from .common import AssetPack, Strict
from .enterprise import CrmOverlay, PurchaseRequisition
from .run import DesignBrief, RunEvent, RunRecord, StepRecord


class Project(Strict):
    id: str  # "hall-a", "hall-b", "pune-edge-1", "grid-132kv", "solar-5mwp", "vindhya-lv"
    name: str
    client: str
    asset_pack: AssetPack
    state: Literal["not_started", "running", "in_review", "checked", "draft", "signed", "archived"]
    sample: bool
    updated_at: float


class Approval(Strict):
    id: str
    revision: str
    approver_name: str
    role: str
    decision: Literal["approved", "rejected"]
    comment: str = ""
    ts: float


class ProjectBundle(Strict):
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

`services/api/kirchhoff/contracts/__init__.py`:
```python
from .bundle import Approval, Project, ProjectBundle
from .checks import Finding, LedgerEntry, Revision, WhatIfResult
from .common import AgentName, AssetPack, Citation, ClauseRef, EventKind, FindingStatus, Phase, TopologyId
from .design import Connection, CoolingNode, DesignModel, Equipment, Geometry, Pipe, Point3, Rack
from .enterprise import CrmOverlay, Material, Opportunity, PRLine, PurchaseRequisition
from .run import (DesignBrief, OpenQuestion, PlanStep, Requirement, RunEvent, RunRecord, StepRecord,
                  TopologyOption)

__all__ = [n for n in dir() if not n.startswith("_")]
```

`services/api/kirchhoff/contracts/export_schema.py`:
```python
import json
import sys
from pathlib import Path

from pydantic.json_schema import models_json_schema

from . import (Material, Opportunity, ProjectBundle, PurchaseRequisition, RunEvent, TopologyOption,
               WhatIfResult)

TOP_LEVEL = [ProjectBundle, RunEvent, TopologyOption, WhatIfResult, PurchaseRequisition, Material, Opportunity]


def build_schema(out: Path) -> None:
    _, schema = models_json_schema([(m, "serialization") for m in TOP_LEVEL], title="KirchhoffContracts")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(schema, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    build_schema(Path(sys.argv[1] if len(sys.argv) > 1 else "build/schema.json"))
```

- [ ] **Step 4: Run tests**

Run: `cd services/api && uv run pytest tests/test_contracts.py -q`
Expected: `4 passed`

- [ ] **Step 5: Generate TypeScript and type-check**

Run: `make gen-types && cd apps/web && npx tsc --noEmit -p .`
Expected: `apps/web/src/contracts/generated.ts` contains `export interface ProjectBundle`, `export interface DesignModel`, `export interface Finding`; tsc exits 0.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat(contracts): frozen shared models + TS generation

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Event writer, stores, auth and the hello-run API

**Files:**
- Create: `services/api/kirchhoff/store/{__init__,events,memory,firestore}.py`, `services/api/kirchhoff/api/{__init__,app,auth,hello}.py`
- Test: `services/api/tests/test_events.py`, `services/api/tests/test_api_hello.py`

**Interfaces:**
- Consumes: `RunEvent`, `RunRecord` from Task 2.
- Produces:
  - `class Store(Protocol)`: `set_doc(path: str, data: dict) -> None`, `update_doc(path: str, data: dict) -> None`, `get_doc(path: str) -> dict | None`, `batch_set(items: list[tuple[str, dict]]) -> None`, `list_docs(collection_path: str) -> list[dict]`.
  - `MemoryStore()` and `FirestoreStore(client: google.cloud.firestore.Client)` implementing `Store`.
  - `EventWriter(store: Store, run_path: str, phase: Phase, step: str, attempt: int = 1, flush_interval_s: float = 0.25)` with `.emit(agent, kind, title, detail="", payload=None) -> RunEvent`, `.flush() -> None`, `.close() -> None`; assigns monotonically increasing `seq` starting from `start_seq` (constructor kwarg, default 1); writes to `f"{run_path}/events/{seq:06d}"`.
  - `create_app(store: Store | None = None, verify_token: Callable | None = None) -> FastAPI`.
  - `current_uid` FastAPI dependency: reads `Authorization: Bearer <Firebase ID token>`, verifies with `firebase_admin.auth.verify_id_token`, returns uid; if env `KIRCHHOFF_REQUIRE_APPCHECK=1`, also verifies header `X-Firebase-AppCheck` with `firebase_admin.app_check.verify_token`.
  - `POST /api/hello-run` → `{"run_id": str}`; background thread writes `workspaces/{uid}/runs/{run_id}` (RunRecord, status running→done) and 5 events, 1 s apart.
  - `GET /api/health` → `{"ok": true, "version": str}` (no auth).

- [ ] **Step 1: Write the failing tests**

`services/api/tests/test_events.py`:
```python
from kirchhoff.store.events import EventWriter
from kirchhoff.store.memory import MemoryStore


def test_event_writer_assigns_seq_and_batches():
    store = MemoryStore()
    w = EventWriter(store, "workspaces/u1/runs/r1", phase="p1", step="p1.intake", flush_interval_s=999)
    e1 = w.emit("intake", "status", "Reading tender")
    e2 = w.emit("intake", "message", "Found 18 requirements")
    assert (e1.seq, e2.seq) == (1, 2)
    assert store.list_docs("workspaces/u1/runs/r1/events") == []  # not flushed yet
    w.flush()
    docs = store.list_docs("workspaces/u1/runs/r1/events")
    assert [d["seq"] for d in docs] == [1, 2]
    assert docs[0]["step"] == "p1.intake" and docs[0]["attempt"] == 1


def test_event_writer_start_seq_continues_numbering():
    store = MemoryStore()
    w = EventWriter(store, "workspaces/u1/runs/r1", phase="p2", step="p2.x", start_seq=7, flush_interval_s=999)
    assert w.emit("layout", "status", "x").seq == 7
    w.close()
    assert store.get_doc("workspaces/u1/runs/r1/events/000007")["seq"] == 7
```

`services/api/tests/test_api_hello.py`:
```python
import time

from fastapi.testclient import TestClient

from kirchhoff.api.app import create_app
from kirchhoff.store.memory import MemoryStore


def test_health_needs_no_auth():
    client = TestClient(create_app(store=MemoryStore(), verify_token=lambda t: "u1"))
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_hello_run_rejects_missing_token():
    client = TestClient(create_app(store=MemoryStore(), verify_token=lambda t: "u1"))
    assert client.post("/api/hello-run").status_code == 401


def test_hello_run_streams_events(monkeypatch):
    monkeypatch.setenv("KIRCHHOFF_HELLO_INTERVAL_S", "0.01")
    store = MemoryStore()
    client = TestClient(create_app(store=store, verify_token=lambda t: "u1"))
    r = client.post("/api/hello-run", headers={"Authorization": "Bearer x"})
    assert r.status_code == 202
    run_id = r.json()["run_id"]
    for _ in range(100):
        run = store.get_doc(f"workspaces/u1/runs/{run_id}")
        if run and run["status"] == "done":
            break
        time.sleep(0.02)
    events = store.list_docs(f"workspaces/u1/runs/{run_id}/events")
    assert run["status"] == "done"
    assert len(events) == 5
```

- [ ] **Step 2: Run to verify failure**

Run: `cd services/api && uv run pytest tests/test_events.py tests/test_api_hello.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'kirchhoff.store'`

- [ ] **Step 3: Implement stores and the event writer**

`services/api/kirchhoff/store/__init__.py`:
```python
from typing import Protocol


class Store(Protocol):
    def set_doc(self, path: str, data: dict) -> None: ...
    def update_doc(self, path: str, data: dict) -> None: ...
    def get_doc(self, path: str) -> dict | None: ...
    def batch_set(self, items: list[tuple[str, dict]]) -> None: ...
    def list_docs(self, collection_path: str) -> list[dict]: ...
```

`services/api/kirchhoff/store/memory.py`:
```python
import copy
import threading


class MemoryStore:
    """Thread-safe in-memory Store for tests. Paths look like 'a/b/c/d' (even segment count = document)."""

    def __init__(self) -> None:
        self._docs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def set_doc(self, path: str, data: dict) -> None:
        with self._lock:
            self._docs[path] = copy.deepcopy(data)

    def update_doc(self, path: str, data: dict) -> None:
        with self._lock:
            self._docs.setdefault(path, {}).update(copy.deepcopy(data))

    def get_doc(self, path: str) -> dict | None:
        with self._lock:
            d = self._docs.get(path)
            return copy.deepcopy(d) if d is not None else None

    def batch_set(self, items: list[tuple[str, dict]]) -> None:
        with self._lock:
            for path, data in items:
                self._docs[path] = copy.deepcopy(data)

    def list_docs(self, collection_path: str) -> list[dict]:
        prefix = collection_path.rstrip("/") + "/"
        depth = collection_path.count("/") + 2
        with self._lock:
            keys = sorted(k for k in self._docs if k.startswith(prefix) and k.count("/") + 1 == depth)
            return [copy.deepcopy(self._docs[k]) for k in keys]
```

`services/api/kirchhoff/store/firestore.py`:
```python
from google.cloud import firestore


class FirestoreStore:
    def __init__(self, client: firestore.Client | None = None) -> None:
        self._db = client or firestore.Client(project="ordinal-mep")

    def set_doc(self, path: str, data: dict) -> None:
        self._db.document(path).set(data)

    def update_doc(self, path: str, data: dict) -> None:
        self._db.document(path).set(data, merge=True)

    def get_doc(self, path: str) -> dict | None:
        snap = self._db.document(path).get()
        return snap.to_dict() if snap.exists else None

    def batch_set(self, items: list[tuple[str, dict]]) -> None:
        for i in range(0, len(items), 450):  # Firestore batch limit is 500 writes
            batch = self._db.batch()
            for path, data in items[i:i + 450]:
                batch.set(self._db.document(path), data)
            batch.commit()

    def list_docs(self, collection_path: str) -> list[dict]:
        return [s.to_dict() for s in self._db.collection(collection_path).order_by("__name__").stream()]
```

`services/api/kirchhoff/store/events.py`:
```python
import threading
import time
from typing import Any

from kirchhoff.contracts import RunEvent

from . import Store


class EventWriter:
    """Assigns seq and writes RunEvents in batches (spec §11: ~250 ms batching, single writer per phase)."""

    def __init__(self, store: Store, run_path: str, phase: str, step: str, attempt: int = 1,
                 start_seq: int = 1, flush_interval_s: float = 0.25) -> None:
        self._store, self._run_path = store, run_path
        self._phase, self._step, self._attempt = phase, step, attempt
        self._seq = start_seq - 1
        self._pending: list[RunEvent] = []
        self._lock = threading.Lock()
        self._interval = flush_interval_s
        self._last_flush = time.monotonic()

    @property
    def last_seq(self) -> int:
        return self._seq

    def set_step(self, step: str) -> None:
        self.flush()
        self._step = step

    def emit(self, agent: str, kind: str, title: str, detail: str = "",
             payload: dict[str, Any] | None = None) -> RunEvent:
        with self._lock:
            self._seq += 1
            ev = RunEvent(seq=self._seq, phase=self._phase, step=self._step, attempt=self._attempt,
                          agent=agent, kind=kind, title=title, detail=detail, payload=payload or {},
                          ts=time.time())
            self._pending.append(ev)
            due = time.monotonic() - self._last_flush >= self._interval
        if due:
            self.flush()
        return ev

    def flush(self) -> None:
        with self._lock:
            items = [(f"{self._run_path}/events/{e.seq:06d}", e.model_dump()) for e in self._pending]
            self._pending = []
            self._last_flush = time.monotonic()
        if items:
            self._store.batch_set(items)

    def close(self) -> None:
        self.flush()
```

- [ ] **Step 4: Implement auth, app and hello route**

`services/api/kirchhoff/api/auth.py`:
```python
import os
from typing import Callable

from fastapi import Header, HTTPException, Request


def firebase_verify(token: str) -> str:
    import firebase_admin
    from firebase_admin import auth

    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={"projectId": "ordinal-mep"})
    return auth.verify_id_token(token)["uid"]


def appcheck_verify(token: str) -> None:
    import firebase_admin
    from firebase_admin import app_check

    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={"projectId": "ordinal-mep"})
    app_check.verify_token(token)


def make_current_uid(verify_token: Callable[[str], str]):
    def current_uid(request: Request, authorization: str | None = Header(default=None),
                    x_firebase_appcheck: str | None = Header(default=None)) -> str:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="missing bearer token")
        try:
            uid = verify_token(authorization.removeprefix("Bearer "))
        except Exception as exc:  # invalid/expired token
            raise HTTPException(status_code=401, detail="invalid token") from exc
        if os.environ.get("KIRCHHOFF_REQUIRE_APPCHECK") == "1":
            if not x_firebase_appcheck:
                raise HTTPException(status_code=401, detail="missing app check token")
            try:
                appcheck_verify(x_firebase_appcheck)
            except Exception as exc:
                raise HTTPException(status_code=401, detail="invalid app check token") from exc
        return uid
    return current_uid
```

`services/api/kirchhoff/api/hello.py`:
```python
import os
import threading
import time
import uuid

from fastapi import APIRouter, Depends

from kirchhoff.contracts import RunRecord
from kirchhoff.store import Store
from kirchhoff.store.events import EventWriter

STEPS = ["Intake reading tender", "Layout placing racks", "Power sizing chain", "Cooling sizing CDUs",
         "Checker verifying"]


def make_router(store: Store, current_uid) -> APIRouter:
    router = APIRouter()

    def _run(uid: str, run_id: str) -> None:
        interval = float(os.environ.get("KIRCHHOFF_HELLO_INTERVAL_S", "1.0"))
        run_path = f"workspaces/{uid}/runs/{run_id}"
        writer = EventWriter(store, run_path, phase="p1", step="p1.hello", flush_interval_s=0)
        for i, title in enumerate(STEPS):
            writer.emit("system", "status", title, detail=f"step {i + 1} of {len(STEPS)}")
            time.sleep(interval)
        writer.close()
        store.update_doc(run_path, {"status": "done", "finished_at": time.time()})

    @router.post("/api/hello-run", status_code=202)
    def hello_run(uid: str = Depends(current_uid)) -> dict:
        run_id = uuid.uuid4().hex[:12]
        run = RunRecord(id=run_id, project_id="hello", status="running", autonomy="auto", phase="p1",
                        started_at=time.time())
        store.set_doc(f"workspaces/{uid}/runs/{run_id}", run.model_dump())
        threading.Thread(target=_run, args=(uid, run_id), daemon=True).start()
        return {"run_id": run_id}

    return router
```

`services/api/kirchhoff/api/app.py`:
```python
import os
from typing import Callable

from fastapi import FastAPI

from kirchhoff.store import Store

from .auth import firebase_verify, make_current_uid
from .hello import make_router as hello_router

VERSION = os.environ.get("K_REVISION", "dev")


def create_app(store: Store | None = None, verify_token: Callable[[str], str] | None = None) -> FastAPI:
    if store is None:
        from kirchhoff.store.firestore import FirestoreStore
        store = FirestoreStore()
    current_uid = make_current_uid(verify_token or firebase_verify)
    app = FastAPI(title="Kirchhoff API")

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "version": VERSION}

    app.include_router(hello_router(store, current_uid))
    app.state.store = store
    app.state.current_uid = current_uid
    return app
```

- [ ] **Step 5: Run tests**

Run: `cd services/api && uv run pytest -q`
Expected: all tests pass (`8 passed`).

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat(api): event writer, stores, auth, hello-run

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Web hello screen (anonymous auth + live Firestore events)

**Files:**
- Create: `apps/web/src/firebase.ts`, `apps/web/src/api.ts`, `apps/web/src/hello/HelloRun.tsx`, `apps/web/src/hello/HelloRun.test.tsx`
- Modify: `apps/web/src/App.tsx`, `apps/web/src/main.tsx`

**Interfaces:**
- Consumes: `RunEvent` TS type from `src/contracts/generated.ts`; `POST /api/hello-run`.
- Produces:
  - `src/firebase.ts`: `export const app`, `export const auth`, `export const db`, `export async function ensureSignedIn(): Promise<User>`, `export function initAppCheck(): void` (no-op when `import.meta.env.MODE === 'test'`).
  - `src/api.ts`: `export async function apiFetch(path: string, init?: RequestInit): Promise<Response>` — adds `Authorization: Bearer <idToken>` and `X-Firebase-AppCheck` headers.
  - `HelloRun` component with props `{ start: () => Promise<string>; subscribe: (runId: string, cb: (events: RunEvent[]) => void) => () => void }`.

- [ ] **Step 1: Write the failing component test**

`apps/web/src/hello/HelloRun.test.tsx`:
```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { HelloRun } from './HelloRun'
import type { RunEvent } from '../contracts/generated'

const ev = (seq: number, title: string): RunEvent => ({
  seq, phase: 'p1', step: 'p1.hello', attempt: 1, agent: 'system', kind: 'status', title, detail: '', payload: {}, ts: seq,
})

test('starts a run and renders streamed events in seq order', async () => {
  let push: (e: RunEvent[]) => void = () => {}
  render(<HelloRun start={async () => 'run1'} subscribe={(_id, cb) => { push = cb; return () => {} }} />)
  fireEvent.click(screen.getByRole('button', { name: /start run/i }))
  await waitFor(() => expect(screen.getByText(/run1/)).toBeInTheDocument())
  push([ev(2, 'Layout placing racks'), ev(1, 'Intake reading tender')])
  await waitFor(() => {
    const items = screen.getAllByRole('listitem').map((li) => li.textContent)
    expect(items[0]).toContain('Intake reading tender')
    expect(items[1]).toContain('Layout placing racks')
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps/web && npx vitest run src/hello`
Expected: FAIL — cannot find module `./HelloRun`.

- [ ] **Step 3: Implement**

`apps/web/src/firebase.ts`:
```ts
import { initializeApp } from 'firebase/app'
import { getAuth, signInAnonymously, onAuthStateChanged, type User } from 'firebase/auth'
import { getFirestore } from 'firebase/firestore'
import { initializeAppCheck, ReCaptchaEnterpriseProvider, getToken, type AppCheck } from 'firebase/app-check'

export const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: 'ordinal-mep.firebaseapp.com',
  projectId: 'ordinal-mep',
  storageBucket: 'ordinal-mep.firebasestorage.app',
  messagingSenderId: '1015632998221',
  appId: '1:1015632998221:web:c98110f2fc88424da81104',
}

export const app = initializeApp(firebaseConfig)
export const auth = getAuth(app)
export const db = getFirestore(app)

let appCheck: AppCheck | null = null
export function initAppCheck(): void {
  if (import.meta.env.MODE === 'test' || appCheck) return
  if (import.meta.env.DEV) (self as any).FIREBASE_APPCHECK_DEBUG_TOKEN = import.meta.env.VITE_APPCHECK_DEBUG_TOKEN || true
  appCheck = initializeAppCheck(app, {
    provider: new ReCaptchaEnterpriseProvider('6LdBw-wtAAAAALNbcALgFtPxNx9lcvnK_q2HuERk'),
    isTokenAutoRefreshEnabled: true,
  })
}

export async function appCheckToken(): Promise<string | null> {
  if (!appCheck) return null
  try { return (await getToken(appCheck, false)).token } catch { return null }
}

export function ensureSignedIn(): Promise<User> {
  return new Promise((resolve, reject) => {
    const off = onAuthStateChanged(auth, (u) => {
      if (u) { off(); resolve(u) }
    })
    signInAnonymously(auth).catch(reject)
  })
}
```

`apps/web/src/api.ts`:
```ts
import { ensureSignedIn, appCheckToken } from './firebase'

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const user = await ensureSignedIn()
  const headers = new Headers(init.headers)
  headers.set('Authorization', `Bearer ${await user.getIdToken()}`)
  const ac = await appCheckToken()
  if (ac) headers.set('X-Firebase-AppCheck', ac)
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  return fetch(path, { ...init, headers })
}
```

`apps/web/src/hello/HelloRun.tsx`:
```tsx
import { useEffect, useState } from 'react'
import type { RunEvent } from '../contracts/generated'

type Props = {
  start: () => Promise<string>
  subscribe: (runId: string, cb: (events: RunEvent[]) => void) => () => void
}

export function HelloRun({ start, subscribe }: Props) {
  const [runId, setRunId] = useState<string | null>(null)
  const [events, setEvents] = useState<RunEvent[]>([])

  useEffect(() => {
    if (!runId) return
    return subscribe(runId, (evs) => setEvents([...evs].sort((a, b) => a.seq - b.seq)))
  }, [runId, subscribe])

  return (
    <main style={{ fontFamily: 'Inter, system-ui', padding: 24, color: '#e5e7eb', background: '#0b0d10', minHeight: '100vh' }}>
      <h1>Kirchhoff — hello run</h1>
      <button onClick={async () => setRunId(await start())}>Start run</button>
      {runId && <p>Run {runId}</p>}
      <ol>{events.map((e) => <li key={e.seq}>{e.seq}. {e.title} <small>{e.detail}</small></li>)}</ol>
    </main>
  )
}
```

`apps/web/src/App.tsx`:
```tsx
import { collection, onSnapshot, orderBy, query } from 'firebase/firestore'
import { useCallback } from 'react'
import { apiFetch } from './api'
import { auth, db } from './firebase'
import { HelloRun } from './hello/HelloRun'
import type { RunEvent } from './contracts/generated'

export default function App() {
  const start = useCallback(async () => {
    const r = await apiFetch('/api/hello-run', { method: 'POST' })
    if (!r.ok) throw new Error(`hello-run failed: ${r.status}`)
    return (await r.json()).run_id as string
  }, [])
  const subscribe = useCallback((runId: string, cb: (e: RunEvent[]) => void) => {
    const uid = auth.currentUser!.uid
    const q = query(collection(db, `workspaces/${uid}/runs/${runId}/events`), orderBy('seq'))
    return onSnapshot(q, (snap) => cb(snap.docs.map((d) => d.data() as RunEvent)))
  }, [])
  return <HelloRun start={start} subscribe={subscribe} />
}
```

`apps/web/src/main.tsx`:
```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { initAppCheck } from './firebase'

initAppCheck()
createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
```

Create `apps/web/.env.production` with `VITE_FIREBASE_API_KEY=<apiKey>`; obtain the value with:
```bash
TOKEN=$(gcloud auth print-access-token); curl -s -H "Authorization: Bearer $TOKEN" -H "x-goog-user-project: ordinal-mep" \
  "https://firebase.googleapis.com/v1beta1/projects/ordinal-mep/webApps/1:1015632998221:web:c98110f2fc88424da81104/config" | python3 -c "import sys,json;print(json.load(sys.stdin)['apiKey'])"
```
The Firebase web API key is a public client identifier (safe in the bundle); copy the same line into `apps/web/.env.development`. Update `.gitignore` to allow these two files: add `!.env.production` and `!.env.development`.

- [ ] **Step 4: Run the test**

Run: `cd apps/web && npx vitest run`
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(web): anonymous auth + live event stream hello screen

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Security rules, container, deploy and production smoke test

**Files:**
- Create: `services/api/Dockerfile`, `infra/firebase.json`, `infra/.firebaserc`, `infra/firestore.rules`, `infra/storage.rules`, `infra/deploy_api.sh`, `infra/deploy_web.sh`, `infra/smoke.sh`

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces: Cloud Run service `kirchhoff-api` (asia-south1) serving `/api/*`; Hosting site `kirchhoff` with `/api/**` → `kirchhoff-api`; `infra/smoke.sh` exits 0 when production works.

- [ ] **Step 1: Dockerfile**

`services/api/Dockerfile`:
```dockerfile
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY kirchhoff ./kirchhoff
RUN uv sync --frozen --no-dev
ENV PORT=8080
CMD ["/app/.venv/bin/uvicorn", "kirchhoff.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
```

- [ ] **Step 2: Rules**

`infra/firestore.rules`:
```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /workspaces/{uid}/{document=**} {
      allow read: if request.auth != null && request.auth.uid == uid;
      allow write: if false;
    }
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```

`infra/storage.rules`:
```
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    match /seed/{allPaths=**} { allow read: if true; allow write: if false; }
    match /workspaces/{uid}/{allPaths=**} {
      allow read: if request.auth != null && request.auth.uid == uid;
      allow write: if false;
    }
  }
}
```

`infra/firebase.json`:
```json
{
  "hosting": {
    "site": "kirchhoff",
    "public": "../apps/web/dist",
    "ignore": ["firebase.json", "**/.*"],
    "rewrites": [
      { "source": "/api/**", "run": { "serviceId": "kirchhoff-api", "region": "asia-south1" } },
      { "source": "**", "destination": "/index.html" }
    ],
    "headers": [{ "source": "/demo/**", "headers": [{ "key": "Cache-Control", "value": "public, max-age=300" }] }]
  },
  "firestore": { "rules": "firestore.rules" },
  "storage": { "rules": "storage.rules" }
}
```

`infra/.firebaserc`:
```json
{ "projects": { "default": "ordinal-mep" } }
```

- [ ] **Step 3: Deploy scripts**

`infra/deploy_api.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../services/api"
uv lock
gcloud run deploy kirchhoff-api --project=ordinal-mep --region=asia-south1 --source=. \
  --allow-unauthenticated --no-cpu-throttling --min-instances=1 --max-instances=3 --concurrency=20 \
  --cpu=2 --memory=2Gi --timeout=900 \
  --set-env-vars=GOOGLE_CLOUD_PROJECT=ordinal-mep,GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_LOCATION=global
```

`infra/deploy_web.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
(cd "$ROOT/apps/web" && npm run build)
cd "$ROOT/infra"
npx -y firebase-tools@latest deploy --project ordinal-mep --only hosting:kirchhoff,firestore:rules,storage --non-interactive
```

`infra/smoke.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
BASE=${1:-https://kirchhoff.web.app}
curl -fsS "$BASE/api/health" | grep -q '"ok":true'
curl -fsS "$BASE/" | grep -qi '<div id="root">'
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/hello-run")
[ "$code" = "401" ]
echo "smoke OK: $BASE"
```

Run: `chmod +x infra/*.sh`

- [ ] **Step 4: Grant the Cloud Run runtime service account Firestore access**

Run:
```bash
PN=$(gcloud projects describe ordinal-mep --format='value(projectNumber)')
gcloud projects add-iam-policy-binding ordinal-mep --member="serviceAccount:${PN}-compute@developer.gserviceaccount.com" --role=roles/datastore.user --condition=None
gcloud projects add-iam-policy-binding ordinal-mep --member="serviceAccount:${PN}-compute@developer.gserviceaccount.com" --role=roles/aiplatform.user --condition=None
gcloud projects add-iam-policy-binding ordinal-mep --member="serviceAccount:${PN}-compute@developer.gserviceaccount.com" --role=roles/storage.objectAdmin --condition=None
gcloud projects add-iam-policy-binding ordinal-mep --member="serviceAccount:${PN}-compute@developer.gserviceaccount.com" --role=roles/firebaseauth.viewer --condition=None
```
Expected: each prints the updated policy.

- [ ] **Step 5: Deploy the API**

Run: `./infra/deploy_api.sh`
Expected: "Service [kirchhoff-api] revision [...] has been deployed and is serving 100 percent of traffic." If Cloud Build asks to enable APIs or create an Artifact Registry repo, answer yes (`--quiet` is acceptable).

- [ ] **Step 6: Deploy hosting and rules**

Run: `./infra/deploy_web.sh`
Expected: "Deploy complete!" with Hosting URL https://kirchhoff.web.app. If firebase-tools reports it is not authenticated, stop and ask the controller to have the user run `! npx -y firebase-tools@latest login` in the session, then re-run.

- [ ] **Step 7: Production smoke test**

Run: `./infra/smoke.sh`
Expected: `smoke OK: https://kirchhoff.web.app`

Then open https://kirchhoff.web.app in a browser (Playwright: `npx -y playwright@latest open https://kirchhoff.web.app` or a headless script), click "Start run", and confirm 5 events appear within ~7 s. Record the result in the commit message.

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "feat(infra): rules, container, deploy scripts; hello world live end to end

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

## Self-review notes

- Spec §7 (Hosting → Cloud Run rewrite, min 1/max 3, no CPU throttling, 2 vCPU/2 GiB, auth on every call except health) → Task 5 Step 3 and Task 3.
- Spec §14 (clients read only own workspace; writes denied; storage rules) → Task 5 Step 2.
- Spec §11 (batched events ~250 ms, single writer assigns seq) → Task 3 `EventWriter`.
- Spec §14 ProjectBundle and contracts → Task 2 (frozen; later plans may only add optional fields).
- App Check verification is wired but only enforced when `KIRCHHOFF_REQUIRE_APPCHECK=1`; enforcement is switched on in the P4 plan after the client sends tokens in production.
