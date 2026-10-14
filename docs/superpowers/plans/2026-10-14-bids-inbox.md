# Kirchhoff Bids Inbox (spec §20) Implementation Plan — addendum to P2, P3 and P4

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the bids inbox, Kirchhoff's front door: a seeded `bids@meridian-power.example` mailbox (sandbox, simulated) whose six emails are triaged by a Gemini Inbox agent (attachment classes, CRM link, verified field quotes), checked against the firm's appetite by deterministic fit rules including a day-zero supply check on the engine and ERP, and turned into a project and a "Qualification" CRM opportunity with one Pursue click.

**Architecture:** Three tasks, one per workstream, each fitting its plan. **I-1 (WS4)** authors the six emails, their attachments and the appetite rules in `world.yaml`, renders the new attachments deterministically, and writes the inbox in the static bundle (`apps/web/public/demo/inbox.json`) and the API seed (`scenarios/demo_world/out/inbox_seed.json`, loaded into Firestore `seed/inbox` by the existing seed loader). It also gives the CRM sandbox the "Qualification" stage and per-visitor opportunity creation. **I-2 (WS2)** adds `kirchhoff/inbox/`: deterministic fit rules and the day-zero supply check (engine `place_racks`, `power_options`, `r15_swap` and ERP lead times; no LLM), the Inbox agent (Gemini 3.8 Flash, low thinking) with quotes verified by the existing `verify_quote`, the triage pipeline, three endpoints, and a precompute script that freezes the real agent's triage of every seeded email into the static bundle at golden-capture time. **I-3 (WS3)** adds `/app/inbox`, a list and detail page that reads the static bundle first and the live API second, with a live Triage button on the Hall B email only.

**Tech Stack:** Python 3.12, FastAPI 0.141, pydantic 2.14, pdfplumber 0.11.10, reportlab 5.0.1, Pillow 12.3.0 (already locked in `uv.lock` as a reportlab/pdfplumber dependency; nothing is added to `pyproject.toml`), pyyaml, pytest; React 19.3, TypeScript 5.9.3, zustand 5, react-router 8.4, lucide-react 1.56, vitest 5 + Testing Library.

**Spec:** `docs/superpowers/specs/2026-10-13-kirchhoff-design.md` (v4.1). Read §20 (the feature), §6.3 (trust rules), §13 (demo world), §11 (static first) and §9.5 (ERP and CRM seed). **Binding:** `docs/superpowers/plans/2026-10-13-interfaces.md` (ownership, conventions, HTTP API table, controller rulings). **Plans this addendum extends:** `2026-10-13-p4-enterprise-demo-infra.md` (Tasks 1, 2, 4, 11), `2026-10-13-p2-agents-api.md` (Tasks 3, 4, 5, 7, 8, 9, 12), `2026-10-13-p3-web.md` (Tasks 3, 5, 13, 14).

**Prerequisites and order:**
- **I-1** needs only P4 Tasks 1, 2 and 4 (merged in `ws4-infra`) and WS2's rendered `scenarios/hall_a/out/{tender-hall-a.pdf,hall-a-plan.pdf}`. Those PDFs are on `build`. A branch cut from `build` has them; `ws4-infra` gets them by merging `build` first (`ls scenarios/hall_a/out/tender-hall-a.pdf` must succeed). I-1 does **not** need P4 Task 11: the inbox has its own generator and output paths, so `write_world` never deletes inbox files. It can start now.
- **I-3** can start now. It renders from its own fixture; the real `inbox.json` comes from I-1.
- **I-2** waits for P2 Task 9 (`canonical_topology`), Task 12 (`Deps`, `create_app`, `tests/api/conftest.py`) and for I-1 to be merged into `ws2-agents` (it reads `inbox_seed.json`, the rendered attachments and the sandbox's `create_opportunity`). Check with:
  ```bash
  cd services/api && uv run python -c "from kirchhoff.intake.brief import canonical_topology; from kirchhoff.api.app import create_app; from kirchhoff.enterprise.world.inbox import load_inbox_seed; from kirchhoff.enterprise.sandbox import Sandbox; assert hasattr(Sandbox, 'create_opportunity'); print('I-2 prerequisites OK')"
  ls ../../scenarios/demo_world/out/inbox_seed.json ../../scenarios/demo_world/out/inbox/hall-b-addendum-1.pdf
  ```

## Global Constraints

- GCP project `ordinal-mep`. Always pass `--project=ordinal-mep` to gcloud. Never run `gcloud config set project`.
- Every local process that calls Google APIs sets `GOOGLE_GENAI_USE_VERTEXAI=true GOOGLE_CLOUD_PROJECT=ordinal-mep GOOGLE_CLOUD_QUOTA_PROJECT=ordinal-mep GOOGLE_CLOUD_LOCATION=global`.
- Fresh code only: everything is written from scratch during the hackathon. Open-source libraries are fine.
- Git: the machine's global identity (no `-c user.*`). End every commit message with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`. **Stage only the files your task lists** (`git add <paths>`; never `git add -A` or `git add .`): other workstreams commit to the same branches in parallel.
- Do not spawn subagents from inside a task.
- **Ownership (amends the interfaces doc for this feature):**
  - WS4 (I-1) creates or modifies only `services/api/kirchhoff/enterprise/**`, `services/api/tests/enterprise/**`, `scenarios/demo_world/**` and the `Makefile` `demo-world` target. It also owns the generated files `apps/web/public/demo/inbox.json`, `apps/web/public/demo/inbox/**`, `scenarios/demo_world/out/inbox_seed.json`, `scenarios/demo_world/out/inbox/**`, and commits `scenarios/demo_world/captures/inbox-triage.json` (written by WS2's precompute script).
  - WS2 (I-2) newly owns `services/api/kirchhoff/inbox/**` and `services/api/tests/inbox/**`, and modifies only its own `kirchhoff/agents/{ports,specs}.py`, `kirchhoff/runs/fakes.py`, `kirchhoff/api/{app.py,inbox_routes.py}` and `tests/api/{conftest.py,test_api_inbox.py}`.
  - WS3 (I-3) touches only `apps/web/src/**`.
- Contracts stay frozen: no field is added to `kirchhoff/contracts/*`. The inbox shapes are WS4-local (`kirchhoff.enterprise.world.inbox`: the seed) and WS2-local (`kirchhoff.inbox.models`: the triage). WS3 types them by hand in `src/lib/types.ts`, as P3 ruling R13 does for `World`.
- Firestore conventions (binding): documents are `model_dump(mode="json")` output (snake_case, unix-second floats, no tuples). Document paths have an even number of segments. No arrays nested directly in arrays. New paths:
  - `seed/inbox` (meta doc) and `seed/inbox/emails/{email_id}`: written by WS4's seed loader, read by the API only (the existing rules keep `seed/*` from clients).
  - `workspaces/{uid}/inbox/{email_id}` (the visitor's triage and Pursue overlay) and `workspaces/{uid}/projects/{pid}` (projects created by Pursue): written by WS2, readable by their owner under the existing rules, deleted by `POST /api/workspace/reset`.
  - `sandbox_visitors/{uid}/opportunities/{oid}`: opportunities a visitor creates, written by the WS4 sandbox and deleted by `reset_visitor`.
- Clients never write Firestore. Every mutation goes through `/api`.
- Every `/api` call returns in < 10 s (triage is cut at 9.5 s and answers 504 `timeout`). The web client aborts every call after 12 s.
- Trust rules (spec §6.3): all LLM text shown in the UI passes `kirchhoff.agents.trust.sanitize`. A field value is shown only if its verbatim quote verifies: with pdfplumber `verify_quote` on a PDF page that has text, or as a normalized substring of the email body. A field read from a page without a text layer is marked `unverified_scan` ("unverified (scan)"), and its value is withheld unless it is digit-free text. Fit reasons and the supply line are code-authored templates filled only from verified values, ERP records, engine results and `world.yaml` (P2 ruling R14).
- Model `gemini-3.8-flash` only (Pro and flash-lite return 404). The Inbox agent uses thinking level `low`. Gemini calls retry through `kirchhoff.agents.runner.with_retries` (already inside both runners).
- Required labels, verbatim: `Demo workspace — all companies, people and data are fictional`, `sandbox (simulated)` (the mailbox and the CRM), `IEC-based, illustrative values, not for construction` (on every generated PDF).
- Generators are deterministic: fixed seed `20261013`, fixed anchor `now = 1792132200` (2026-10-16 12:00 IST), no wall-clock reads, sorted outputs, reportlab `invariant = 1`. Days to a bid deadline are counted from the inbox's `as_of` (the world anchor), never from the wall clock, so live and precomputed verdicts agree throughout judging (19 Oct – 6 Nov).
- Static first (spec §11): the inbox page, its precomputed triage and the dashboard entry render from `/demo/inbox.json` with Cloud Run, Gemini, Firestore and App Check down. The live API only adds the visitor's overlay, live Triage and Pursue.
- UI (spec §12, P3): status is always icon + text, never colour alone. WCAG AA on `#0b0d10`. Every control is keyboard-reachable. Motion only for progress, and `prefers-reduced-motion` disables it (`motion-reduce:` utilities). The 7-step tour order (spec §13.5) does not change.
- Live GCP actions (Firestore seed reloads, deploys) are run by the controller, never by a task implementer.
- Tests: Python from `services/api`: `uv run pytest <path> -q`. Test files have unique basenames. Web from `apps/web`: `npx vitest run <path>`, full suite `npm test`, type-check `npx tsc -b`.
- **Cut line (spec §20, checkpoint Thu 16 Oct 12:00 IST).** Every step is tagged:
  - **[cut-safe]**: ships even if Must items are behind at the checkpoint. That is all of I-1, I-2's triage pipeline and precompute script, and I-3's static page.
  - **[cut]**: skipped if Must items are behind at the checkpoint. That is I-2's endpoints and I-3's live Triage button.
  - If the cut is taken, the inbox ships with precomputed triage only, and the static Pursue still opens Hall B (I-3 Step 5).

## Rulings for this addendum

| # | Question | Ruling |
|---|---|---|
| B1 | Spec §20's first draft said "Qualifying"; P4's sandbox `STAGES` and `world.yaml` already say "Qualification" | **Controller ruling:** use the existing stage name **"Qualification"** everywhere. No stage is renamed, `STAGES` and the seeded `opp-hall-c`/`opp-vindhya-cpp` are untouched, and the spec's §20 wording is corrected to "Qualification". Pursue (B2) and the fit/pursue logic (I-2, I-3) all move or create opportunities at "Qualification". |
| B2 | "Moves or creates the CRM opportunity" but the sandbox can only move seed opportunities | I-1 adds `Sandbox.create_opportunity(uid, opportunity)` (per visitor, idempotent, under `sandbox_visitors/{uid}/opportunities`), `POST /crm/opportunities` on kirchhoff-enterprise, `create_opportunity` on both clients, and visitor opportunities in `list_opportunities(uid)`. I-2 adds `list_opportunities` and `create_opportunity` to WS2's `EnterpriseClient` protocol and to `FakeEnterprise`. |
| B3 | Spec §9.5 seeds `opp-hall-b` at "Design in progress", but Pursue on the Hall B email sets "Qualification" | Pursue sets "Qualification" in the visitor's overlay unless the opportunity is already "Design approved", "Closed won" or "Closed lost". A signed or closed deal is never reopened. For Hall B the visitor's story then runs Qualification → (live run, sign) → Design approved. The seed itself is unchanged. |
| B4 | "Pursue creates the project", but `hall-b` already exists in the demo world | An email may name an existing world project (`project_id: hall-b`). Pursue then creates nothing, returns `open: "/app/p/hall-b"`, and the UI opens the normal Hall B intake flow. Other emails create `workspaces/{uid}/projects/bid-{slug}` (state `draft`), shown on the email's detail. The dashboard lists only world projects. |
| B5 | Where the precomputed triage lives (WS2 produces it, WS4 owns the static bundle) | WS2's `python -m kirchhoff.inbox.precompute` writes `scenarios/demo_world/captures/inbox-triage.json`. WS4's inbox generator folds it into `inbox.json` and `inbox_seed.json` at golden-capture time, so the static bundle keeps one writer and `--check` stays meaningful. Until the capture exists, every email's `triage` is `null` and the page says "Not triaged yet". |
| B6 | Where the inbox's PDFs live | The Hall B tender and drawing are Hall A's (`/demo/docs/tender-hall-a.pdf`, `/demo/docs/hall-a-plan.pdf`, copied by WS3's `sync-demo-docs.mjs`). The email says Hall B is Hall A's twin and Addendum 1 says the requirements apply unchanged. New attachments are rendered by WS4 into `apps/web/public/demo/inbox/` (browser) and `scenarios/demo_world/out/inbox/` (API image and precompute). This is not `/demo/files/`, which P4 Task 11's `write_world` prunes. |
| B7 | The supply check needs engine internals that `kirchhoff/engine/api.py` does not re-export (`r15_swap`, `with_limit`, `effective_lead_weeks`) | `kirchhoff/inbox/fit.py` imports them read-only from `kirchhoff.engine.options`, `.scenario` and `.erp` (WS1 is complete and frozen). `test_supply_uses_the_engine_internals_it_names` pins the imports, so a rename fails loudly. The reference hall is Hall A's geometry with the per-rack load scaled to the extracted MW (`with_limit(scn, "rack_kw", …)`). |
| B8 | The first engine call in a fresh process takes about 6 s (pandapower import) | On Cloud Run (`K_SERVICE` set), the inbox router warms the engine in a daemon thread with `kirchhoff.engine.api.warm_up()`, which is idempotent. The P1 final review already asked P2 to warm the engine at startup; this covers the inbox until that lands. After warm-up the supply check takes about 0.2 s. |
| B9 | "New" on the dashboard | An email is new until this browser opens it. Read ids live in `localStorage` key `kirchhoff.inbox.read`, which "Reset demo workspace" clears. |
| B10 | Emails that are not bids (correspondence, a brochure) | The verdict is `null`, shown as "Not a bid", with one reason saying where the email was filed. Pursue is offered only for `pursue` and `clarify` verdicts on an email whose asset type is one of the firm's packs. |

## File Structure

```
scenarios/demo_world/
  world.yaml                       (modify, append-only) inbox: mailbox, appetite rules, six emails (no stage rename)
  build_inbox.py                   (create) CLI: build or --check the inbox files
  captures/inbox-triage.json       (generated by I-2's precompute at golden capture; committed by WS4)
  out/inbox_seed.json, out/inbox/*.pdf     (generated, committed) API image + Firestore seed
apps/web/public/demo/
  inbox.json, inbox/*.pdf          (generated by I-1, committed) static bundle
services/api/kirchhoff/enterprise/
  world/config.py                  (modify) RegionCfg, Appetite, InboxAttachmentCfg, InboxEmailCfg, InboxCfg; WorldConfig.inbox
  world/inbox.py                   (create) InboxAttachment, InboxEmail, InboxSeed, renderers, build/write/check, load_inbox
  sandbox.py                       (modify) STAGES unchanged; create_opportunity; visitor opportunities listed
  app.py, client.py                (modify) POST /crm/opportunities; create_opportunity on both clients
  seed_cli.py                      (modify) --inbox: loads seed/inbox
services/api/tests/enterprise/
  test_world_inbox.py              (create)
  test_enterprise_sandbox.py, test_enterprise_http.py, test_enterprise_seed_cli.py   (modify: append tests)
services/api/kirchhoff/inbox/      (create, WS2)
  __init__.py
  models.py                        InboxExtraction (agent output), ExtractedField, AttachmentTriage, CrmLink,
                                   FitReason, SupplyCheck, FitResult, TriageResult, PursueResult
  fit.py                           parse_due, days_to_due, region_of, day_zero_supply, supply_for, assess_fit
  triage.py                        build_message, verify_field, triage_email
  store.py                         seed + overlay access for the API
  precompute.py                    CLI: real agent over every seeded email → captures/inbox-triage.json
services/api/kirchhoff/agents/specs.py   (modify) INBOX AgentSpec
services/api/kirchhoff/agents/ports.py   (modify) EnterpriseClient.list_opportunities/create_opportunity, STAGE_QUALIFYING
services/api/kirchhoff/runs/fakes.py     (modify) FAKE_OPPORTUNITIES, FakeEnterprise CRM, six inbox FAKE_REPLIES
services/api/kirchhoff/api/inbox_routes.py   (create) GET /api/inbox, POST …/triage, POST …/pursue
services/api/kirchhoff/api/app.py        (modify) include the inbox router
services/api/tests/inbox/                (create) conftest.py, test_inbox_fit.py, test_inbox_triage.py, test_inbox_precompute.py
services/api/tests/api/test_api_inbox.py (create); tests/api/conftest.py (append inbox_ready)
apps/web/src/
  lib/types.ts                     (modify) InboxSnapshot, InboxEmail, TriageResult, PursueResult …
  data/staticData.ts               (modify) loadInboxSnapshot
  services/apiClient.ts            (modify) inbox(), triage(), pursue(); error sentences
  inbox/useInbox.ts                (create) store: static first, live second; read state; overlays
  inbox/inboxMeta.ts               (create) verdict / verification / attachment-kind labels and icons
  inbox/EmailDetail.tsx            (create) chips, CRM link, fields, fit card, Pursue
  inbox/InboxPage.tsx              (create) list + detail at /app/inbox[/:emailId]
  inbox/TriageButton.tsx           (create, [cut]) live triage on Hall B with fallback
  inbox/inboxTour.ts               (create) optional tour hook (not in TOUR_STEPS)
  App.tsx, pages/Dashboard.tsx, shell/AppShell.tsx   (modify) route, "Bids inbox · N new", nav link
  test/fixtures/inbox.json, test/fixtures/index.ts, test/render.tsx   (create/modify)
  inbox/InboxPage.test.tsx, inbox/TriageButton.test.tsx ([cut])   (create)
  pages/Dashboard.test.tsx, services/apiClient.test.ts             (modify: append tests)
```

**HTTP API table additions** (append to the interfaces doc when this lands):

| Method | Path | Body → Response |
|---|---|---|
| GET | `/api/inbox` | → `InboxSnapshot` (seed + the visitor's overlay: each email gains `status: "new"\|"triaged"\|"pursued"` and `pursue: PursueResult \| null`); 503 `{detail: "inbox_unavailable"}` |
| POST | `/api/inbox/{email_id}/triage` | → `TriageResult` (Hall B email only); 404 `email_not_found`, 409 `precomputed`, 429 `triage_rate_limit`, 502 `triage_failed`, 504 `timeout` |
| POST | `/api/inbox/{email_id}/pursue` | → `PursueResult`; 404 `email_not_found`, 409 `not_triaged` / `cannot_pursue`, 502 `enterprise_unavailable` |

Enterprise service addition: `POST /crm/opportunities {uid, opportunity}` → `Opportunity` (422 if the id is a seed opportunity or the stage is unknown).

---

### Task I-1 (WS4): Seeded bids mailbox, rendered attachments and appetite rules

Spec §20 and §13: the `bids@meridian-power.example` mailbox holds six emails in the demo world, in this order: the Deccan Compute Hall B tender, a Konkan Cloud clarification reply, a forwarded chain with a scanned BOQ, a Narmada Transmission 400 kV substation request, a vendor brochure and a thin Suryodaya Renewables solar enquiry. `world.yaml` stays the single authored source. It holds the emails (sender, subject, received offset over the past 10 days, body, attachment references) and the appetite rules: asset packs, MW range, regions, minimum days to the bid deadline and the lead-time check. A deterministic generator writes the static bundle (`/demo/inbox.json` and `/demo/inbox/*.pdf`) and the API copy (`scenarios/demo_world/out/inbox_seed.json` and `out/inbox/*.pdf`). The existing seed loader loads Firestore `seed/inbox`. This task also gives the CRM sandbox what Pursue needs (rulings B1, B2): per-visitor opportunity creation in the sandbox, its service and both clients, at the existing "Qualification" stage (unchanged, not renamed). **Every step of this task is [cut-safe].**

**Branch:** `jd/inbox-i1`, cut from `build`.

**Conflicts with in-flight work:** none of this task's existing-file edits fall inside a live workstream's files. The live edits to watch are P4 Task 11 (`scenarios/demo_world/build.py`, `kirchhoff/enterprise/world/{feed,build}.py`, `apps/web/public/demo/**`); this task edits `scenarios/demo_world/world.yaml` (append-only, a different file from `build.py`), creates `scenarios/demo_world/build_inbox.py` (new file) and `kirchhoff/enterprise/world/inbox.py` (new file, not `feed.py`/`build.py`), and only generates new paths under `apps/web/public/demo/` (`inbox.json`, `inbox/*.pdf`) that P4 Task 11 does not write. The one real touch point: `make demo-world` also re-runs P4 Task 11's `build.py`, so Step 9's regenerated `apps/web/public/demo/world.json`/`integrations.json` are staged (`git add -u`) only if P4 Task 11 has already landed on `build` (Step 10 already conditions this). It also modifies `services/api/kirchhoff/enterprise/{sandbox.py,app.py,client.py,seed_cli.py}` and `services/api/kirchhoff/enterprise/world/config.py`, none of which are in any live workstream's edit list.

**Files:**
- Modify: `scenarios/demo_world/world.yaml` (append-only: add the `inbox:` block at the end of the file; the existing "Qualification" stage and seeded opportunities are untouched)
- Modify: `services/api/kirchhoff/enterprise/world/config.py` (inbox config models; `WorldConfig.inbox`)
- Create: `services/api/kirchhoff/enterprise/world/inbox.py`, `scenarios/demo_world/build_inbox.py`
- Modify: `services/api/kirchhoff/enterprise/sandbox.py`, `services/api/kirchhoff/enterprise/app.py`, `services/api/kirchhoff/enterprise/client.py`, `services/api/kirchhoff/enterprise/seed_cli.py`, `Makefile` (`demo-world` target)
- Test: `services/api/tests/enterprise/test_world_inbox.py` (create); `services/api/tests/enterprise/test_enterprise_sandbox.py`, `test_enterprise_http.py`, `test_enterprise_seed_cli.py` (append; one test in `test_enterprise_http.py` is rewritten)
- Generated (committed): `apps/web/public/demo/inbox.json`, `apps/web/public/demo/inbox/*.pdf`, `scenarios/demo_world/out/inbox_seed.json`, `scenarios/demo_world/out/inbox/*.pdf`, the regenerated `scenarios/demo_world/out/enterprise_seed.json`, and, only if P4 Task 11 has landed, the regenerated tracked files under `apps/web/public/demo/` and `scenarios/demo_world/out/manifest.json`

**Interfaces:**
- Consumes: `WorldConfig`, `rng_for`, `load_world_config`, `DAY_S` (P4 Task 4 `kirchhoff.enterprise.world.config`); `FICTIONAL_NOTICE`, `SANDBOX_LABEL`, `ILLUSTRATIVE` (P4 Task 1 `kirchhoff.enterprise.model`); `scenarios_dir()` (P4 Task 1 `kirchhoff.enterprise.paths`); `Sandbox`, `STAGES`, `OPPORTUNITIES`, `visitor_path`, `NotFound` (P4 Task 1); `LocalEnterpriseClient`, `HttpEnterpriseClient._call`, `create_enterprise_app`, `_guard` (P4 Task 2); `seed_cli.main` (P4 Task 4); `Store`, `MemoryStore`, `firestore_safe_problems` (P0 fix wave); WS2's `scenarios/hall_a/out/tender-hall-a.pdf` and `hall-a-plan.pdf`; conftest fixtures `world_cfg`, `scenarios_root`, `sandbox`, `small_seed` (P4 Tasks 1 and 4).
- Produces:
  - `kirchhoff.enterprise.world.config`: `RegionCfg(name, places)`, `Appetite(asset_types: list["datahall"|"grid"|"solar"], mw: tuple[float, float], regions: list[RegionCfg], min_days_to_bid_due: int, lead_time_check: bool = True)`, `InboxAttachmentCfg`, `InboxEmailCfg`, `InboxCfg(mailbox, appetite, emails)`, and `WorldConfig.inbox: InboxCfg | None`.
  - `kirchhoff.enterprise.world.inbox`:
    - Constants: `INBOX_JSON = "apps/web/public/demo/inbox.json"`, `INBOX_DIR = "apps/web/public/demo/inbox"`, `INBOX_SEED = "scenarios/demo_world/out/inbox_seed.json"`, `INBOX_OUT_DIR = "scenarios/demo_world/out/inbox"`, `TRIAGE_CAPTURE = "scenarios/demo_world/captures/inbox-triage.json"`, `SEED_DOC = "seed/inbox"`, `SEED_EMAILS = "seed/inbox/emails"`, `CAPTURE_VERSION = 1`.
    - Models (re-exports `Appetite`): `InboxAttachment(id, name, url, source, content_type="application/pdf")`, where `url` is the browser URL and `source` is the path under the scenarios dir. `InboxEmail(id, from_name, from_addr, from_org, to, subject, received_at: float, body, attachments, project_id: str | None, live_triage: bool, triage: dict | None)`. `InboxSeed(mailbox, label="sandbox (simulated)", notice, as_of: float, appetite, emails)`, with emails newest first.
    - Functions: `InboxBuild(seed, files)` with `.digest()`; `build_inbox(cfg, scenarios_root, triage: dict[str, dict] | None = None) -> InboxBuild`; `write_inbox(build, root) -> list[str]`; `inbox_diff_on_disk(build, root) -> list[str]`; `load_triage_capture(path) -> dict[str, dict]`, which reads `{"version": 1, "results": {email_id: TriageResult JSON}}`; `inbox_seed_path() -> Path`; `load_inbox_seed(path) -> InboxSeed`; `load_inbox(store, seed) -> int`; `letter_pdf(title, lines) -> bytes`; `scan_pdf(title, lines, rng) -> bytes`.
  - Sandbox and clients:
    - `STAGES` is unchanged: `("Qualification", "Proposal", "Negotiation", "Design in progress", "Design approved", "Closed won", "Closed lost")`.
    - `Sandbox.create_opportunity(uid, opportunity: Opportunity) -> Opportunity` is idempotent by id. It raises `ValueError` for a seed id, a bad id or an unknown stage.
    - `Sandbox.list_opportunities(uid)` includes the visitor's created opportunities.
    - kirchhoff-enterprise serves `POST /crm/opportunities {uid, opportunity}`.
    - `LocalEnterpriseClient.create_opportunity(uid, opportunity)` and `HttpEnterpriseClient.create_opportunity(uid, opportunity)` return an `Opportunity`.
  - `seed_cli.main` takes `--inbox PATH` (default `inbox_seed_path()`), reports `inbox_emails`, and on a real run writes `seed/inbox` (reported as `inbox_written`).
  - CLI `scenarios/demo_world/build_inbox.py [--check]`; `make demo-world` runs it after `build.py`.
  - The six email ids, newest first: `em-hall-b` (live triage, `project_id: hall-b`), `em-tapti-brochure`, `em-konkan-rfi`, `em-vindhya-boq`, `em-suryodaya-solar`, `em-narmada-400kv`. Attachment ids: `att-hall-b-tender`, `att-hall-b-drawing`, `att-hall-b-addendum`, `att-tapti-brochure`, `att-konkan-rfi`, `att-vindhya-boq` (scanned), `att-narmada-spec`.

- [ ] **Step 1 [cut-safe]: Write the failing tests**

`services/api/tests/enterprise/test_world_inbox.py`:
```python
import io
import json

import pdfplumber
import pytest

from kirchhoff.enterprise.model import FICTIONAL_NOTICE, ILLUSTRATIVE
from kirchhoff.enterprise.world.inbox import (INBOX_DIR, INBOX_JSON, INBOX_OUT_DIR, INBOX_SEED, SEED_DOC, SEED_EMAILS,
                                              InboxSeed, build_inbox, inbox_diff_on_disk, load_inbox,
                                              load_triage_capture, write_inbox)
from kirchhoff.store.memory import MemoryStore

DAY = 86400.0


@pytest.fixture(scope="module")
def build(world_cfg, scenarios_root):
    return build_inbox(world_cfg, scenarios_root)


def _text(pdf: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        return " ".join(" ".join((p.extract_text() or "").split()) for p in doc.pages)


def test_the_six_spec_20_emails_newest_first(build, world_cfg):
    seed = build.seed
    assert seed.mailbox == "bids@meridian-power.example" and seed.label == "sandbox (simulated)"
    assert seed.notice == FICTIONAL_NOTICE and seed.as_of == world_cfg.now
    assert [e.id for e in seed.emails] == ["em-hall-b", "em-tapti-brochure", "em-konkan-rfi", "em-vindhya-boq",
                                           "em-suryodaya-solar", "em-narmada-400kv"]
    assert all(world_cfg.now - 10 * DAY <= e.received_at <= world_cfg.now for e in seed.emails)
    assert [e.id for e in seed.emails if e.live_triage] == ["em-hall-b"]
    hall_b = seed.emails[0]
    assert hall_b.project_id == "hall-b" and hall_b.to == seed.mailbox
    assert [(a.id, a.url, a.source) for a in hall_b.attachments] == [
        ("att-hall-b-tender", "/demo/docs/tender-hall-a.pdf", "hall_a/out/tender-hall-a.pdf"),
        ("att-hall-b-drawing", "/demo/docs/hall-a-plan.pdf", "hall_a/out/hall-a-plan.pdf"),
        ("att-hall-b-addendum", "/demo/inbox/hall-b-addendum-1.pdf", "demo_world/out/inbox/hall-b-addendum-1.pdf")]
    assert {e.id: len(e.attachments) for e in seed.emails}["em-suryodaya-solar"] == 0
    assert all(e.triage is None for e in seed.emails)


def test_appetite_rules(build):
    a = build.seed.appetite
    assert a.asset_types == ["datahall", "grid", "solar"] and a.mw == (2.0, 120.0)
    assert a.min_days_to_bid_due == 10 and a.lead_time_check is True
    assert [r.name for r in a.regions] == ["Telangana", "Andhra Pradesh", "Karnataka", "Maharashtra", "Madhya Pradesh"]


def test_attachments_are_deterministic_and_labelled(build, world_cfg, scenarios_root):
    assert build_inbox(world_cfg, scenarios_root).digest() == build.digest()
    addendum = _text(build.files[f"{INBOX_DIR}/hall-b-addendum-1.pdf"])
    for quote in ("Hall B IT load: 6.336 MW", "Bids are due by 13 November 2026",
                  "no later than 26 weeks from contract award", ILLUSTRATIVE, "Demo workspace - all companies"):
        assert quote in addendum, quote
    with pdfplumber.open(io.BytesIO(build.files[f"{INBOX_DIR}/vindhya-boq-scan.pdf"])) as scan:
        assert len(scan.pages) == 1 and not scan.pages[0].extract_text() and len(scan.pages[0].images) == 1


def test_static_and_api_copies_are_identical(build, scenarios_root):
    assert build.files[INBOX_JSON] == build.files[INBOX_SEED]
    assert InboxSeed.model_validate_json(build.files[INBOX_JSON]) == build.seed
    web = {k.rsplit("/", 1)[1]: v for k, v in build.files.items() if k.startswith(INBOX_DIR + "/")}
    api = {k.rsplit("/", 1)[1]: v for k, v in build.files.items() if k.startswith(INBOX_OUT_DIR + "/")}
    assert web == api and sorted(web) == ["hall-b-addendum-1.pdf", "konkan-rfi-response.pdf",
                                          "narmada-400kv-spec.pdf", "tapti-brochure.pdf", "vindhya-boq-scan.pdf"]
    assert all((scenarios_root / a.source).is_file() for e in build.seed.emails for a in e.attachments
               if a.source.startswith("hall_a/"))


def test_triage_capture_is_folded_in_and_checked(world_cfg, scenarios_root, tmp_path):
    result = {"email_id": "em-hall-b", "fit": {"verdict": "pursue"}}
    seed = build_inbox(world_cfg, scenarios_root, {"em-hall-b": result}).seed
    assert next(e for e in seed.emails if e.id == "em-hall-b").triage == result
    with pytest.raises(ValueError, match="unknown emails"):
        build_inbox(world_cfg, scenarios_root, {"em-nope": {"email_id": "em-nope"}})
    with pytest.raises(ValueError, match="carries email_id"):
        build_inbox(world_cfg, scenarios_root, {"em-hall-b": {"email_id": "em-konkan-rfi"}})
    assert load_triage_capture(tmp_path / "missing.json") == {}
    capture = tmp_path / "inbox-triage.json"
    capture.write_text(json.dumps({"version": 1, "results": {"em-hall-b": result}}), encoding="utf-8")
    assert load_triage_capture(capture) == {"em-hall-b": result}
    capture.write_text(json.dumps({"version": 2, "results": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="version"):
        load_triage_capture(capture)


def test_write_prunes_stale_files_and_check_detects_drift(build, tmp_path):
    stale = tmp_path / INBOX_DIR / "old.pdf"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"%PDF")
    write_inbox(build, tmp_path)
    assert not stale.exists() and inbox_diff_on_disk(build, tmp_path) == []
    (tmp_path / INBOX_JSON).write_text("{}", encoding="utf-8")
    (tmp_path / INBOX_OUT_DIR / "extra.pdf").write_bytes(b"%PDF")
    assert inbox_diff_on_disk(build, tmp_path) == [INBOX_JSON, f"{INBOX_OUT_DIR}/extra.pdf"]


def test_seed_loader_writes_seed_inbox(build):
    store = MemoryStore()
    store.set_doc(f"{SEED_EMAILS}/em-stale", {"id": "em-stale"})
    assert load_inbox(store, build.seed) == 6
    meta = store.get_doc(SEED_DOC)
    assert "emails" not in meta and meta["as_of"] == build.seed.as_of and meta["appetite"]["mw"] == [2.0, 120.0]
    assert sorted(d["id"] for d in store.list_docs(SEED_EMAILS)) == sorted(e.id for e in build.seed.emails)
```

Append to `services/api/tests/enterprise/test_enterprise_sandbox.py`:
```python


def test_visitor_created_opportunities(sandbox):
    from kirchhoff.contracts import Opportunity
    from kirchhoff.enterprise.sandbox import STAGES

    assert "Qualification" in STAGES  # existing stage; unchanged by this task (ruling B1)
    opp = Opportunity(id="opp-em-suryodaya-solar", account="Suryodaya Renewables",
                      name="Enquiry: solar EPC near Anantapur", stage="Qualification", value=0.0)
    assert sandbox.create_opportunity("u1", opp) == opp
    assert sandbox.create_opportunity("u1", opp.model_copy(update={"name": "changed"})).name == opp.name  # idempotent
    assert opp.id in {o.id for o in sandbox.list_opportunities("u1")}
    assert opp.id not in {o.id for o in sandbox.list_opportunities("u2")} | {o.id for o in sandbox.list_opportunities(None)}
    assert sandbox.set_opportunity_stage("u1", "opp-hall-b", "Qualification").stage == "Qualification"
    with pytest.raises(ValueError):
        sandbox.create_opportunity("u1", opp.model_copy(update={"id": "opp-hall-b"}))  # a seed opportunity
    with pytest.raises(ValueError):
        sandbox.create_opportunity("u1", opp.model_copy(update={"id": "opp-x", "stage": "Shipped"}))
    sandbox.reset_visitor("u1")
    assert opp.id not in {o.id for o in sandbox.list_opportunities("u1")}
```

Append to `services/api/tests/enterprise/test_enterprise_http.py`:
```python


def test_http_client_creates_visitor_opportunities(http_client):
    from kirchhoff.contracts import Opportunity

    opp = Opportunity(id="opp-em-x", account="Suryodaya Renewables", name="Enquiry", stage="Qualification", value=0.0)
    assert http_client.create_opportunity("u1", opp) == opp
    assert "opp-em-x" in {o.id for o in http_client.list_opportunities("u1")}
    with pytest.raises(ValueError):
        http_client.create_opportunity("u1", opp.model_copy(update={"id": "opp-hall-b"}))
```

In the same file, replace the body of `test_clients_match_the_ws2_enterprise_protocol`, so it checks every method WS2's protocol declares. I-2 adds two; the test must not need editing then:
```python
def test_clients_match_the_ws2_enterprise_protocol():
    ports = pytest.importorskip("kirchhoff.agents.ports")
    names = [n for n in vars(ports.EnterpriseClient) if not n.startswith("_")]  # grows with WS2's protocol
    assert {"list_materials", "create_pr", "set_pr_status", "set_opportunity_stage", "reset_visitor"} <= set(names)
    for name in names:
        want = list(inspect.signature(getattr(ports.EnterpriseClient, name)).parameters)
        for cls in (LocalEnterpriseClient, HttpEnterpriseClient):
            assert list(inspect.signature(getattr(cls, name)).parameters) == want, (cls.__name__, name)
```

Append to `services/api/tests/enterprise/test_enterprise_seed_cli.py`:
```python


def test_dry_run_reports_the_inbox(tmp_path, small_seed, capsys):
    seed = tmp_path / "seed.json"
    seed.write_text(small_seed.model_dump_json(), encoding="utf-8")
    assert main(["--seed", str(seed), "--inbox", str(tmp_path / "none.json"), "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["inbox_emails"] == 0
```

- [ ] **Step 2 [cut-safe]: Run to verify failure**

Run: `cd services/api && uv run pytest tests/enterprise -q`
Expected: collection ERROR in `test_world_inbox.py` with `ModuleNotFoundError: No module named 'kirchhoff.enterprise.world.inbox'`.

- [ ] **Step 3 [cut-safe]: Author the mailbox and the appetite rules in `world.yaml`**

`scenarios/demo_world/world.yaml` is append-only for this task: `opp-hall-c` and `opp-vindhya-cpp` keep `stage: Qualification` unchanged (ruling B1 — no rename, no touching seeded data). Append at the end of the file:
```yaml
inbox:                     # spec §20: the bids@ mailbox (sandbox, simulated). Every sender, company and document is fictional.
  mailbox: bids@meridian-power.example
  appetite:                # deterministic fit rules (WS2 kirchhoff/inbox/fit.py)
    asset_types: [datahall, grid, solar]
    mw: [2, 120]
    regions:
      - {name: Telangana, places: [Telangana, Hyderabad]}
      - {name: Andhra Pradesh, places: [Andhra Pradesh, Anantapur, Visakhapatnam]}
      - {name: Karnataka, places: [Karnataka, Bengaluru]}
      - {name: Maharashtra, places: [Maharashtra, Pune, Mumbai]}
      - {name: Madhya Pradesh, places: [Madhya Pradesh, Satna]}
    min_days_to_bid_due: 10
    lead_time_check: true
  emails:
    - id: em-hall-b
      from_name: Ananya Reddy
      from_addr: ananya.reddy@deccan-compute.example
      from_org: Deccan Compute
      subject: "Tender: Deccan AI Campus Hall B, electrical and liquid-cooling design-build"
      days_ago: 0.125
      project_id: hall-b
      live_triage: true
      body: |
        Dear Meridian bids team,

        Deccan Compute invites your bid for the electrical and liquid-cooling design-build of Data Hall B at our AI campus near Hyderabad, Telangana.

        Hall B is a twin of Hall A: the attached technical requirements DC-HA-TS-001 Rev 0 apply to Hall B without change, as Addendum 1 confirms. Hall B carries 6.336 MW of IT load in 48 racks.

        Bids are due by 13 November 2026. Please note the programme clause: all major equipment must be on site no later than 26 weeks from contract award.

        Regards,
        Ananya Reddy
        Procurement, Deccan Compute
      attachments:
        - {id: att-hall-b-tender, name: "DC-HA-TS-001 Rev 0 technical requirements.pdf", reuse: tender-hall-a.pdf}
        - {id: att-hall-b-drawing, name: "Data hall general arrangement.pdf", reuse: hall-a-plan.pdf}
        - id: att-hall-b-addendum
          name: "Addendum 1, Hall B.pdf"
          file: hall-b-addendum-1.pdf
          render: letter
          title: "Addendum 1 to DC-HA-TS-001 Rev 0: Deccan AI Campus, Hall B"
          lines:
            - "A1.1 The technical requirements DC-HA-TS-001 Rev 0, issued for Hall A, apply to Hall B without change."
            - "A1.2 Hall B IT load: 6.336 MW in 48 racks of 132 kW."
            - "A1.3 Bids are due by 13 November 2026, 17:00 IST."
            - "A1.4 Clause §2.3 is unchanged: equipment on site no later than 26 weeks from contract award."
            - "Issued by Deccan Compute, Procurement."
    - id: em-tapti-brochure
      from_name: Tapti Transformers
      from_addr: sales@tapti-transformers.example
      from_org: Tapti Transformers
      subject: "New: cast-resin transformers ex-stock"
      days_ago: 1.0625
      body: |
        Dear partner,

        Our cast-resin transformer range is now available ex-stock from our Vadodara works. The brochure is attached.

        Tapti Transformers sales team
      attachments:
        - id: att-tapti-brochure
          name: "Tapti cast-resin range.pdf"
          file: tapti-brochure.pdf
          render: letter
          title: "Tapti Transformers: cast-resin range"
          lines:
            - "Cast-resin transformers, 33/0.415 kV, Dyn11, from 1.6 to 3.15 MVA."
            - "Selected ratings ship ex-stock from our Vadodara works."
            - "Ask your Tapti account manager for current stock."
    - id: em-konkan-rfi
      from_name: Vikram Joshi
      from_addr: vikram.joshi@konkan-cloud.example
      from_org: Konkan Cloud
      subject: "RE: Pune Edge Phase 1, RFI on CDU gallery access"
      days_ago: 2.875
      body: |
        Hi Kavya,

        Thanks for the RFI on the CDU gallery access door. Confirmed: the door stays on the north wall as drawn, so there is no change to the signed Pune Edge Phase 1 design. Our signed response is attached.

        Regards,
        Vikram Joshi
        Konkan Cloud
      attachments:
        - id: att-konkan-rfi
          name: "RFI response, CDU gallery access.pdf"
          file: konkan-rfi-response.pdf
          render: letter
          title: "Konkan Cloud: response to Meridian RFI, Pune Edge Phase 1"
          lines:
            - "Subject: CDU gallery access door."
            - "Response: the access door remains on the north wall of the CDU gallery as drawn. No design change is required."
            - "Signed for Konkan Cloud, site engineering."
    - id: em-vindhya-boq
      from_name: Neha Kapoor
      from_addr: neha.kapoor@meridian-power.example
      from_org: Vindhya Steel
      subject: "FW: Captive power switchyard, BOQ for pricing"
      days_ago: 4.0
      body: |
        Forwarding from Vindhya Steel. Their BOQ only exists as a scan; can we bid?
        Neha

        ---------- Forwarded message ----------
        From: Sanjay Verma <sanjay.verma@vindhya-steel.example>
        Subject: Captive power switchyard, BOQ for pricing

        Please price the attached BOQ for the 33 kV captive power switchyard at our Satna mill, Madhya Pradesh. Bids are due by 30 October 2026.

        Sanjay Verma
        Vindhya Steel
      attachments:
        - id: att-vindhya-boq
          name: "Switchyard BOQ (scan).pdf"
          file: vindhya-boq-scan.pdf
          render: scan
          title: "BILL OF QUANTITIES: 33 kV CAPTIVE POWER SWITCHYARD"
          lines:
            - "Client: Vindhya Steel, Satna mill"
            - "Plant load: 40 MW"
            - "1   33 kV VCB panel, 1250 A                  6 nos"
            - "2   33 kV XLPE cable 3C x 300 mm2         2400 m"
            - "3   Numerical feeder protection relay        6 nos"
            - "4   Current transformer 33 kV 1200/1 A      18 nos"
    - id: em-suryodaya-solar
      from_name: Meera Iyer
      from_addr: meera.iyer@suryodaya-renewables.example
      from_org: Suryodaya Renewables
      subject: "Enquiry: solar EPC near Anantapur"
      days_ago: 6.0625
      body: |
        Hello,

        Suryodaya Renewables is planning a 20 MWp ground-mount solar plant near Anantapur, Andhra Pradesh, and would like Meridian to bid for the EPC. We will share the tender documents soon. Could you confirm your interest?

        Best regards,
        Meera Iyer
        Suryodaya Renewables
    - id: em-narmada-400kv
      from_name: Rakesh Patel
      from_addr: rakesh.patel@narmada-transmission.example
      from_org: Narmada Transmission
      subject: "RFQ: 400 kV GIS substation at Bharuch, EPC"
      days_ago: 8.9375
      body: |
        Dear Sir or Madam,

        Narmada Transmission requests EPC quotations for a new 400 kV GIS substation at Bharuch, Gujarat. The specification is attached. Quotations are due by 20 November 2026.

        Rakesh Patel
        Narmada Transmission
      attachments:
        - id: att-narmada-spec
          name: "NT-400-BH specification.pdf"
          file: narmada-400kv-spec.pdf
          render: letter
          title: "Narmada Transmission: 400/220 kV GIS substation, Bharuch (NT-400-BH)"
          lines:
            - "1. Scope: EPC of a new 400/220 kV gas-insulated substation at Bharuch, Gujarat."
            - "2. Transformation: two 500 MVA 400/220 kV autotransformers."
            - "3. Quotations are due by 20 November 2026."
            - "Issued by Narmada Transmission."
```

The bodies and PDF lines are the ground truth the Inbox agent's quotes are verified against (I-2's `FAKE_REPLIES` quote them verbatim). Do not reword them without updating I-2.

- [ ] **Step 4 [cut-safe]: Type the inbox config**

In `services/api/kirchhoff/enterprise/world/config.py`, insert these classes directly above `class WorldConfig(_M):`:
```python
class RegionCfg(_M):
    name: str
    places: list[str]  # case-insensitive substrings of the extracted site that place it in this region


class Appetite(_M):
    """The firm's bid appetite (spec §20): the deterministic fit rules WS2's kirchhoff.inbox.fit applies."""
    asset_types: list[Literal["datahall", "grid", "solar"]]
    mw: tuple[float, float]
    regions: list[RegionCfg]
    min_days_to_bid_due: int
    lead_time_check: bool = True


class InboxAttachmentCfg(_M):
    id: str
    name: str
    reuse: str | None = None  # a WS2-rendered PDF in scenarios/hall_a/out/, served at /demo/docs/{reuse}
    file: str | None = None  # a PDF rendered by the inbox generator into /demo/inbox/{file}
    render: Literal["letter", "scan"] | None = None
    title: str = ""
    lines: list[str] = []


class InboxEmailCfg(_M):
    id: str
    from_name: str
    from_addr: str
    from_org: str
    subject: str
    days_ago: float
    body: str
    attachments: list[InboxAttachmentCfg] = []
    project_id: str | None = None  # an existing world project this email is about (hall-b)
    live_triage: bool = False


class InboxCfg(_M):
    mailbox: str
    appetite: Appetite
    emails: list[InboxEmailCfg]
```

and add one field to `WorldConfig`, after `activity: list[ActivityCfg] = []`:
```python
    inbox: InboxCfg | None = None
```

- [ ] **Step 5 [cut-safe]: Implement the inbox generator and seed loader**

`services/api/kirchhoff/enterprise/world/inbox.py`:
```python
"""The bids inbox of the demo world (spec §20): the bids@ mailbox (sandbox, simulated), its rendered attachments and
the Firestore seed. Deterministic for a given world.yaml: reportlab invariant, seeded scan noise, no wall clock.
The precomputed triage comes from scenarios/demo_world/captures/inbox-triage.json, which WS2's
`python -m kirchhoff.inbox.precompute` writes at golden-capture time (addendum ruling B5)."""
import hashlib
import io
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from pydantic import BaseModel, ConfigDict

from kirchhoff.store import Store
from kirchhoff.store.validate import firestore_safe_problems

from ..model import FICTIONAL_NOTICE, ILLUSTRATIVE, SANDBOX_LABEL
from ..paths import scenarios_dir
from .config import Appetite, InboxAttachmentCfg, WorldConfig, rng_for

__all__ = ["Appetite", "InboxAttachment", "InboxEmail", "InboxSeed", "InboxBuild", "build_inbox", "write_inbox",
           "inbox_diff_on_disk", "load_inbox", "load_inbox_seed", "inbox_seed_path", "load_triage_capture",
           "letter_pdf", "scan_pdf"]

DEMO = "apps/web/public/demo"
INBOX_JSON = f"{DEMO}/inbox.json"
INBOX_DIR = f"{DEMO}/inbox"
INBOX_SEED = "scenarios/demo_world/out/inbox_seed.json"
INBOX_OUT_DIR = "scenarios/demo_world/out/inbox"
TRIAGE_CAPTURE = "scenarios/demo_world/captures/inbox-triage.json"
MANAGED_DIRS = (INBOX_DIR, INBOX_OUT_DIR)
SEED_DOC = "seed/inbox"
SEED_EMAILS = "seed/inbox/emails"
CAPTURE_VERSION = 1


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InboxAttachment(_M):
    id: str
    name: str
    url: str  # browser URL: /demo/docs/{reuse} (WS3 sync script) or /demo/inbox/{file}
    source: str  # path under the scenarios dir: hall_a/out/{reuse} or demo_world/out/inbox/{file}
    content_type: str = "application/pdf"


class InboxEmail(_M):
    id: str
    from_name: str
    from_addr: str
    from_org: str
    to: str
    subject: str
    received_at: float
    body: str
    attachments: list[InboxAttachment] = []
    project_id: str | None = None
    live_triage: bool = False
    triage: dict[str, Any] | None = None  # WS2 TriageResult JSON (precomputed); null until captured


class InboxSeed(_M):
    mailbox: str
    label: str = SANDBOX_LABEL
    notice: str = FICTIONAL_NOTICE
    as_of: float  # the world anchor: days to a bid deadline are counted from here, never from the wall clock
    appetite: Appetite
    emails: list[InboxEmail]  # newest first


@dataclass
class InboxBuild:
    seed: InboxSeed
    files: dict[str, bytes] = field(default_factory=dict)  # repo-relative path -> bytes

    def digest(self) -> str:
        manifest = {rel: hashlib.sha256(data).hexdigest() for rel, data in sorted(self.files.items())}
        return hashlib.sha256(json.dumps(manifest, sort_keys=True).encode("utf-8")).hexdigest()


_SUBST = {"—": "-", "–": "-", "·": "-", "≤": "<=", "≥": ">=", "→": "->"}


def _latin1(s: str) -> str:
    text = "".join(_SUBST.get(ch, ch) for ch in s)
    return text.encode("latin-1", "replace").decode("latin-1")


def letter_pdf(title: str, lines: list[str]) -> bytes:
    """A one-page text PDF (pdfplumber can verify quotes on it), with the illustrative and fictional labels."""
    from reportlab import rl_config

    rl_config.invariant = 1
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=13, leading=17, spaceAfter=8)
    body = ParagraphStyle("b", fontName="Helvetica", fontSize=10, leading=14, spaceAfter=6)
    note = ParagraphStyle("n", fontName="Helvetica-Oblique", fontSize=8, leading=10, textColor=colors.grey)
    story = [Paragraph(escape(_latin1(title)), h1)]
    story += [Paragraph(escape(_latin1(line)), body) for line in lines]
    story += [Spacer(1, 8 * mm), Paragraph(escape(_latin1(ILLUSTRATIVE)), note),
              Paragraph(escape(_latin1(FICTIONAL_NOTICE)), note)]
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, title=_latin1(title), author="Kirchhoff demo world", leftMargin=20 * mm,
                      rightMargin=20 * mm, topMargin=20 * mm, bottomMargin=20 * mm).build(story)
    return buf.getvalue()


def scan_pdf(title: str, lines: list[str], rng: random.Random) -> bytes:
    """A one-page image-only PDF that looks like a scan: no text layer, so pdfplumber finds nothing and the trust
    rules mark anything read from it "unverified (scan)" (spec §20); Gemini can still read the image."""
    from PIL import Image, ImageDraw, ImageFont
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    w, h = 1240, 1754  # A4 at 150 dpi
    img = Image.new("L", (w, h), 244)
    draw = ImageDraw.Draw(img)
    draw.text((110, 130), _latin1(title), fill=20, font=ImageFont.load_default(size=36))
    y = 230
    for line in lines:
        draw.text((110, y), _latin1(line), fill=35, font=ImageFont.load_default(size=28))
        y += 56
    small = ImageFont.load_default(size=20)
    draw.text((110, h - 150), _latin1(ILLUSTRATIVE), fill=90, font=small)
    draw.text((110, h - 118), _latin1(FICTIONAL_NOTICE), fill=90, font=small)
    for _ in range(2500):  # scanner speckle, seeded
        img.putpixel((rng.randrange(w), rng.randrange(h)), rng.randrange(150, 235))
    img = img.rotate(0.6, resample=Image.Resampling.BILINEAR, fillcolor=244)
    png = io.BytesIO()
    img.save(png, format="PNG")
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4, invariant=1)
    c.setTitle(_latin1(title))
    c.setAuthor("Kirchhoff demo world")
    c.drawImage(ImageReader(io.BytesIO(png.getvalue())), 0, 0, width=A4[0], height=A4[1])
    c.showPage()
    c.save()
    return buf.getvalue()


def _attachment(cfg: WorldConfig, email_id: str, a: InboxAttachmentCfg, scenarios_root: Path,
                files: dict[str, bytes]) -> InboxAttachment:
    if (a.reuse is None) == (a.file is None):
        raise ValueError(f"{email_id}/{a.id}: set exactly one of reuse and file")
    if a.reuse is not None:
        if not (scenarios_root / "hall_a" / "out" / a.reuse).is_file():
            raise FileNotFoundError(f"{email_id}/{a.id}: scenarios/hall_a/out/{a.reuse} is missing (WS2 renders it)")
        return InboxAttachment(id=a.id, name=a.name, url=f"/demo/docs/{a.reuse}", source=f"hall_a/out/{a.reuse}")
    if a.render == "letter":
        data = letter_pdf(a.title, a.lines)
    elif a.render == "scan":
        data = scan_pdf(a.title, a.lines, rng_for(cfg, f"inbox:{a.id}"))
    else:
        raise ValueError(f"{email_id}/{a.id}: render must be letter or scan")
    files[f"{INBOX_DIR}/{a.file}"] = data
    files[f"{INBOX_OUT_DIR}/{a.file}"] = data
    return InboxAttachment(id=a.id, name=a.name, url=f"/demo/inbox/{a.file}",
                           source=f"demo_world/out/inbox/{a.file}")


def build_inbox(cfg: WorldConfig, scenarios_root: Path, triage: dict[str, dict] | None = None) -> InboxBuild:
    if cfg.inbox is None:
        raise ValueError("world.yaml has no inbox section")
    scenarios_root = Path(scenarios_root)
    triage = dict(triage or {})
    ids = [e.id for e in cfg.inbox.emails]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate email ids: {sorted({i for i in ids if ids.count(i) > 1})}")
    unknown = sorted(set(triage) - set(ids))
    if unknown:
        raise ValueError(f"triage for unknown emails: {unknown}")
    files: dict[str, bytes] = {}
    emails = []
    for e in cfg.inbox.emails:
        result = triage.get(e.id)
        if result is not None and result.get("email_id") != e.id:
            raise ValueError(f"triage for {e.id} carries email_id {result.get('email_id')!r}")
        emails.append(InboxEmail(
            id=e.id, from_name=e.from_name, from_addr=e.from_addr, from_org=e.from_org, to=cfg.inbox.mailbox,
            subject=e.subject, received_at=cfg.ts(e.days_ago), body=e.body.rstrip("\n"),
            attachments=[_attachment(cfg, e.id, a, scenarios_root, files) for a in e.attachments],
            project_id=e.project_id, live_triage=e.live_triage, triage=result))
    emails.sort(key=lambda m: (-m.received_at, m.id))
    seed = InboxSeed(mailbox=cfg.inbox.mailbox, as_of=cfg.now, appetite=cfg.inbox.appetite, emails=emails)
    data = (seed.model_dump_json(indent=2) + "\n").encode("utf-8")
    files[INBOX_JSON] = data  # static bundle (Hosting)
    files[INBOX_SEED] = data  # API image fallback + Firestore seed source
    return InboxBuild(seed=seed, files=files)


def load_triage_capture(path: Path) -> dict[str, dict]:
    """{email_id: TriageResult JSON} from WS2's precompute capture, or {} if it has not been captured yet."""
    path = Path(path)
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != CAPTURE_VERSION:
        raise ValueError(f"{path}: expected version {CAPTURE_VERSION}, got {data.get('version')!r}")
    return dict(data["results"])


def write_inbox(build: InboxBuild, root: Path) -> list[str]:
    root = Path(root)
    for d in MANAGED_DIRS:
        folder = root / d
        if folder.is_dir():
            for f in sorted(folder.iterdir()):
                if f.is_file() and f.relative_to(root).as_posix() not in build.files:
                    f.unlink()
    for rel, data in sorted(build.files.items()):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return sorted(build.files)


def inbox_diff_on_disk(build: InboxBuild, root: Path) -> list[str]:
    root = Path(root)
    stale = [rel for rel, data in sorted(build.files.items())
             if not (root / rel).exists() or (root / rel).read_bytes() != data]
    extra = [f.relative_to(root).as_posix() for d in MANAGED_DIRS if (root / d).is_dir()
             for f in sorted((root / d).iterdir()) if f.is_file() and f.relative_to(root).as_posix() not in build.files]
    return stale + extra


def inbox_seed_path() -> Path:
    return scenarios_dir() / "demo_world" / "out" / "inbox_seed.json"


def load_inbox_seed(path: Path | str) -> InboxSeed:
    return InboxSeed.model_validate_json(Path(path).read_text(encoding="utf-8"))


def load_inbox(store: Store, seed: InboxSeed) -> int:
    """Seed loader: seed/inbox (meta) and seed/inbox/emails/{id}, replacing whatever was there. API read-only."""
    meta = seed.model_dump(mode="json", exclude={"emails"})
    items = [(f"{SEED_EMAILS}/{e.id}", e.model_dump(mode="json")) for e in seed.emails]
    problems = [f"{path}: {p}" for path, doc in [(SEED_DOC, meta), *items] for p in firestore_safe_problems(doc)]
    if problems:
        raise ValueError("inbox seed is not Firestore-safe: " + "; ".join(problems[:5]))
    store.delete_tree(SEED_DOC)
    store.set_doc(SEED_DOC, meta)
    store.batch_set(items)
    return len(items)
```

Pillow is imported directly by `scan_pdf`. It is already locked (12.3.0) as a dependency of reportlab and pdfplumber, so `pyproject.toml` does not change. `ImageFont.load_default(size=…)` uses Pillow's bundled FreeType font, so the scan is byte-identical on every machine with the locked versions.

- [ ] **Step 6 [cut-safe]: Visitor-created opportunities in the sandbox, its service and both clients**

`services/api/kirchhoff/enterprise/sandbox.py`: `STAGES` is **not** modified (ruling B1 — it already reads `("Qualification", "Proposal", "Negotiation", "Design in progress", "Design approved", "Closed won", "Closed lost")`). Replace `list_opportunities` with these two methods:
```python
    def list_opportunities(self, uid: str | None) -> list[Opportunity]:
        opps = [Opportunity.model_validate(d) for d in self.store.list_docs(OPPORTUNITIES)]
        if not uid:
            return sorted(opps, key=lambda o: o.id)
        base = visitor_path(uid)
        opps += [Opportunity.model_validate(d) for d in self.store.list_docs(f"{base}/opportunities")]
        stages = {d["opportunity_id"]: d["stage"] for d in self.store.list_docs(f"{base}/crm")}
        return sorted((o.model_copy(update={"stage": stages[o.id]}) if o.id in stages else o for o in opps),
                      key=lambda o: o.id)

    def create_opportunity(self, uid: str, opportunity: Opportunity) -> Opportunity:
        """A visitor-created opportunity (bids inbox Pursue, spec §20; addendum ruling B2). Stored under
        sandbox_visitors/{uid}/opportunities, never in the seed; idempotent by id (the first write wins)."""
        base = visitor_path(uid)
        if not opportunity.id or "/" in opportunity.id:
            raise ValueError("opportunity id must be a non-empty string without '/'")
        if opportunity.stage not in STAGES:
            raise ValueError(f"stage must be one of {STAGES}")
        if self.store.get_doc(f"{OPPORTUNITIES}/{opportunity.id}") is not None:
            raise ValueError(f"{opportunity.id} is a seed opportunity; set its stage instead")
        path = f"{base}/opportunities/{opportunity.id}"
        out: dict = {}

        def fn(snap: dict) -> list:
            out.clear()  # Firestore may retry the transaction function
            if snap.get(path) is not None:
                out["existing"] = snap[path]
                return []
            return [(path, opportunity.model_dump(mode="json"))]

        self.store.transact([path], fn)
        return Opportunity.model_validate(out["existing"]) if "existing" in out else opportunity
```

`services/api/kirchhoff/enterprise/app.py`: change `from kirchhoff.contracts import PRLine` to `from kirchhoff.contracts import Opportunity, PRLine`. Add this model after `class SetStage`:
```python
class CreateOpportunity(BaseModel):
    uid: str
    opportunity: Opportunity
```
Then add this route directly above `@app.delete("/visitors/{uid}")`:
```python
    @app.post("/crm/opportunities")
    def create_opportunity(body: CreateOpportunity):
        return _guard(lambda: sandbox.create_opportunity(body.uid, body.opportunity).model_dump(mode="json"))

```

`services/api/kirchhoff/enterprise/client.py`: in `LocalEnterpriseClient`, after `set_opportunity_stage`, add
```python
    def create_opportunity(self, uid, opportunity) -> Opportunity:
        return self.sandbox.create_opportunity(uid, Opportunity.model_validate(opportunity))
```
and in `HttpEnterpriseClient`, after `set_opportunity_stage`, add (create is idempotent, so the existing one retry on 5xx is safe):
```python
    def create_opportunity(self, uid, opportunity) -> Opportunity:
        body = {"uid": uid, "opportunity": Opportunity.model_validate(opportunity).model_dump(mode="json")}
        return Opportunity.model_validate(self._call("POST", "/crm/opportunities", body=body))
```

- [ ] **Step 7 [cut-safe]: Seed loader, CLI and Make target**

`services/api/kirchhoff/enterprise/seed_cli.py`:
- Change the first docstring line to `"""Load the generated enterprise seed into Firestore (seed/erp/**, seed/crm/**), the bids inbox (seed/inbox, spec §20)`. The second line becomes `and upload the demo documents to Cloud Storage seed/files/ (ruling W10). Run from services/api:`.
- After `from .sandbox import Sandbox`, add `from .world.inbox import inbox_seed_path, load_inbox, load_inbox_seed`.
- Replace `main` with:
```python
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Load the Kirchhoff enterprise sandbox seed")
    ap.add_argument("--seed", type=Path, default=enterprise_seed_path())
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--docs", type=Path)
    ap.add_argument("--inbox", type=Path, default=inbox_seed_path())
    args = ap.parse_args(argv)
    seed = load_enterprise_seed(args.seed)
    inbox = load_inbox_seed(args.inbox) if args.inbox.is_file() else None  # exists once build_inbox.py has run
    report: dict = {"seed": str(args.seed), "hash": seed_hash(seed), "materials": len(seed.materials),
                    "prs": len(seed.prs), "opportunities": len(seed.opportunities),
                    "inbox_emails": len(inbox.emails) if inbox else 0}
    if not args.dry_run:
        from kirchhoff.store.firestore import FirestoreStore
        store = FirestoreStore()
        report["written"] = Sandbox(store).load_seed(seed)
        if inbox is not None:
            report["inbox_written"] = load_inbox(store, inbox)
        if args.docs and args.docs.is_dir():  # documents exist from Task 11 on
            report["docs"] = upload_docs(args.docs)
    print(json.dumps(report, indent=2))
    return 0
```

`scenarios/demo_world/build_inbox.py`:
```python
"""Build the bids inbox (spec §20): apps/web/public/demo/inbox.json + rendered attachments (static bundle) and
scenarios/demo_world/out/inbox_seed.json + the same attachments (API image, Firestore seed). Run from services/api:
  uv run python ../../scenarios/demo_world/build_inbox.py            # write the files
  uv run python ../../scenarios/demo_world/build_inbox.py --check    # exit 1 if the committed files are stale
captures/inbox-triage.json (WS2 `python -m kirchhoff.inbox.precompute`, golden-capture time) is folded in if present."""
import argparse
import sys
from pathlib import Path

from kirchhoff.enterprise.world.config import load_world_config
from kirchhoff.enterprise.world.inbox import (TRIAGE_CAPTURE, build_inbox, inbox_diff_on_disk, load_triage_capture,
                                              write_inbox)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build the Kirchhoff bids inbox")
    ap.add_argument("--check", action="store_true", help="fail if the files on disk differ from a fresh build")
    args = ap.parse_args(argv)
    cfg = load_world_config(HERE / "world.yaml")
    triage = load_triage_capture(ROOT / TRIAGE_CAPTURE)
    build = build_inbox(cfg, ROOT / "scenarios", triage)
    if build_inbox(cfg, ROOT / "scenarios", triage).digest() != build.digest():
        print("build_inbox: two builds differ; the generator is not deterministic", file=sys.stderr)
        return 1
    if args.check:
        stale = inbox_diff_on_disk(build, ROOT)
        if stale:
            print("stale inbox files: " + ", ".join(stale), file=sys.stderr)
            return 1
        print(f"inbox up to date ({build.digest()[:16]})")
        return 0
    written = write_inbox(build, ROOT)
    print(f"inbox {build.digest()[:16]}: {len(build.seed.emails)} emails, {len(written)} files; "
          f"triaged {sorted(triage)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

`Makefile`: replace the `demo-world` recipe with
```make
demo-world:
	cd services/api && uv run python ../../scenarios/demo_world/build.py && uv run python ../../scenarios/demo_world/build_inbox.py
```

- [ ] **Step 8 [cut-safe]: Run tests**

Run: `cd services/api && uv run pytest tests/enterprise -q`
Expected: all pass. `test_world_inbox.py` reports `7 passed`, and the three appended tests pass. `test_clients_match_the_ws2_enterprise_protocol` skips in `ws4-infra` until WS2's `kirchhoff/agents/ports.py` is merged; on `build` it passes.

- [ ] **Step 9 [cut-safe]: Generate the files and inspect them**

Run:
```bash
make demo-world
cd services/api && uv run python ../../scenarios/demo_world/build_inbox.py --check && uv run python -m kirchhoff.enterprise.seed_cli --dry-run && cd ../.. && \
  find apps/web/public/demo/inbox scenarios/demo_world/out/inbox -type f | sort && \
  grep -c '"stage": "Qualification"' scenarios/demo_world/out/enterprise_seed.json
```
Expected:
- `inbox <16 hex>: 6 emails, 12 files; triaged []`, then `inbox up to date (<16 hex>)`.
- A dry-run report with `"materials": 60`, `"opportunities": 9`, `"inbox_emails": 6`.
- Five PDFs in each of the two inbox folders (`hall-b-addendum-1`, `konkan-rfi-response`, `narmada-400kv-spec`, `tapti-brochure`, `vindhya-boq-scan`).
- `2` for the grep.

Open `apps/web/public/demo/inbox/vindhya-boq-scan.pdf`: it must look like a slightly rotated, speckled scan with the BOQ lines and both labels. Run `make demo-world` twice; `git status --short` must show no change the second time.

- [ ] **Step 10 [cut-safe]: Commit**

```bash
git add scenarios/demo_world/world.yaml scenarios/demo_world/build_inbox.py scenarios/demo_world/out \
  apps/web/public/demo/inbox.json apps/web/public/demo/inbox Makefile \
  services/api/kirchhoff/enterprise/world/config.py services/api/kirchhoff/enterprise/world/inbox.py \
  services/api/kirchhoff/enterprise/sandbox.py services/api/kirchhoff/enterprise/app.py \
  services/api/kirchhoff/enterprise/client.py services/api/kirchhoff/enterprise/seed_cli.py \
  services/api/tests/enterprise/test_world_inbox.py services/api/tests/enterprise/test_enterprise_sandbox.py \
  services/api/tests/enterprise/test_enterprise_http.py services/api/tests/enterprise/test_enterprise_seed_cli.py
git add -u -- apps/web/public/demo   # only if P4 Task 11 has landed: world.json/integrations.json regenerated by make demo-world
git commit -m "feat(demo-world): bids inbox mailbox, rendered attachments, appetite rules; visitor-created opportunities

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 11 [cut-safe] (controller-run after merge, live Firestore): Reload the sandbox seed**

Run: `make seed-enterprise`
Expected: the report shows `"written": {"materials": 60, …, "opportunities": 9}` and `"inbox_written": 6`. Then `seed/inbox` and `seed/inbox/emails/*` exist in Firestore, and `opp-hall-c` and `opp-vindhya-cpp` still read "Qualification" (unchanged). Redeploy kirchhoff-enterprise with the next normal `infra/deploy_api.sh` run (`create_opportunity` is new code). Until then, Pursue on an email that proposes a new opportunity answers 502 `enterprise_unavailable`, and Hall B's Pursue is unaffected.

- [ ] **Step 12: Tell WS2, WS3 and the controller**

"I-1 landed:
- `apps/web/public/demo/inbox.json` (shape `InboxSeed`, emails newest first, `triage: null` until the I-2 capture) and the rendered attachments under `/demo/inbox/` are committed. The Hall B tender and drawing are linked at `/demo/docs/tender-hall-a.pdf` and `/demo/docs/hall-a-plan.pdf` (WS3's sync script).
- The API copy is `scenarios/demo_world/out/inbox_seed.json` plus `out/inbox/*.pdf`. Firestore has `seed/inbox` (meta) and `seed/inbox/emails/{id}`.
- CRM: the stage is still 'Qualification' (unchanged, ruling B1). `create_opportunity(uid, opportunity)` exists on both enterprise clients and on kirchhoff-enterprise (`POST /crm/opportunities`).
- For P4 Task 12's web deploy gate, add `uv run python ../../scenarios/demo_world/build_inbox.py --check` next to `build.py --check`."

---

### Task I-2 (WS2): Inbox agent, deterministic fit check, endpoints and the precompute script

Spec §20, §6.3 and §11. `kirchhoff/inbox/` turns one seeded email into a `TriageResult`.
- **Agent:** the Inbox agent (`gemini-3.8-flash`, thinking `low`) classifies each attachment, links the email to a CRM opportunity or proposes one, and extracts client, site, asset type, MW, redundancy, bid due date and lead-time limit, each with a verbatim quote.
- **Verification:** code checks every quote with the existing pdfplumber `verify_quote` (PDF pages with text) or as a normalized substring of the email body. Pages without a text layer are marked `unverified_scan`. Unverified numbers are withheld, and the summary passes `trust.sanitize`.
- **Fit check:** `fit.py` (no LLM) applies the appetite rules and the day-zero supply check. The supply check sizes the transformer for the extracted MW and redundancy with the engine (`place_racks`, `power_options`), checks its ERP lead time against the extracted limit, and calls the engine's own `r15_swap` when it misses.
- **Endpoints:** three endpoints expose this (live triage only on Hall B).
- **Precompute:** a script freezes the real agent's triage of every seeded email for the static bundle at golden-capture time.

Steps 1–9 and 15 are **[cut-safe]** (pipeline and precompute). Steps 10–14 are **[cut]** (endpoints).

**Branch:** `jd/inbox-i2`, cut from `build`, after I-1 and P2 Tasks 9 and 12 have landed on `build` (see Prerequisites above). Rebase on `build` again immediately before opening the PR, since this task edits files P2 Tasks 9–12 are actively changing.

**Conflicts with in-flight work:** P2 Tasks 9–12 are live on `kirchhoff/agents/**`, `kirchhoff/runs/**`, `kirchhoff/api/**` and `kirchhoff/intake/**` right now, and this task must touch three of those four:
- `kirchhoff/agents/specs.py`: inserting `INBOX = AgentSpec(...)` above `SPECS_BY_AGENT` is a pure textual append — low risk.
- `kirchhoff/agents/ports.py`: the contracts-import change and the new `STAGE_QUALIFYING` constant are additive, but adding `list_opportunities`/`create_opportunity` to the body of the existing `class EnterpriseClient(Protocol)` edits a class P2 Tasks 9–12 may also be extending. **Coordinate with Mehul before merging this file's hunk** — rebase on `build` immediately before the PR and re-run `make check-types` to catch a silent clobber.
- `kirchhoff/runs/fakes.py`: `FAKE_OPPORTUNITIES` and `INBOX_REPLIES` are additive blocks, but replacing `FakeEnterprise.__init__`'s first fields and replacing `reset_visitor` with three methods both rewrite lines inside a class P2 Tasks 9–12 are also changing (it is their primary fakes file). This cannot be made purely append-only without duplicating `FakeEnterprise`. **Coordinate with Mehul before merging this file's hunk.**
- `kirchhoff/api/app.py`: adding one `app.include_router(inbox_routes.make_router(...))` line (Step 12, `[cut]`) touches a file P2 Tasks 9–12 own. Low-risk single-line insert next to the existing `include_router` calls, but still **coordinate with Mehul before merging** if P2's own router wiring is mid-edit when this PR is ready.
- `services/api/tests/api/conftest.py`: the two new fixtures are appended at file end — low risk.

**Files:**
- Create: `services/api/kirchhoff/inbox/__init__.py`, `services/api/kirchhoff/inbox/models.py`, `services/api/kirchhoff/inbox/fit.py`, `services/api/kirchhoff/inbox/triage.py`, `services/api/kirchhoff/inbox/precompute.py`, `services/api/kirchhoff/inbox/store.py`, `services/api/kirchhoff/api/inbox_routes.py`
- Modify: `services/api/kirchhoff/agents/specs.py` (`INBOX`), `services/api/kirchhoff/agents/ports.py` (protocol + `STAGE_QUALIFYING`), `services/api/kirchhoff/runs/fakes.py` (`FAKE_OPPORTUNITIES`, `FakeEnterprise` CRM, `INBOX_REPLIES`), `services/api/kirchhoff/api/app.py` (include the router), `services/api/tests/api/conftest.py` (append two fixtures)
- Test: `services/api/tests/inbox/conftest.py`, `services/api/tests/inbox/test_inbox_fit.py`, `services/api/tests/inbox/test_inbox_triage.py`, `services/api/tests/inbox/test_inbox_precompute.py`, `services/api/tests/api/test_api_inbox.py` (no `__init__.py` in `tests/inbox/`, like `tests/runs/`)
- Generated at golden capture (committed by WS4): `scenarios/demo_world/captures/inbox-triage.json`

**Interfaces:**
- Consumes:
  - P2 Task 3: `PdfText(path)` (`.page_text(page)`, `.page_count`, `.close()`), `verify_quote(pdf, page, quote, value) -> QuoteCheck(ok, reason, bbox)` and `value_in_quote(value, quote)` from `kirchhoff.intake.verify`; `normalize` from `kirchhoff.intake.textnorm`.
  - P2 Task 4: `sanitize(text, allowed_ids, template)`, `is_clean(text, allowed_ids)`, `fmt_number`, `fmt_value` from `kirchhoff.agents.trust`.
  - P2 Task 5: `AgentSpec`, `Attachment`, `run_json(runner, spec, key, message, schema, tools=(), attachments=()) -> (model, AgentResult)`, `ReplayRunner(replies)` (key `"{spec.name}:{key}"`, `{"raise": …}` raises), `MODEL`, `AdkRunner`, `GenaiRunner`.
  - P2 Task 7: `ErpSnapshot`, `EnterpriseClient`, `FakeEnterprise`, `FAKE_REPLIES`, `FAKE_MATERIALS`.
  - P2 Task 8: `Deps` (`store`, `runner`, `enterprise`, `scenarios_dir`, `clock`, `erp()`), `build_fake_deps`, `CheckedStore`.
  - P2 Task 9: `canonical_topology(s) -> "2N" | "DR" | "BLOCK" | None` from `kirchhoff.intake.brief`.
  - P2 Task 12: `create_app(store=None, verify_token=None, deps=None)`, `err(status, detail, **extra)`, `kirchhoff.api.deps.scenarios_dir()`, `tests/api/conftest.py` fixtures `deps`, `client`, `auth`, `firestore_safe`, and `POST /api/workspace/reset` (deletes `workspaces/{uid}`, calls `enterprise.reset_visitor`).
  - Engine (WS1, frozen): `kirchhoff.engine.api.load_scenario`, `place_racks`, `power_options`, `default_erp`, `warm_up`; `kirchhoff.engine.options.r15_swap(scn, model, material_id, erp) -> (model, swap) | None`; `kirchhoff.engine.scenario.with_limit(scn, key, value)`; `kirchhoff.engine.erp.effective_lead_weeks(material, qty)` (ruling B7).
  - I-1: `kirchhoff.enterprise.world.inbox` (`Appetite`, `InboxEmail`, `InboxSeed`, `load_inbox_seed`, `load_inbox`, `build_inbox`, `SEED_DOC`, `SEED_EMAILS`, `CAPTURE_VERSION`); `kirchhoff.enterprise.world.config.load_world_config`; `make_enterprise_client()` with `list_opportunities(uid)` and `create_opportunity(uid, opportunity)`; the committed `scenarios/demo_world/out/inbox_seed.json` and `out/inbox/*.pdf`.
- Produces:
  - `kirchhoff.inbox.models`:
    - Agent output: `InboxExtraction(is_bid, summary, attachments: [RawAttachment(attachment_id, kind)], fields: [RawField(key, value, unit, source, page, verbatim_quote)], crm: RawCrm(account, opportunity_id, propose_new))`.
    - Code-built: `AttachmentTriage(attachment_id, name, kind, scanned)`; `ExtractedField(key, label, value, unit, display, source, source_label, page, quote, verification: "verified"|"unverified_scan"|"unverified", bbox: list[float] | None)`; `CrmLink(account, opportunity_id, opportunity_name, stage, proposed, proposed_name)`; `FitReason(rule: "asset_pack"|"mw_range"|"region"|"deadline"|"supply"|"not_a_bid", status: "pass"|"warn"|"fail"|"n/a", text)`; `SupplyCheck(status: "ok"|"swap"|"risk"|"not_assessed", text, topology, mw, lead_limit_weeks, material_id, lead_time_weeks, stock, swap_to, swap_stock)`; `FitResult(verdict: "pursue"|"clarify"|"decline"|None, headline, reasons, supply)`.
    - Results: `TriageResult(email_id, is_bid, summary, attachments, fields, crm, fit, quotes_verified, quotes_total, source: "live"|"precomputed", model, triaged_at, tokens_in, tokens_out)`; `PursueResult(email_id, project_id, project_name: str | None, project_created, opportunity_id, opportunity_name, stage, previous_stage, opportunity_created, open: str | None)`.
    - Constants: `FIELD_ORDER`, `FIELD_LABELS`, `ASSET_LABELS`.
  - `kirchhoff.inbox.fit`: `parse_due(text) -> date | None`, `fmt_date(d) -> str`, `days_to_due(due, as_of) -> int`, `region_of(site, appetite) -> str | None`, `day_zero_supply(mw, redundancy, lead_limit_weeks, erp, scenarios_root=None) -> SupplyCheck`, `supply_for(fields, appetite, erp, supply_fn=day_zero_supply) -> SupplyCheck | None`, `assess_fit(*, is_bid, fields, crm, appetite, as_of, supply) -> FitResult`, `warm_engine()`, `SupplyFn`.
  - `kirchhoff.inbox.triage`: `TRIAGE_PROMPT`, `build_message(email, opportunities) -> str`, `verify_field(raw, email, pdfs, names) -> ExtractedField`, `link_crm(raw, is_bid, email, opportunities) -> CrmLink`, `triage_email(email, *, runner, scenarios_dir, opportunities, erp, appetite, as_of, source, now, supply_fn=day_zero_supply, spec=INBOX) -> TriageResult` (replay key `inbox:triage:{email_id}`).
  - `kirchhoff.inbox.precompute`: `precompute(seed, *, runner, scenarios_dir, opportunities, erp, supply_fn=day_zero_supply) -> {"version": 1, "model", "as_of", "results": {email_id: TriageResult JSON}}` and CLI `python -m kirchhoff.inbox.precompute [--seed] [--out] [--backend adk|genai|replay]` (default out `scenarios/demo_world/captures/inbox-triage.json`).
  - `kirchhoff.inbox.store`: `overlay_path(uid, email_id)`, `project_path(uid, pid)`, `load_seed(store, scenarios_dir) -> InboxSeed` (Firestore `seed/inbox` first, else the file), `overlays(store, uid)`, `inbox_view(seed, overlays) -> dict`.
  - `kirchhoff.agents.specs.INBOX = AgentSpec("inbox", thinking="low", timeout_s=8.0, …)`. `kirchhoff.agents.ports.STAGE_QUALIFYING = "Qualification"`, and `EnterpriseClient.list_opportunities(uid)` / `create_opportunity(uid, opportunity)`.
  - `kirchhoff.runs.fakes`: `FAKE_OPPORTUNITIES`, `FakeEnterprise(materials=None, opportunities=None)` with `list_opportunities`, `create_opportunity`, `.created`, and `INBOX_REPLIES` (merged into `FAKE_REPLIES` under `inbox:triage:{email_id}` for all six emails).
  - Routes (`kirchhoff.api.inbox_routes.make_router(deps, current_uid)`, module attributes `TRIAGE_TIMEOUT_S = 9.5`, `TRIAGES_PER_HOUR = 10`, `SUPPLY_FN`):
    - `GET /api/inbox` → `InboxSnapshot`. Each email gains `status` and `pursue`. 503 `inbox_unavailable`.
    - `POST /api/inbox/{email_id}/triage` → `TriageResult` for the Hall B email only. Errors: 404 `email_not_found`, 409 `precomputed`, 429 `triage_rate_limit`, 502 `triage_failed`, 504 `timeout`.
    - `POST /api/inbox/{email_id}/pursue` → `PursueResult`. Idempotent. Errors: 404, 409 `not_triaged` / `cannot_pursue`, 502 `enterprise_unavailable`.

- [ ] **Step 1 [cut-safe]: Write the failing pipeline tests**

`services/api/tests/inbox/conftest.py`:
```python
from pathlib import Path

import pytest

from kirchhoff.enterprise.world.inbox import InboxSeed, load_inbox_seed

REPO = Path(__file__).resolve().parents[4]
SCENARIOS = REPO / "scenarios"
AS_OF = 1792132200.0  # world anchor: 2026-10-16 12:00 IST


@pytest.fixture(scope="session")
def scenarios() -> Path:
    return SCENARIOS


@pytest.fixture(scope="session")
def inbox_seed() -> InboxSeed:
    """I-1's committed seed (scenarios/demo_world/out/inbox_seed.json) with its rendered attachments."""
    return load_inbox_seed(SCENARIOS / "demo_world" / "out" / "inbox_seed.json")


@pytest.fixture(scope="session")
def erp():
    from kirchhoff.engine.api import default_erp
    return default_erp()  # the Hall A ERP: TX-2500 0 in stock / 98 weeks, TX-3150 6 in stock
```

`services/api/tests/inbox/test_inbox_fit.py`:
```python
from datetime import date

from kirchhoff.inbox.fit import assess_fit, day_zero_supply, days_to_due, parse_due, region_of, supply_for
from kirchhoff.inbox.models import CrmLink, ExtractedField

AS_OF = 1792132200.0  # 2026-10-16 12:00 IST
SWAP = ("26-week limit; the 2.5 MVA unit TX-2500 is 98 weeks with none in stock; "
        "expect an in-stock swap to TX-3150 (3.15 MVA, 6 in stock).")


def F(key, value, display=None, verification="verified", source_label="Email body"):
    return ExtractedField(key=key, label=key, value=value, display=display or str(value), source="body",
                          source_label=source_label, verification=verification)


HALL_B = {"client": F("client", "Deccan Compute"), "site": F("site", "AI campus near Hyderabad, Telangana"),
          "asset_type": F("asset_type", "datahall", "AI data hall"), "mw": F("mw", 6.336, "6.34 MW"),
          "redundancy": F("redundancy", "2N"), "bid_due": F("bid_due", "13 November 2026", "13 Nov 2026"),
          "lead_time_weeks": F("lead_time_weeks", 26.0, "26 weeks")}


def _fit(fields, appetite, supply=None, is_bid=True, crm=None):
    return assess_fit(is_bid=is_bid, fields=fields, crm=crm or CrmLink(), appetite=appetite, as_of=AS_OF,
                      supply=supply)


def test_dates_are_counted_from_the_world_anchor():
    assert parse_due("13 November 2026") == parse_due("13th Nov 2026") == parse_due("2026-11-13") == date(2026, 11, 13)
    assert parse_due("next month") is None and parse_due(None) is None
    assert days_to_due(date(2026, 11, 13), AS_OF) == 28


def test_region_of(inbox_seed):
    a = inbox_seed.appetite
    assert region_of("AI campus near Hyderabad, Telangana", a) == "Telangana"
    assert region_of("Satna mill, Madhya Pradesh", a) == "Madhya Pradesh"
    assert region_of("Bharuch, Gujarat", a) is None


def test_supply_uses_the_engine_internals_it_names():
    """Ruling B7: these engine internals are not on the facade; a rename in WS1 must fail here first."""
    from kirchhoff.engine import erp, options, scenario
    assert callable(options.r15_swap) and callable(scenario.with_limit) and callable(erp.effective_lead_weeks)


def test_day_zero_supply_for_hall_b_expects_the_in_stock_swap(erp):
    s = day_zero_supply(6.336, "2N", 26.0, erp)
    assert (s.status, s.topology, s.material_id, s.lead_time_weeks, s.stock, s.swap_to, s.swap_stock) == \
        ("swap", "2N", "TX-2500", 98, 0, "TX-3150", 6)
    assert s.text == SWAP
    assert day_zero_supply(6.336, "distributed redundant", 26.0, erp).topology == "DR"


def test_day_zero_supply_other_outcomes(erp):
    ok = day_zero_supply(6.336, "2N", 100.0, erp)
    assert ok.status == "ok" and ok.text == "100-week limit; the 2.5 MVA unit TX-2500 ships in time (98 weeks to order)."
    assumed = day_zero_supply(6.336, None, 26.0, erp)
    assert assumed.status == "swap" and assumed.text.startswith("Redundancy not stated; assumed 2N. 26-week limit;")
    big = day_zero_supply(30.0, "2N", 26.0, erp)
    assert big.status == "not_assessed" and "No catalogue transformer passes R01 for 30 MW in 2N" in big.text
    assert day_zero_supply(None, "2N", 26.0, erp).status == "not_assessed"
    assert day_zero_supply(6.336, "2N", None, erp).status == "not_assessed"


def test_hall_b_is_pursue_with_the_supply_line(inbox_seed, erp):
    supply = supply_for(HALL_B, inbox_seed.appetite, erp)
    fit = _fit(HALL_B, inbox_seed.appetite, supply)
    assert fit.verdict == "pursue"
    assert fit.headline == "Pursue: inside our appetite; plan the transformer swap the lead-time limit needs."
    assert [(r.rule, r.status) for r in fit.reasons] == [("asset_pack", "pass"), ("mw_range", "pass"),
                                                         ("region", "pass"), ("deadline", "pass"), ("supply", "pass")]
    assert [r.text for r in fit.reasons] == [
        "AI data hall is one of our asset packs.", "6.34 MW is inside our 2–120 MW range.",
        "AI campus near Hyderabad, Telangana is in Telangana, one of our regions.",
        "Bid due 13 Nov 2026: 28 days from 16 Oct 2026 (minimum 10).", SWAP]


def test_a_scanned_load_means_clarify(inbox_seed, erp):
    fields = {"site": F("site", "Satna mill, Madhya Pradesh"), "asset_type": F("asset_type", "grid", "Grid"),
              "mw": F("mw", None, "Not verified (scan)", "unverified_scan", "Switchyard BOQ (scan).pdf · p.1"),
              "bid_due": F("bid_due", "30 October 2026", "30 Oct 2026")}
    supply = supply_for(fields, inbox_seed.appetite, erp)
    assert supply.status == "not_assessed" and supply.text == "The day-zero supply check covers AI data halls only."
    fit = _fit(fields, inbox_seed.appetite, supply)
    assert fit.verdict == "clarify" and fit.headline == "Clarify before bidding: load (MW)."
    mw = next(r for r in fit.reasons if r.rule == "mw_range")
    assert mw.status == "warn" and "scanned page (Switchyard BOQ (scan).pdf · p.1)" in mw.text
    assert next(r for r in fit.reasons if r.rule == "supply").status == "n/a"


def test_outside_the_appetite_declines(inbox_seed):
    fields = {"site": F("site", "Bharuch, Gujarat"), "asset_type": F("asset_type", "substation", "Substation"),
              "bid_due": F("bid_due", "20 November 2026", "20 Nov 2026")}
    fit = _fit(fields, inbox_seed.appetite)
    assert fit.verdict == "decline" and fit.headline == "Decline: outside our appetite on asset type, region."
    assert fit.reasons[0].text == "Substation is not one of our asset packs (AI data hall, Grid, Solar)."


def test_deadline_rules(inbox_seed):
    def deadline(value):
        fields = {**HALL_B, "bid_due": F("bid_due", value)} if value else {k: v for k, v in HALL_B.items()
                                                                           if k != "bid_due"}
        return next(r for r in _fit(fields, inbox_seed.appetite).reasons if r.rule == "deadline")

    short = deadline("20 October 2026")
    assert short.status == "fail" and short.text == "Bid due 20 Oct 2026: 4 days from 16 Oct 2026, under our 10-day minimum."
    assert deadline("1 October 2026").status == "fail"
    assert deadline(None).status == "warn"


def test_not_a_bid_says_where_it_was_filed(inbox_seed):
    crm = CrmLink(account="Konkan Cloud", opportunity_id="opp-pune-edge-1", opportunity_name="Pune Edge Phase 1")
    fit = _fit({}, inbox_seed.appetite, is_bid=False, crm=crm)
    assert fit.verdict is None and fit.headline == "Not a bid: no fit check."
    assert [(r.rule, r.status, r.text) for r in fit.reasons] == [
        ("not_a_bid", "n/a", "Not a bid; filed to Konkan Cloud · Pune Edge Phase 1 in the CRM.")]
```

`services/api/tests/inbox/test_inbox_triage.py`:
```python
import copy

from kirchhoff.agents.runner import ReplayRunner
from kirchhoff.inbox.triage import build_message, triage_email
from kirchhoff.runs.fakes import FAKE_OPPORTUNITIES, FAKE_REPLIES


def _triage(seed, scenarios, erp, email_id, replies=None):
    email = next(e for e in seed.emails if e.id == email_id)
    return triage_email(email, runner=ReplayRunner(replies or FAKE_REPLIES), scenarios_dir=scenarios,
                        opportunities=FAKE_OPPORTUNITIES, erp=erp, appetite=seed.appetite, as_of=seed.as_of,
                        source="live", now=seed.as_of + 60)


def _by_key(result):
    return {f.key: f for f in result.fields}


def test_the_message_lists_attachments_and_the_crm(inbox_seed):
    msg = build_message(inbox_seed.emails[0], FAKE_OPPORTUNITIES)
    assert "1. att-hall-b-tender: DC-HA-TS-001 Rev 0 technical requirements.pdf" in msg
    assert "opp-hall-b | Deccan Compute | Hall B design-build | Design in progress" in msg
    assert "Bids are due by 13 November 2026." in msg


def test_hall_b_verifies_every_quote_and_pursues(inbox_seed, scenarios, erp):
    r = _triage(inbox_seed, scenarios, erp, "em-hall-b")
    assert (r.is_bid, r.quotes_verified, r.quotes_total, r.source, r.tokens_in) == (True, 7, 7, "live", 14200)
    assert [(a.attachment_id, a.kind, a.scanned) for a in r.attachments] == [
        ("att-hall-b-tender", "tender", False), ("att-hall-b-drawing", "drawing", False),
        ("att-hall-b-addendum", "addendum", False)]
    f = _by_key(r)
    assert [k for k in f] == ["client", "site", "asset_type", "mw", "redundancy", "bid_due", "lead_time_weeks"]
    assert (f["mw"].value, f["mw"].display, f["mw"].source_label) == (6.336, "6.34 MW", "Addendum 1, Hall B.pdf · p.1")
    assert len(f["mw"].bbox) == 4 and f["mw"].quote == "Hall B IT load: 6.336 MW"
    assert f["redundancy"].source_label == "DC-HA-TS-001 Rev 0 technical requirements.pdf · p.4"
    assert (f["asset_type"].display, f["bid_due"].display, f["lead_time_weeks"].display) == \
        ("AI data hall", "13 Nov 2026", "26 weeks")
    assert (r.crm.opportunity_id, r.crm.stage, r.crm.proposed) == ("opp-hall-b", "Design in progress", False)
    assert r.fit.verdict == "pursue" and r.fit.supply.swap_to == "TX-3150"
    assert r.summary == "Deccan Compute invites a design-build bid for Data Hall B, a twin of Hall A with 2N power."


def test_a_scanned_page_is_marked_and_its_number_withheld(inbox_seed, scenarios, erp):
    r = _triage(inbox_seed, scenarios, erp, "em-vindhya-boq")
    assert [(a.kind, a.scanned) for a in r.attachments] == [("boq", True)]
    mw = _by_key(r)["mw"]
    assert (mw.verification, mw.value, mw.display, mw.quote) == ("unverified_scan", None, "Not verified (scan)", "")
    assert (r.quotes_verified, r.quotes_total) == (4, 5)
    assert r.fit.verdict == "clarify" and r.crm.opportunity_id == "opp-vindhya-cpp"


def test_other_emails(inbox_seed, scenarios, erp):
    brochure = _triage(inbox_seed, scenarios, erp, "em-tapti-brochure")
    assert (brochure.is_bid, brochure.fit.verdict, brochure.crm.account, brochure.crm.proposed) == (False, None, None, False)
    assert brochure.fit.reasons[0].text == "Not a bid; no CRM record to update."
    konkan = _triage(inbox_seed, scenarios, erp, "em-konkan-rfi")
    assert _by_key(konkan)["client"].verification == "verified"  # quoted from the RFI response PDF
    assert konkan.fit.reasons[0].text == "Not a bid; filed to Konkan Cloud · Pune Edge Phase 1 in the CRM."
    solar = _triage(inbox_seed, scenarios, erp, "em-suryodaya-solar")
    assert (solar.crm.proposed, solar.crm.account, solar.crm.proposed_name) == \
        (True, "Suryodaya Renewables", "Enquiry: solar EPC near Anantapur")
    assert solar.fit.headline == "Clarify before bidding: bid deadline." and _by_key(solar)["mw"].display == "20 MWp"
    narmada = _triage(inbox_seed, scenarios, erp, "em-narmada-400kv")
    assert narmada.fit.verdict == "decline" and narmada.crm.proposed is True


def test_untrusted_agent_output_is_contained(inbox_seed, scenarios, erp):
    reply = copy.deepcopy(FAKE_REPLIES["inbox:triage:em-hall-b"])
    reply["text"]["summary"] = "Hall B needs 6 transformers of 2.5 MVA."
    mw = next(f for f in reply["text"]["fields"] if f["key"] == "mw")
    mw.update(value=7, verbatim_quote="Hall B IT load: 7 MW")
    reply["text"]["crm"]["opportunity_id"] = "opp-made-up"
    r = _triage(inbox_seed, scenarios, erp, "em-hall-b", {"inbox:triage:em-hall-b": reply})
    assert r.summary == "Bid from Deccan Compute."  # digits outside the allowlist: template (spec §6.3)
    f = _by_key(r)["mw"]
    assert (f.verification, f.value, f.display) == ("unverified", None, "Not verified")
    assert (r.crm.opportunity_id, r.crm.account) == (None, "Deccan Compute")
    assert r.fit.verdict == "clarify" and r.fit.supply.status == "not_assessed"
```

`services/api/tests/inbox/test_inbox_precompute.py`:
```python
import json

from kirchhoff.agents.runner import ReplayRunner
from kirchhoff.enterprise.world.config import load_world_config
from kirchhoff.enterprise.world.inbox import build_inbox
from kirchhoff.inbox.precompute import main, precompute
from kirchhoff.runs.fakes import FAKE_OPPORTUNITIES, FAKE_REPLIES

VERDICTS = {"em-hall-b": "pursue", "em-konkan-rfi": None, "em-narmada-400kv": "decline",
            "em-suryodaya-solar": "clarify", "em-tapti-brochure": None, "em-vindhya-boq": "clarify"}


def _capture(seed, scenarios, erp):
    return precompute(seed, runner=ReplayRunner(FAKE_REPLIES), scenarios_dir=scenarios,
                      opportunities=FAKE_OPPORTUNITIES, erp=erp)


def test_precompute_covers_every_seeded_email_deterministically(inbox_seed, scenarios, erp):
    capture = _capture(inbox_seed, scenarios, erp)
    assert capture["version"] == 1 and capture["model"] == "gemini-3.8-flash" and capture["as_of"] == inbox_seed.as_of
    assert {k: v["fit"]["verdict"] for k, v in capture["results"].items()} == VERDICTS
    assert all(v["source"] == "precomputed" and v["triaged_at"] == inbox_seed.as_of
               for v in capture["results"].values())
    assert _capture(inbox_seed, scenarios, erp) == capture


def test_the_capture_folds_into_the_ws4_inbox_build(inbox_seed, scenarios, erp):
    capture = _capture(inbox_seed, scenarios, erp)
    build = build_inbox(load_world_config(scenarios / "demo_world" / "world.yaml"), scenarios, capture["results"])
    assert {e.id: e.triage["fit"]["verdict"] for e in build.seed.emails} == VERDICTS


def test_cli_with_the_replay_backend_writes_the_capture(tmp_path, capsys):
    out = tmp_path / "inbox-triage.json"
    assert main(["--backend", "replay", "--out", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert sorted(data["results"]) == sorted(VERDICTS)
    assert "em-hall-b: pursue (7/7 quotes verified)" in capsys.readouterr().out
```

- [ ] **Step 2 [cut-safe]: Run to verify failure**

Run: `cd services/api && uv run pytest tests/inbox -q`
Expected: collection errors with `ModuleNotFoundError: No module named 'kirchhoff.inbox'`.

- [ ] **Step 3 [cut-safe]: The triage models**

`services/api/kirchhoff/inbox/__init__.py`:
```python
"""Bids inbox (spec §20): Inbox agent triage, deterministic fit rules and the day-zero supply check."""
```

`services/api/kirchhoff/inbox/models.py`:
```python
"""Shapes of the bids inbox triage (spec §20). InboxExtraction is the agent's untrusted output; everything else is
built by code from verified quotes, ERP records and engine results (spec §6.3, P2 ruling R14)."""
from typing import Literal

from pydantic import BaseModel, ConfigDict

AttachmentKind = Literal["tender", "drawing", "addendum", "boq", "brochure", "other"]
AssetType = Literal["datahall", "grid", "solar", "substation", "other"]
FieldKey = Literal["client", "site", "asset_type", "mw", "redundancy", "bid_due", "lead_time_weeks"]
Verification = Literal["verified", "unverified_scan", "unverified"]
Verdict = Literal["pursue", "clarify", "decline"]
ReasonStatus = Literal["pass", "warn", "fail", "n/a"]  # the FindingStatus vocabulary, rendered with icon + text
FIELD_ORDER: tuple[FieldKey, ...] = ("client", "site", "asset_type", "mw", "redundancy", "bid_due", "lead_time_weeks")
FIELD_LABELS: dict[str, str] = {"client": "Client", "site": "Site", "asset_type": "Asset type", "mw": "Load",
                                "redundancy": "Redundancy", "bid_due": "Bid due", "lead_time_weeks": "Lead-time limit"}
ASSET_LABELS: dict[str, str] = {"datahall": "AI data hall", "grid": "Grid", "solar": "Solar",
                                "substation": "Substation", "other": "Other"}


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---- agent output (untrusted until verified) -------------------------------------------------------------------
class RawAttachment(BaseModel):
    attachment_id: str
    kind: AttachmentKind = "other"


class RawField(BaseModel):
    key: FieldKey
    value: float | str | None = None
    unit: str | None = None
    source: str = "body"  # "body" or an attachment id
    page: int | None = None  # 1-based PDF page when source is an attachment
    verbatim_quote: str = ""


class RawCrm(BaseModel):
    account: str | None = None
    opportunity_id: str | None = None
    propose_new: bool = False


class InboxExtraction(BaseModel):
    is_bid: bool
    summary: str = ""
    attachments: list[RawAttachment] = []
    fields: list[RawField] = []
    crm: RawCrm = RawCrm()


# ---- triage result (code-built) ---------------------------------------------------------------------------------
class AttachmentTriage(_M):
    attachment_id: str
    name: str
    kind: AttachmentKind
    scanned: bool  # no page has a text layer: nothing on it can be verified


class ExtractedField(_M):
    key: FieldKey
    label: str
    value: float | str | None  # None when withheld (unverified and not digit-free text)
    unit: str | None = None
    display: str  # code-formatted from the verified value
    source: str  # "body" or an attachment id
    source_label: str  # "Email body" or "{attachment name} · p.{page}"
    page: int | None = None
    quote: str = ""  # the verified verbatim quote (normalized); "" when unverified
    verification: Verification
    bbox: list[float] | None = None


class CrmLink(_M):
    account: str | None = None
    opportunity_id: str | None = None  # an existing opportunity, checked against the CRM list
    opportunity_name: str | None = None
    stage: str | None = None
    proposed: bool = False  # no existing opportunity matches: Pursue creates one
    proposed_name: str | None = None


class FitReason(_M):
    rule: Literal["asset_pack", "mw_range", "region", "deadline", "supply", "not_a_bid"]
    status: ReasonStatus
    text: str


class SupplyCheck(_M):
    status: Literal["ok", "swap", "risk", "not_assessed"]
    text: str
    topology: str | None = None
    mw: float | None = None
    lead_limit_weeks: float | None = None
    material_id: str | None = None
    lead_time_weeks: int | None = None
    stock: int | None = None
    swap_to: str | None = None
    swap_stock: int | None = None


class FitResult(_M):
    verdict: Verdict | None  # None: not a bid
    headline: str
    reasons: list[FitReason]
    supply: SupplyCheck | None = None


class TriageResult(_M):
    email_id: str
    is_bid: bool
    summary: str  # LLM text, sanitized
    attachments: list[AttachmentTriage]
    fields: list[ExtractedField]
    crm: CrmLink
    fit: FitResult
    quotes_verified: int
    quotes_total: int
    source: Literal["live", "precomputed"]
    model: str
    triaged_at: float
    tokens_in: int = 0
    tokens_out: int = 0


class PursueResult(_M):
    email_id: str
    project_id: str
    project_name: str | None  # None for an existing world project: the UI names it from world.json
    project_created: bool
    opportunity_id: str
    opportunity_name: str
    stage: str
    previous_stage: str | None
    opportunity_created: bool
    open: str | None  # the app route to open next (Hall B's intake), or None
```

- [ ] **Step 4 [cut-safe] (coordinate with Mehul before merging: `kirchhoff/agents/ports.py` and `kirchhoff/runs/fakes.py` are live P2 Task 9–12 files): The agent spec, the CRM port and the fakes**

`services/api/kirchhoff/agents/specs.py`: insert directly above `SPECS_BY_AGENT = {` (the Inbox agent is not a run-lane agent, so it stays out of `SPECS_BY_AGENT`):
```python
INBOX = AgentSpec("inbox", thinking="low", timeout_s=8.0, instruction=(
    "You are the Inbox agent of Kirchhoff. You triage the bids@ mailbox of an EPC contractor: you classify each "
    "attachment, link the email to the CRM and extract bid fields with exact verbatim quotes. Code checks every "
    "quote against the documents, so copy text exactly and never guess. Reply with JSON only."))

```

`services/api/kirchhoff/agents/ports.py`:
- Change the contracts import to `from kirchhoff.contracts import CrmOverlay, Material, Opportunity, PRLine, PurchaseRequisition`.
- After `STAGE_DESIGN_APPROVED = "Design approved"`, add `STAGE_QUALIFYING = "Qualification"  # bids inbox Pursue (spec §20)`.
- Add these two methods at the end of `class EnterpriseClient(Protocol)`. I-1 already implements them on both WS4 clients, and WS4's protocol-match test checks every method declared here:
```python
    def list_opportunities(self, uid: str | None) -> list[Opportunity]: ...
    def create_opportunity(self, uid: str, opportunity: Opportunity) -> Opportunity: ...
```

`services/api/kirchhoff/runs/fakes.py`:
- Add `Opportunity` to the `from kirchhoff.contracts import (...)` list.
- Insert directly above `class FakeEnterprise:`:
```python
FAKE_OPPORTUNITIES = [
    Opportunity(id="opp-hall-a", account="Deccan Compute", name="Hall A design-build", stage="Design approved",
                value=18_500_000.0),
    Opportunity(id="opp-hall-b", account="Deccan Compute", name="Hall B design-build", stage="Design in progress",
                value=18_500_000.0),
    Opportunity(id="opp-pune-edge-1", account="Konkan Cloud", name="Pune Edge Phase 1", stage="Closed won",
                value=7_000_000.0),
    Opportunity(id="opp-grid-132kv", account="Narmada Transmission", name="Deccan campus 132 kV intake",
                stage="Negotiation", value=4_800_000.0),
    Opportunity(id="opp-solar-5mwp", account="Suryodaya Renewables", name="Deccan campus 5 MWp solar",
                stage="Proposal", value=3_000_000.0),
    Opportunity(id="opp-vindhya-cpp", account="Vindhya Steel", name="Captive power switchyard", stage="Qualification",
                value=3_700_000.0),
]
```
- Replace the start of `FakeEnterprise` (its `__init__` signature and first fields) with:
```python
class FakeEnterprise:
    def __init__(self, materials: list[Material] | None = None,
                 opportunities: list[Opportunity] | None = None) -> None:
        self.materials = list(materials or FAKE_MATERIALS)
        self.opportunities = list(opportunities or FAKE_OPPORTUNITIES)
        self.created: dict[tuple[str, str], Opportunity] = {}
        self.prs: dict[tuple[str, str], PurchaseRequisition] = {}
        self.keys: dict[str, tuple[str, str]] = {}
        self.stages: dict[tuple[str, str], CrmOverlay] = {}
```
  Keep the remaining `__init__` lines (`self._n = 141`, `self._lock = threading.Lock()`).
- Replace `reset_visitor` with these three methods:
```python
    def list_opportunities(self, uid) -> list[Opportunity]:
        with self._lock:
            mine = [o for (u, _), o in self.created.items() if u == uid]
            stages = {oid: ov.stage for (u, oid), ov in self.stages.items() if u == uid}
        return sorted((o.model_copy(update={"stage": stages[o.id]}) if o.id in stages else o
                       for o in self.opportunities + mine), key=lambda o: o.id)

    def create_opportunity(self, uid, opportunity) -> Opportunity:
        if opportunity.id in {o.id for o in self.opportunities}:
            raise ValueError(f"{opportunity.id} is a seed opportunity")
        with self._lock:
            return self.created.setdefault((uid, opportunity.id), opportunity)

    def reset_visitor(self, uid) -> None:
        with self._lock:
            self.prs = {k: v for k, v in self.prs.items() if k[0] != uid}
            self.keys = {k: v for k, v in self.keys.items() if v[0] != uid}
            self.stages = {k: v for k, v in self.stages.items() if k[0] != uid}
            self.created = {k: v for k, v in self.created.items() if k[0] != uid}
```
- Insert directly above `def build_fake_scenarios(`. These are the recorded Inbox-agent replies; every quote is verbatim from I-1's `world.yaml` bodies and PDFs or from the Hall A tender:
```python
def _q(key, value, source, quote, page=None, unit=None):
    return {"key": key, "value": value, "unit": unit, "source": source, "page": page, "verbatim_quote": quote}


# Bids inbox (addendum I-2): one recorded Inbox-agent reply per seeded email. Quotes are verbatim from I-1's world.yaml
# bodies and rendered PDFs (and the Hall A tender), so verification runs for real in the tests.
INBOX_REPLIES: dict[str, dict] = {
    "inbox:triage:em-hall-b": {"usage": {"in": 14200, "out": 610}, "text": {
        "is_bid": True,
        "summary": "Deccan Compute invites a design-build bid for Data Hall B, a twin of Hall A with 2N power.",
        "attachments": [{"attachment_id": "att-hall-b-tender", "kind": "tender"},
                        {"attachment_id": "att-hall-b-drawing", "kind": "drawing"},
                        {"attachment_id": "att-hall-b-addendum", "kind": "addendum"}],
        "fields": [_q("client", "Deccan Compute", "body", "Deccan Compute invites your bid"),
                   _q("site", "AI campus near Hyderabad, Telangana", "body",
                      "at our AI campus near Hyderabad, Telangana"),
                   _q("asset_type", "datahall", "body", "liquid-cooling design-build of Data Hall B"),
                   _q("mw", 6.336, "att-hall-b-addendum", "Hall B IT load: 6.336 MW", 1, "MW"),
                   _q("redundancy", "2N", "att-hall-b-tender", "The critical power distribution shall be 2N", 4),
                   _q("bid_due", "13 November 2026", "att-hall-b-addendum", "Bids are due by 13 November 2026", 1),
                   _q("lead_time_weeks", 26, "att-hall-b-tender", "no later than 26 weeks from contract award", 2,
                      "weeks")],
        "crm": {"account": "Deccan Compute", "opportunity_id": "opp-hall-b", "propose_new": False}}},
    "inbox:triage:em-tapti-brochure": {"usage": {"in": 2100, "out": 140}, "text": {
        "is_bid": False, "summary": "Vendor marketing from Tapti Transformers about its cast-resin range.",
        "attachments": [{"attachment_id": "att-tapti-brochure", "kind": "brochure"}], "fields": [],
        "crm": {"account": None, "opportunity_id": None, "propose_new": False}}},
    "inbox:triage:em-konkan-rfi": {"usage": {"in": 2300, "out": 180}, "text": {
        "is_bid": False,
        "summary": "Konkan Cloud confirms the CDU gallery door stays as drawn, so the signed Pune Edge design holds.",
        "attachments": [{"attachment_id": "att-konkan-rfi", "kind": "other"}],
        "fields": [_q("client", "Konkan Cloud", "att-konkan-rfi", "Signed for Konkan Cloud", 1)],
        "crm": {"account": "Konkan Cloud", "opportunity_id": "opp-pune-edge-1", "propose_new": False}}},
    "inbox:triage:em-vindhya-boq": {"usage": {"in": 2600, "out": 260}, "text": {
        "is_bid": True,
        "summary": "Vindhya Steel asks for pricing of a captive power switchyard; its BOQ is a scanned image.",
        "attachments": [{"attachment_id": "att-vindhya-boq", "kind": "boq"}],
        "fields": [_q("client", "Vindhya Steel", "body", "Forwarding from Vindhya Steel"),
                   _q("site", "Satna mill, Madhya Pradesh", "body", "at our Satna mill, Madhya Pradesh"),
                   _q("asset_type", "grid", "body", "the 33 kV captive power switchyard"),
                   _q("mw", 40, "att-vindhya-boq", "Plant load: 40 MW", 1, "MW"),
                   _q("bid_due", "30 October 2026", "body", "Bids are due by 30 October 2026")],
        "crm": {"account": "Vindhya Steel", "opportunity_id": "opp-vindhya-cpp", "propose_new": False}}},
    "inbox:triage:em-suryodaya-solar": {"usage": {"in": 900, "out": 200}, "text": {
        "is_bid": True,
        "summary": "Suryodaya Renewables asks whether Meridian will bid for a ground-mount solar EPC.",
        "attachments": [],
        "fields": [_q("client", "Suryodaya Renewables", "body", "Suryodaya Renewables is planning"),
                   _q("site", "near Anantapur, Andhra Pradesh", "body", "plant near Anantapur, Andhra Pradesh"),
                   _q("asset_type", "solar", "body", "ground-mount solar plant"),
                   _q("mw", 20, "body", "a 20 MWp ground-mount solar plant", unit="MWp")],
        "crm": {"account": "Suryodaya Renewables", "opportunity_id": None, "propose_new": True}}},
    "inbox:triage:em-narmada-400kv": {"usage": {"in": 2400, "out": 230}, "text": {
        "is_bid": True,
        "summary": "Narmada Transmission requests EPC quotations for a GIS substation in Gujarat.",
        "attachments": [{"attachment_id": "att-narmada-spec", "kind": "tender"}],
        "fields": [_q("client", "Narmada Transmission", "body", "Narmada Transmission requests EPC quotations"),
                   _q("site", "Bharuch, Gujarat", "body", "substation at Bharuch, Gujarat"),
                   _q("asset_type", "substation", "att-narmada-spec",
                      "EPC of a new 400/220 kV gas-insulated substation", 1),
                   _q("bid_due", "20 November 2026", "body", "Quotations are due by 20 November 2026")],
        "crm": {"account": "Narmada Transmission", "opportunity_id": None, "propose_new": True}}},
}
FAKE_REPLIES.update(INBOX_REPLIES)
```

- [ ] **Step 5 [cut-safe]: The deterministic fit rules and the day-zero supply check**

`services/api/kirchhoff/inbox/fit.py`:
```python
"""Deterministic fit rules and the day-zero supply check (spec §20). No LLM: the inputs are verified fields, the
appetite rules from world.yaml, ERP records and the engine's own functions (addendum ruling B7). Every sentence is a
code-authored template filled from those records (P2 ruling R14)."""
import logging
import re
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from kirchhoff.agents.trust import fmt_number, fmt_value
from kirchhoff.contracts import Material
from kirchhoff.enterprise.world.inbox import Appetite
from kirchhoff.intake.brief import canonical_topology

from .models import ASSET_LABELS, CrmLink, ExtractedField, FitReason, FitResult, ReasonStatus, SupplyCheck

log = logging.getLogger("kirchhoff.inbox")
IST = timezone(timedelta(hours=5, minutes=30))
DATE_FORMATS = ("%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y", "%Y-%m-%d")
RULE_LABELS = {"asset_pack": "asset type", "mw_range": "load (MW)", "region": "region", "deadline": "bid deadline",
               "supply": "day-zero supply"}
SUPPLY_STATUS: dict[str, ReasonStatus] = {"ok": "pass", "swap": "pass", "risk": "warn", "not_assessed": "n/a"}
SupplyFn = Callable[[float | None, str | None, float | None, object], SupplyCheck]


def parse_due(text: str | None) -> date | None:
    """A bid due date as printed ("13 November 2026", "13th Nov 2026", "2026-11-13"), or None."""
    if not text:
        return None
    t = re.sub(r"\b(\d{1,2})(st|nd|rd|th)\b", r"\1", str(text)).replace(",", " ")
    t = " ".join(t.split()).rstrip(".")
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            continue
    return None


def fmt_date(d: date) -> str:
    return f"{d.day} {d.strftime('%b %Y')}"


def days_to_due(due: date, as_of: float) -> int:
    """Whole days from the inbox's as_of (the world anchor, in IST) to the due date; never the wall clock."""
    return (due - datetime.fromtimestamp(as_of, IST).date()).days


def region_of(site: str, appetite: Appetite) -> str | None:
    s = site.casefold()
    return next((r.name for r in appetite.regions if any(p.casefold() in s for p in r.places)), None)


def _mva(m: Material) -> str:
    if m.unit == "kVA" and m.rating:
        return f"{fmt_number(m.rating / 1000.0)} MVA"
    return fmt_value(m.rating, m.unit)


def _stock(m: Material) -> str:
    return "none in stock" if m.stock <= 0 else f"{m.stock} in stock"


def day_zero_supply(mw: float | None, redundancy: str | None, lead_limit_weeks: float | None, erp,
                    scenarios_root: Path | None = None) -> SupplyCheck:
    """R15 before bidding (spec §20): size the transformer the extracted load and redundancy imply with the engine
    (Hall A's reference hall, per-rack load scaled to the load), then check its ERP lead time against the extracted
    limit and, if it misses, let the engine's r15_swap find the swap."""
    if mw is None:
        return SupplyCheck(status="not_assessed", text="No verified load, so the transformer cannot be sized yet.")
    if lead_limit_weeks is None:
        return SupplyCheck(status="not_assessed", mw=mw,
                           text="No verified lead-time clause, so there is no limit to check the ERP against.")
    from kirchhoff.engine.api import load_scenario, place_racks, power_options
    from kirchhoff.engine.erp import effective_lead_weeks
    from kirchhoff.engine.options import r15_swap
    from kirchhoff.engine.scenario import with_limit

    topology = canonical_topology(redundancy) if redundancy else None
    note = "" if topology else "Redundancy not stated; assumed 2N. "
    topology = topology or "2N"
    limit = float(lead_limit_weeks)
    base = load_scenario("hall_a", scenarios_root)
    scn = with_limit(with_limit(base, "rack_kw", mw * 1000.0 / len(place_racks(base))), "max_lead_time_weeks", limit)
    options = {opt.id: model for opt, model in power_options(scn, place_racks(scn))}
    common: dict = {"topology": topology, "mw": mw, "lead_limit_weeks": limit}
    if topology not in options:
        return SupplyCheck(status="not_assessed", **common,
                           text=f"{note}No catalogue transformer passes R01 for {fmt_value(mw, 'MW')} in {topology} "
                                "on the reference hall; size it at intake.")
    model = options[topology]
    txs = [e for e in model.equipment if e.kind == "transformer"]
    m = erp.get(txs[0].catalogue_id)
    common.update(material_id=m.id, lead_time_weeks=m.lead_time_weeks, stock=m.stock)
    head = f"{note}{fmt_number(limit)}-week limit; the {_mva(m)} unit {m.id}"
    if effective_lead_weeks(m, len(txs)) <= limit:
        how = _stock(m) if m.stock >= len(txs) else f"{m.lead_time_weeks} weeks to order"
        return SupplyCheck(status="ok", **common, text=f"{head} ships in time ({how}).")
    found = r15_swap(scn, model, m.id, erp)
    if found is None:
        return SupplyCheck(status="risk", **common,
                           text=f"{head} is {m.lead_time_weeks} weeks with {_stock(m)}, and the ERP has no compliant "
                                "alternative; ask whether the limit can move.")
    to = erp.get(found[1]["to"])
    kind = (f"an in-stock swap to {to.id} ({_mva(to)}, {to.stock} in stock)" if to.stock >= len(txs)
            else f"a swap to {to.id} ({_mva(to)}, {to.lead_time_weeks} weeks)")
    return SupplyCheck(status="swap", **common, swap_to=to.id, swap_stock=to.stock,
                       text=f"{head} is {m.lead_time_weeks} weeks with {_stock(m)}; expect {kind}.")


def warm_engine() -> None:
    """Pay the engine's first-call cost (pandapower import, about 6 s) off the request path (ruling B8)."""
    try:
        from kirchhoff.engine.api import warm_up
        warm_up()
    except Exception as exc:  # warming is best effort
        log.warning("engine warm-up failed: %r", exc)


def _verified(fields: dict[str, ExtractedField], key: str) -> ExtractedField | None:
    f = fields.get(key)
    return f if f is not None and f.verification == "verified" and f.value is not None else None


def supply_for(fields: dict[str, ExtractedField], appetite: Appetite, erp,
               supply_fn: SupplyFn = day_zero_supply) -> SupplyCheck | None:
    if not appetite.lead_time_check:
        return None
    asset = _verified(fields, "asset_type")
    if asset is None:
        return SupplyCheck(status="not_assessed", text="The asset type is not verified, so the supply check did not run.")
    if asset.value != "datahall":
        return SupplyCheck(status="not_assessed", text="The day-zero supply check covers AI data halls only.")
    mw, red, lead = (_verified(fields, k) for k in ("mw", "redundancy", "lead_time_weeks"))
    return supply_fn(float(mw.value) if mw else None, str(red.value) if red else None,
                     float(lead.value) if lead else None, erp)


def _asset(fields: dict[str, ExtractedField], appetite: Appetite) -> FitReason:
    f = _verified(fields, "asset_type")
    if f is None:
        return FitReason(rule="asset_pack", status="warn", text="The asset type is not stated or not verified.")
    label = ASSET_LABELS.get(str(f.value), str(f.value))
    if f.value in appetite.asset_types:
        return FitReason(rule="asset_pack", status="pass", text=f"{label} is one of our asset packs.")
    packs = ", ".join(ASSET_LABELS[a] for a in appetite.asset_types)
    return FitReason(rule="asset_pack", status="fail", text=f"{label} is not one of our asset packs ({packs}).")


def _mw(fields: dict[str, ExtractedField], appetite: Appetite) -> FitReason:
    lo, hi = appetite.mw
    rng = f"{fmt_number(lo)}–{fmt_number(hi)} MW range"
    f = _verified(fields, "mw")
    if f is not None:
        inside = lo <= float(f.value) <= hi
        return FitReason(rule="mw_range", status="pass" if inside else "fail",
                         text=f"{f.display} is {'inside' if inside else 'outside'} our {rng}.")
    raw = fields.get("mw")
    if raw is not None and raw.verification == "unverified_scan":
        return FitReason(rule="mw_range", status="warn",
                         text=f"The load is only on a scanned page ({raw.source_label}) and is not verified; "
                              "ask for a text copy.")
    if raw is not None:
        return FitReason(rule="mw_range", status="warn", text="The load could not be verified against its quote.")
    return FitReason(rule="mw_range", status="warn", text="No load (MW) is stated.")


def _region(fields: dict[str, ExtractedField], appetite: Appetite) -> FitReason:
    f = _verified(fields, "site")
    if f is None:
        return FitReason(rule="region", status="warn", text="The site is not stated or not verified.")
    name = region_of(str(f.value), appetite)
    if name:
        return FitReason(rule="region", status="pass", text=f"{f.value} is in {name}, one of our regions.")
    names = ", ".join(r.name for r in appetite.regions)
    return FitReason(rule="region", status="fail", text=f"{f.value} is outside our regions ({names}).")


def _deadline(fields: dict[str, ExtractedField], appetite: Appetite, as_of: float) -> FitReason:
    f = _verified(fields, "bid_due")
    due = parse_due(str(f.value)) if f else None
    if due is None:
        return FitReason(rule="deadline", status="warn", text="No verified bid due date yet; ask for it.")
    days, today, need = days_to_due(due, as_of), fmt_date(datetime.fromtimestamp(as_of, IST).date()), \
        appetite.min_days_to_bid_due
    if days < 0:
        return FitReason(rule="deadline", status="fail", text=f"Bid due {fmt_date(due)} has passed (as of {today}).")
    if days < need:
        return FitReason(rule="deadline", status="fail",
                         text=f"Bid due {fmt_date(due)}: {days} days from {today}, under our {need}-day minimum.")
    return FitReason(rule="deadline", status="pass",
                     text=f"Bid due {fmt_date(due)}: {days} days from {today} (minimum {need}).")


def assess_fit(*, is_bid: bool, fields: dict[str, ExtractedField], crm: CrmLink, appetite: Appetite, as_of: float,
               supply: SupplyCheck | None) -> FitResult:
    if not is_bid:
        where = (f"filed to {crm.account} · {crm.opportunity_name} in the CRM" if crm.opportunity_id
                 else "no CRM record to update")
        return FitResult(verdict=None, headline="Not a bid: no fit check.",
                         reasons=[FitReason(rule="not_a_bid", status="n/a", text=f"Not a bid; {where}.")])
    reasons = [_asset(fields, appetite), _mw(fields, appetite), _region(fields, appetite),
               _deadline(fields, appetite, as_of)]
    if supply is not None:
        reasons.append(FitReason(rule="supply", status=SUPPLY_STATUS[supply.status], text=supply.text))
    fails = [RULE_LABELS[r.rule] for r in reasons if r.status == "fail"]
    warns = [RULE_LABELS[r.rule] for r in reasons if r.status == "warn"]
    if fails:
        return FitResult(verdict="decline", headline=f"Decline: outside our appetite on {', '.join(fails)}.",
                         reasons=reasons, supply=supply)
    if warns:
        return FitResult(verdict="clarify", headline=f"Clarify before bidding: {', '.join(warns)}.",
                         reasons=reasons, supply=supply)
    headline = ("Pursue: inside our appetite; plan the transformer swap the lead-time limit needs."
                if supply is not None and supply.status == "swap" else "Pursue: inside our appetite on every rule.")
    return FitResult(verdict="pursue", headline=headline, reasons=reasons, supply=supply)
```

The engine imports sit inside `day_zero_supply` so that importing the API does not load the engine. On a fresh process the first call pays about 6 s for pandapower's import (see `warm_engine` and ruling B8); after that it takes about 0.2 s.

- [ ] **Step 6 [cut-safe]: The triage pipeline**

`services/api/kirchhoff/inbox/triage.py`:
```python
"""Inbox agent triage (spec §20). Gemini classifies the attachments, links the CRM and extracts bid fields with
verbatim quotes. Code verifies every quote (pdfplumber `verify_quote` on PDF pages that have text, a normalized
substring check on the email body), marks pages without a text layer "unverified (scan)", withholds unverified
numbers, sanitizes the LLM summary (spec §6.3) and runs the deterministic fit check."""
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from kirchhoff.agents.runner import MODEL, AgentRunner, AgentSpec, Attachment, run_json
from kirchhoff.agents.specs import INBOX
from kirchhoff.agents.trust import fmt_value, is_clean, sanitize
from kirchhoff.contracts import Opportunity
from kirchhoff.enterprise.world.inbox import Appetite, InboxEmail
from kirchhoff.intake.textnorm import normalize
from kirchhoff.intake.verify import PdfText, value_in_quote, verify_quote

from .fit import SupplyFn, assess_fit, day_zero_supply, fmt_date, parse_due, supply_for
from .models import (ASSET_LABELS, FIELD_LABELS, FIELD_ORDER, AttachmentTriage, CrmLink, ExtractedField,
                     InboxExtraction, RawCrm, RawField, TriageResult)

NUMERIC = ("mw", "lead_time_weeks")
TRIAGE_PROMPT = """Triage this email from the bids@ mailbox of Meridian Power Engineering, an EPC contractor for AI data
halls, grid connections and solar plants. The attached PDFs follow in the order listed under "Attachments".
Reply with JSON only:
{"is_bid": true if the email asks Meridian to bid or quote, else false,
 "summary": one sentence with no digits,
 "attachments": [{"attachment_id": a listed id, "kind": "tender"|"drawing"|"addendum"|"boq"|"brochure"|"other"}],
 "fields": [{"key": a field key, "value": the value, "unit": the unit or null, "source": "body" or an attachment id,
             "page": the PDF page number from 1, or null for the body,
             "verbatim_quote": an exact contiguous phrase copied from that page or from the body that contains the value}],
 "crm": {"account": one of the CRM accounts listed below or null, "opportunity_id": a listed opportunity id or null,
         "propose_new": true when this is a bid and no listed opportunity matches it}}
Field keys (omit a field you cannot find; never guess or paraphrase):
  client: the client company name as written;
  site: the site location as written, town and state;
  asset_type: one of "datahall", "grid", "solar", "substation", "other"; quote the phrase that shows it;
  mw: the IT or plant load in MW (MWp for solar) as a number;
  redundancy: the power redundancy as written, for example "2N";
  bid_due: the bid or quotation due date exactly as written, for example "13 November 2026";
  lead_time_weeks: the maximum equipment lead time in weeks as a number.
A value that appears only on a scanned image still counts: report it with its page."""


def build_message(email: InboxEmail, opportunities: Sequence[Opportunity]) -> str:
    lines = [TRIAGE_PROMPT, "", f"From: {email.from_name} <{email.from_addr}> ({email.from_org})", f"To: {email.to}",
             f"Subject: {email.subject}", "Body:", email.body, "", "Attachments:"]
    lines += [f"{i}. {a.id}: {a.name}" for i, a in enumerate(email.attachments, 1)] or ["(none)"]
    lines += ["", "CRM opportunities (id | account | name | stage):"]
    lines += [f"{o.id} | {o.account} | {o.name} | {o.stage}" for o in opportunities]
    return "\n".join(lines)


def _number(value) -> float | None:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _display(key: str, value, unit: str | None) -> str:
    if key == "asset_type":
        return ASSET_LABELS[str(value)]
    if key == "mw":
        return fmt_value(value, unit or "MW")
    if key == "lead_time_weeks":
        return fmt_value(value, "weeks")
    if key == "bid_due":
        d = parse_due(str(value))
        return fmt_date(d) if d else str(value)
    return str(value)


def verify_field(raw: RawField, email: InboxEmail, pdfs: dict[str, PdfText], names: dict[str, str]) -> ExtractedField:
    value = raw.value
    if raw.key in NUMERIC:
        value = _number(value)
    if raw.key == "asset_type":
        value = str(value).casefold() if value is not None else None
        value = value if value in ASSET_LABELS else None
    check_value = None if raw.key == "asset_type" else value  # a category is not printed; its quote must exist
    quote = normalize(raw.verbatim_quote)
    verification, bbox, page = "unverified", None, raw.page
    if raw.source == "body":
        source_label, page = "Email body", None
        if value is not None and len(quote) >= 8 and quote in normalize(email.body) and value_in_quote(check_value, quote):
            verification = "verified"
    else:
        name = names.get(raw.source, raw.source)
        source_label = f"{name} · p.{page}" if page else name
        pdf = pdfs.get(raw.source)
        if pdf is not None and page is not None and 1 <= page <= pdf.page_count:
            if not pdf.page_text(page):
                verification = "unverified_scan"
            elif value is not None:
                chk = verify_quote(pdf, page, raw.verbatim_quote, check_value)
                if chk.ok:
                    verification, bbox = "verified", list(chk.bbox) if chk.bbox else None
    unit = raw.unit if raw.unit and is_clean(raw.unit, ()) else None
    if verification == "verified":
        return ExtractedField(key=raw.key, label=FIELD_LABELS[raw.key], value=value, unit=unit,
                              display=_display(raw.key, value, unit), source=raw.source, source_label=source_label,
                              page=page, quote=quote, verification="verified", bbox=bbox)
    shown = value if isinstance(value, str) and is_clean(value, ()) else None  # never an unverified digit (§6.3)
    display = (_display(raw.key, shown, unit) if shown is not None
               else "Not verified (scan)" if verification == "unverified_scan" else "Not verified")
    return ExtractedField(key=raw.key, label=FIELD_LABELS[raw.key], value=shown, unit=unit, display=display,
                          source=raw.source, source_label=source_label, page=page, verification=verification)


def _subject_name(subject: str) -> str:
    return re.sub(r"^((re|fw|fwd)\s*:\s*)+", "", subject, flags=re.IGNORECASE).strip()


def link_crm(raw: RawCrm, is_bid: bool, email: InboxEmail, opportunities: Sequence[Opportunity]) -> CrmLink:
    by_id = {o.id: o for o in opportunities}
    o = by_id.get(raw.opportunity_id or "")
    if o is not None:
        return CrmLink(account=o.account, opportunity_id=o.id, opportunity_name=o.name, stage=o.stage)
    account = raw.account if raw.account in {x.account for x in opportunities} else None
    if is_bid and raw.propose_new:
        return CrmLink(account=account or email.from_org, proposed=True, proposed_name=_subject_name(email.subject))
    return CrmLink(account=account)


def triage_email(email: InboxEmail, *, runner: AgentRunner, scenarios_dir: Path, opportunities: Sequence[Opportunity],
                 erp, appetite: Appetite, as_of: float, source: Literal["live", "precomputed"], now: float,
                 supply_fn: SupplyFn = day_zero_supply, spec: AgentSpec = INBOX) -> TriageResult:
    paths = {a.id: Path(scenarios_dir) / a.source for a in email.attachments}
    files = [Attachment(paths[a.id].read_bytes(), a.content_type) for a in email.attachments]
    raw, res = run_json(runner, spec, f"triage:{email.id}", build_message(email, opportunities), InboxExtraction,
                        attachments=files)
    names = {a.id: a.name for a in email.attachments}
    kinds = {a.attachment_id: a.kind for a in raw.attachments}
    pdfs = {aid: PdfText(p) for aid, p in paths.items()}
    try:
        attachments = [AttachmentTriage(attachment_id=a.id, name=a.name, kind=kinds.get(a.id, "other"),
                                        scanned=all(not pdfs[a.id].page_text(p)
                                                    for p in range(1, pdfs[a.id].page_count + 1)))
                       for a in email.attachments]
        seen: dict[str, ExtractedField] = {}
        for f in raw.fields:
            if f.key not in seen:
                seen[f.key] = verify_field(f, email, pdfs, names)
    finally:
        for pdf in pdfs.values():
            pdf.close()
    fields = [seen[k] for k in FIELD_ORDER if k in seen]
    crm = link_crm(raw.crm, raw.is_bid, email, opportunities)
    supply = supply_for(seen, appetite, erp, supply_fn) if raw.is_bid else None
    allowed = set(paths) | {o.id for o in opportunities}
    summary = sanitize(raw.summary, allowed, f"{'Bid' if raw.is_bid else 'Email'} from {email.from_org}.")
    return TriageResult(
        email_id=email.id, is_bid=raw.is_bid, summary=summary, attachments=attachments, fields=fields, crm=crm,
        fit=assess_fit(is_bid=raw.is_bid, fields=seen, crm=crm, appetite=appetite, as_of=as_of, supply=supply),
        quotes_verified=sum(f.verification == "verified" for f in fields), quotes_total=len(fields), source=source,
        model=MODEL, triaged_at=now, tokens_in=res.tokens_in, tokens_out=res.tokens_out)
```

- [ ] **Step 7 [cut-safe]: The precompute script**

`services/api/kirchhoff/inbox/precompute.py`:
```python
"""Precompute the triage of every seeded email with the real Inbox agent (spec §20 "static first"; ruling B5).
Run once at golden-capture time, from services/api:
  GOOGLE_GENAI_USE_VERTEXAI=true GOOGLE_CLOUD_PROJECT=ordinal-mep GOOGLE_CLOUD_QUOTA_PROJECT=ordinal-mep \
    GOOGLE_CLOUD_LOCATION=global uv run python -m kirchhoff.inbox.precompute
then `make demo-world` folds scenarios/demo_world/captures/inbox-triage.json into /demo/inbox.json and the seed.
`--backend replay` runs the FAKE_REPLIES fixtures instead (no cloud access)."""
import argparse
import dataclasses
import json
import sys
from pathlib import Path

from kirchhoff.agents.ports import ErpSnapshot
from kirchhoff.agents.runner import MODEL, AgentRunner, ReplayRunner
from kirchhoff.agents.specs import INBOX
from kirchhoff.contracts import Opportunity
from kirchhoff.enterprise.world.inbox import CAPTURE_VERSION, InboxSeed, load_inbox_seed

from .fit import SupplyFn, day_zero_supply
from .triage import triage_email

OFFLINE_TIMEOUT_S = 60.0  # no request budget offline; the live endpoint keeps INBOX.timeout_s


def precompute(seed: InboxSeed, *, runner: AgentRunner, scenarios_dir: Path, opportunities: list[Opportunity], erp,
               supply_fn: SupplyFn = day_zero_supply) -> dict:
    spec = dataclasses.replace(INBOX, timeout_s=OFFLINE_TIMEOUT_S)
    results = {e.id: triage_email(e, runner=runner, scenarios_dir=scenarios_dir, opportunities=opportunities, erp=erp,
                                  appetite=seed.appetite, as_of=seed.as_of, source="precomputed", now=seed.as_of,
                                  supply_fn=supply_fn, spec=spec).model_dump(mode="json")
               for e in sorted(seed.emails, key=lambda m: m.id)}
    return {"version": CAPTURE_VERSION, "model": MODEL, "as_of": seed.as_of, "results": results}


def _runner(backend: str) -> AgentRunner:
    if backend == "replay":
        from kirchhoff.runs.fakes import FAKE_REPLIES
        return ReplayRunner(FAKE_REPLIES)
    if backend == "genai":
        from kirchhoff.agents.genai_runner import GenaiRunner
        return GenaiRunner()
    from kirchhoff.agents.adk_runner import AdkRunner
    return AdkRunner()


def main(argv: list[str] | None = None) -> int:
    from kirchhoff.api.deps import scenarios_dir
    from kirchhoff.enterprise.client import make_enterprise_client

    scen = scenarios_dir()
    ap = argparse.ArgumentParser(description="Precompute the bids inbox triage with the real Inbox agent")
    ap.add_argument("--seed", type=Path, default=scen / "demo_world" / "out" / "inbox_seed.json")
    ap.add_argument("--out", type=Path, default=scen / "demo_world" / "captures" / "inbox-triage.json")
    ap.add_argument("--backend", choices=("adk", "genai", "replay"), default="adk")
    args = ap.parse_args(argv)
    enterprise = make_enterprise_client()
    try:
        capture = precompute(load_inbox_seed(args.seed), runner=_runner(args.backend), scenarios_dir=scen,
                             opportunities=enterprise.list_opportunities(None),
                             erp=ErpSnapshot(enterprise.list_materials()))
    except Exception as exc:  # never write a partial capture
        print(f"precompute failed, nothing written: {exc!r}", file=sys.stderr)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(capture, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    for eid, r in sorted(capture["results"].items()):
        print(f"{eid}: {r['fit']['verdict'] or 'not a bid'} ({r['quotes_verified']}/{r['quotes_total']} quotes verified)")
    print(f"wrote {args.out}; run `make demo-world` to fold it into the static bundle")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 8 [cut-safe]: Run the pipeline tests**

Run: `cd services/api && uv run pytest tests/inbox -q`
Expected: `18 passed`. The first supply test pays the engine's pandapower import (about 6 s).

- [ ] **Step 9 [cut-safe]: Commit the pipeline**

```bash
git add services/api/kirchhoff/inbox/__init__.py services/api/kirchhoff/inbox/models.py \
  services/api/kirchhoff/inbox/fit.py services/api/kirchhoff/inbox/triage.py services/api/kirchhoff/inbox/precompute.py \
  services/api/kirchhoff/agents/specs.py services/api/kirchhoff/agents/ports.py services/api/kirchhoff/runs/fakes.py \
  services/api/tests/inbox
git commit -m "feat(inbox): Inbox agent triage with verified quotes, deterministic fit and day-zero supply check, precompute

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 10 [cut]: Write the failing endpoint tests**

In `services/api/tests/api/conftest.py`, add these imports at the top:
```python
import shutil

from kirchhoff.enterprise.world.inbox import load_inbox, load_inbox_seed
from kirchhoff.inbox.triage import triage_email
```
and append:
```python
REPO = Path(__file__).resolve().parents[4]


@pytest.fixture
def inbox_ready(deps):
    """I-1's inbox seed and rendered attachments in the fake scenarios dir (the API's file fallback). Precomputed
    triage is stripped, so the tests do not depend on whether the golden capture has been folded in yet."""
    out = deps.scenarios_dir / "demo_world" / "out"
    out.mkdir(parents=True, exist_ok=True)
    seed = load_inbox_seed(REPO / "scenarios" / "demo_world" / "out" / "inbox_seed.json")
    seed = seed.model_copy(update={"emails": [e.model_copy(update={"triage": None}) for e in seed.emails]})
    (out / "inbox_seed.json").write_text(seed.model_dump_json(indent=2), encoding="utf-8")
    shutil.copytree(REPO / "scenarios" / "demo_world" / "out" / "inbox", out / "inbox", dirs_exist_ok=True)
    return deps


@pytest.fixture
def inbox_precomputed(inbox_ready):
    """Firestore seed/inbox with every email's precomputed triage (replayed), as WS4's seed loader writes it."""
    deps = inbox_ready
    seed = load_inbox_seed(deps.scenarios_dir / "demo_world" / "out" / "inbox_seed.json")
    emails = [e.model_copy(update={"triage": triage_email(
        e, runner=deps.runner, scenarios_dir=deps.scenarios_dir, opportunities=deps.enterprise.list_opportunities(None),
        erp=deps.erp(), appetite=seed.appetite, as_of=seed.as_of, source="precomputed",
        now=seed.as_of).model_dump(mode="json")}) for e in seed.emails]
    load_inbox(deps.store, seed.model_copy(update={"emails": emails}))
    return deps
```

`services/api/tests/api/test_api_inbox.py`:
```python
import time

from fastapi.testclient import TestClient

from kirchhoff.api import inbox_routes
from kirchhoff.api.app import create_app
from kirchhoff.runs.fakes import CheckedStore, build_fake_deps

SWAP = ("26-week limit; the 2.5 MVA unit TX-2500 is 98 weeks with none in stock; "
        "expect an in-stock swap to TX-3150 (3.15 MVA, 6 in stock).")


def test_inbox_needs_a_token(client, inbox_ready):
    assert client.get("/api/inbox").status_code == 401


def test_inbox_without_a_seed_is_503(tmp_path):
    deps = build_fake_deps(CheckedStore(), tmp_path)
    r = TestClient(create_app(deps=deps, verify_token=lambda t: "u1")).get("/api/inbox", headers={"Authorization": "Bearer t"})
    assert r.status_code == 503 and r.json() == {"detail": "inbox_unavailable"}


def test_get_inbox_returns_the_seed_newest_first(client, inbox_ready, auth):
    body = client.get("/api/inbox", headers=auth).json()
    assert body["mailbox"] == "bids@meridian-power.example" and body["label"] == "sandbox (simulated)"
    assert [e["id"] for e in body["emails"]][:2] == ["em-hall-b", "em-tapti-brochure"]
    assert {e["status"] for e in body["emails"]} == {"new"} and all(e["pursue"] is None for e in body["emails"])


def test_triage_is_live_only_for_hall_b(client, inbox_ready, auth):
    r = client.post("/api/inbox/em-konkan-rfi/triage", headers=auth)
    assert r.status_code == 409 and r.json() == {"detail": "precomputed"}
    assert client.post("/api/inbox/em-nope/triage", headers=auth).status_code == 404


def test_live_triage_of_hall_b_is_stored_in_the_overlay(client, inbox_ready, auth, firestore_safe):
    r = client.post("/api/inbox/em-hall-b/triage", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "live" and body["fit"]["verdict"] == "pursue" and body["fit"]["supply"]["text"] == SWAP
    assert (body["quotes_verified"], body["quotes_total"]) == (7, 7)
    hall_b = next(e for e in client.get("/api/inbox", headers=auth).json()["emails"] if e["id"] == "em-hall-b")
    assert hall_b["status"] == "triaged" and hall_b["triage"] == body
    firestore_safe(inbox_ready.store)


def test_triage_failure_timeout_and_rate_limit(client, inbox_ready, auth, monkeypatch):
    key = "inbox:triage:em-hall-b"
    recorded, inbox_ready.runner.replies[key] = inbox_ready.runner.replies[key], {"raise": "vertex down"}
    r = client.post("/api/inbox/em-hall-b/triage", headers=auth)
    assert r.status_code == 502 and r.json() == {"detail": "triage_failed"}
    inbox_ready.runner.replies[key] = recorded

    def slow(*args):
        time.sleep(0.3)

    monkeypatch.setattr(inbox_routes, "SUPPLY_FN", slow)
    monkeypatch.setattr(inbox_routes, "TRIAGE_TIMEOUT_S", 0.05)
    r = client.post("/api/inbox/em-hall-b/triage", headers=auth)
    assert r.status_code == 504 and r.json() == {"detail": "timeout"}
    now = inbox_ready.clock()
    inbox_ready.store.set_doc("workspaces/u1", {"triage_starts": [now - 60] * 10})
    r = client.post("/api/inbox/em-hall-b/triage", headers=auth)
    assert r.status_code == 429 and r.json() == {"detail": "triage_rate_limit"}


def test_pursue_hall_b_sets_qualifying_and_opens_its_intake(client, inbox_ready, auth):
    r = client.post("/api/inbox/em-hall-b/pursue", headers=auth)
    assert r.status_code == 409 and r.json() == {"detail": "not_triaged"}  # no capture in the seed, no live triage
    client.post("/api/inbox/em-hall-b/triage", headers=auth)
    r = client.post("/api/inbox/em-hall-b/pursue", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json() == {"email_id": "em-hall-b", "project_id": "hall-b", "project_name": None,
                        "project_created": False, "opportunity_id": "opp-hall-b",
                        "opportunity_name": "Hall B design-build", "stage": "Qualification",
                        "previous_stage": "Design in progress", "opportunity_created": False,
                        "open": "/app/p/hall-b"}
    assert inbox_ready.enterprise.stages[("u1", "opp-hall-b")].stage == "Qualification"
    assert client.post("/api/inbox/em-hall-b/pursue", headers=auth).json() == r.json()  # idempotent
    hall_b = next(e for e in client.get("/api/inbox", headers=auth).json()["emails"] if e["id"] == "em-hall-b")
    assert hall_b["status"] == "pursued" and hall_b["pursue"]["stage"] == "Qualification"


def test_pursue_never_reopens_a_signed_deal(client, inbox_ready, auth):
    inbox_ready.enterprise.set_opportunity_stage("u1", "opp-hall-b", "Design approved")
    client.post("/api/inbox/em-hall-b/triage", headers=auth)
    body = client.post("/api/inbox/em-hall-b/pursue", headers=auth).json()
    assert (body["stage"], body["previous_stage"]) == ("Design approved", "Design approved")


def test_pursue_creates_the_project_and_the_opportunity(client, inbox_precomputed, auth, firestore_safe):
    deps = inbox_precomputed
    r = client.post("/api/inbox/em-suryodaya-solar/pursue", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["project_id"], body["project_created"], body["open"]) == ("bid-suryodaya-solar", True, None)
    assert body["project_name"] == "Suryodaya Renewables · Enquiry: solar EPC near Anantapur"
    assert (body["opportunity_id"], body["opportunity_created"], body["stage"], body["previous_stage"]) == \
        ("opp-em-suryodaya-solar", True, "Qualification", None)
    project = deps.store.get_doc("workspaces/u1/projects/bid-suryodaya-solar")
    assert (project["asset_pack"], project["state"], project["client"]) == ("solar", "draft", "Suryodaya Renewables")
    assert "opp-em-suryodaya-solar" in {o.id for o in deps.enterprise.list_opportunities("u1")}
    vindhya = client.post("/api/inbox/em-vindhya-boq/pursue", headers=auth).json()
    assert (vindhya["opportunity_id"], vindhya["previous_stage"], vindhya["project_id"]) == \
        ("opp-vindhya-cpp", "Qualification", "bid-vindhya-boq")
    for email_id in ("em-narmada-400kv", "em-tapti-brochure"):  # decline, not a bid
        r = client.post(f"/api/inbox/{email_id}/pursue", headers=auth)
        assert r.status_code == 409 and r.json() == {"detail": "cannot_pursue"}
    firestore_safe(deps.store)


def test_pursue_reports_an_unavailable_crm(client, inbox_precomputed, auth, monkeypatch):
    def down(uid):
        raise RuntimeError("sandbox down")

    monkeypatch.setattr(inbox_precomputed.enterprise, "list_opportunities", down)
    r = client.post("/api/inbox/em-suryodaya-solar/pursue", headers=auth)
    assert r.status_code == 502 and r.json() == {"detail": "enterprise_unavailable"}


def test_reset_clears_the_inbox_overlay(client, inbox_ready, auth):
    client.post("/api/inbox/em-hall-b/triage", headers=auth)
    client.post("/api/inbox/em-hall-b/pursue", headers=auth)
    assert client.post("/api/workspace/reset", headers=auth).json() == {"ok": True}
    assert inbox_ready.store.list_docs("workspaces/u1/inbox") == []
    assert ("u1", "opp-hall-b") not in inbox_ready.enterprise.stages
```

- [ ] **Step 11 [cut]: Run to verify failure**

Run: `cd services/api && uv run pytest tests/api/test_api_inbox.py -q`
Expected: collection ERROR with `ImportError: cannot import name 'inbox_routes' from 'kirchhoff.api'`.

- [ ] **Step 12 [cut] (coordinate with Mehul before merging: the `api/app.py` and `inbox_routes` import-line edit touches a live P2 Task 9–12 file): Implement the seed/overlay access, the routes and the wiring**

`services/api/kirchhoff/inbox/store.py`:
```python
"""Bids inbox data for the API: the seed (Firestore seed/inbox, else the image's inbox_seed.json) and the visitor's
overlay (workspaces/{uid}/inbox/{email_id}), merged into the InboxSnapshot the web app renders."""
from pathlib import Path

from kirchhoff.enterprise.world.inbox import SEED_DOC, SEED_EMAILS, InboxSeed, load_inbox_seed
from kirchhoff.store import Store


def overlay_path(uid: str, email_id: str) -> str:
    return f"workspaces/{uid}/inbox/{email_id}"


def project_path(uid: str, project_id: str) -> str:
    return f"workspaces/{uid}/projects/{project_id}"


def load_seed(store: Store, scenarios_dir: Path) -> InboxSeed:
    meta = store.get_doc(SEED_DOC)
    if meta is not None:
        return InboxSeed.model_validate({**meta, "emails": store.list_docs(SEED_EMAILS)})
    return load_inbox_seed(Path(scenarios_dir) / "demo_world" / "out" / "inbox_seed.json")


def overlays(store: Store, uid: str) -> dict[str, dict]:
    return {d["email_id"]: d for d in store.list_docs(f"workspaces/{uid}/inbox") if d.get("email_id")}


def inbox_view(seed: InboxSeed, overlay: dict[str, dict]) -> dict:
    emails = []
    for e in sorted(seed.emails, key=lambda m: (-m.received_at, m.id)):
        ov = overlay.get(e.id, {})
        emails.append({**e.model_dump(mode="json"), "triage": ov.get("triage") or (e.triage or None),
                       "status": ov.get("status", "new"), "pursue": ov.get("pursue")})
    return {**seed.model_dump(mode="json", exclude={"emails"}), "emails": emails}
```

`services/api/kirchhoff/api/inbox_routes.py`:
```python
"""Bids inbox endpoints (spec §20; addendum Task I-2). GET merges the seed with the visitor's overlay. Triage runs
live only for the Hall B email (others answer 409 "precomputed"). Pursue creates the project and sets the CRM
opportunity to "Qualification" through the enterprise port (rulings B3, B4)."""
import logging
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout

from fastapi import APIRouter, Depends

from kirchhoff.agents.ports import STAGE_QUALIFYING
from kirchhoff.contracts import Opportunity, Project
from kirchhoff.inbox import fit
from kirchhoff.inbox.models import PursueResult, TriageResult
from kirchhoff.inbox.store import inbox_view, load_seed, overlay_path, overlays, project_path
from kirchhoff.inbox.triage import triage_email
from kirchhoff.runs.deps import Deps

from .errors import err

log = logging.getLogger("kirchhoff.inbox")
TRIAGE_TIMEOUT_S = 9.5
TRIAGES_PER_HOUR = 10
KEEP_STAGES = ("Design approved", "Closed won", "Closed lost")  # Pursue never reopens these (ruling B3)
PACKS = ("datahall", "grid", "solar")
SUPPLY_FN = fit.day_zero_supply  # module attribute so tests can swap it
_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="inbox")


def make_router(deps: Deps, current_uid) -> APIRouter:
    router = APIRouter()
    if os.environ.get("K_SERVICE"):  # on Cloud Run: warm the engine before the first triage (ruling B8)
        threading.Thread(target=fit.warm_engine, daemon=True).start()

    def seed_and_email(email_id: str | None = None):
        try:
            seed = load_seed(deps.store, deps.scenarios_dir)
        except (OSError, ValueError) as exc:
            log.warning("inbox seed unavailable: %r", exc)
            return None, None, err(503, "inbox_unavailable")
        email = next((e for e in seed.emails if e.id == email_id), None)
        if email_id is not None and email is None:
            return seed, None, err(404, "email_not_found")
        return seed, email, None

    @router.get("/api/inbox")
    def get_inbox(uid: str = Depends(current_uid)):
        seed, _, error = seed_and_email()
        return error or inbox_view(seed, overlays(deps.store, uid))

    @router.post("/api/inbox/{email_id}/triage")
    def triage(email_id: str, uid: str = Depends(current_uid)):
        seed, email, error = seed_and_email(email_id)
        if error:
            return error
        if not email.live_triage:
            return err(409, "precomputed")
        now, ws_path = deps.clock(), f"workspaces/{uid}"
        recent = [t for t in (deps.store.get_doc(ws_path) or {}).get("triage_starts", []) if now - t < 3600]
        if len(recent) >= TRIAGES_PER_HOUR:
            return err(429, "triage_rate_limit")
        deps.store.update_doc(ws_path, {"triage_starts": recent + [now]})

        def run() -> TriageResult:
            return triage_email(email, runner=deps.runner, scenarios_dir=deps.scenarios_dir,
                                opportunities=deps.enterprise.list_opportunities(uid), erp=deps.erp(),
                                appetite=seed.appetite, as_of=seed.as_of, source="live", now=now,
                                supply_fn=SUPPLY_FN)

        try:
            result = _POOL.submit(run).result(timeout=TRIAGE_TIMEOUT_S)
        except FuturesTimeout:
            return err(504, "timeout")
        except Exception as exc:  # agent, repair or enterprise failure: the UI falls back to the recorded triage
            log.warning("live triage failed for %s: %r", email_id, exc)
            return err(502, "triage_failed")
        prev = deps.store.get_doc(overlay_path(uid, email_id)) or {}
        deps.store.set_doc(overlay_path(uid, email_id), {
            "email_id": email_id, "status": "pursued" if prev.get("status") == "pursued" else "triaged",
            "triage": result.model_dump(mode="json"), "pursue": prev.get("pursue"), "updated_at": now})
        return result.model_dump(mode="json")

    @router.post("/api/inbox/{email_id}/pursue")
    def pursue(email_id: str, uid: str = Depends(current_uid)):
        seed, email, error = seed_and_email(email_id)
        if error:
            return error
        prev = deps.store.get_doc(overlay_path(uid, email_id)) or {}
        if prev.get("pursue"):
            return prev["pursue"]  # idempotent
        raw = prev.get("triage") or email.triage
        if raw is None:
            return err(409, "not_triaged")
        t = TriageResult.model_validate(raw)
        asset = next((f for f in t.fields if f.key == "asset_type" and f.verification == "verified"), None)
        pack = asset.value if asset is not None and asset.value in PACKS else None
        if t.fit.verdict not in ("pursue", "clarify") or pack is None:
            return err(409, "cannot_pursue")
        now = deps.clock()
        try:
            current = {o.id: o for o in deps.enterprise.list_opportunities(uid)}
            opp = current.get(t.crm.opportunity_id or "")
            if opp is not None:
                previous, created = opp.stage, False
                stage = (previous if previous in KEEP_STAGES
                         else deps.enterprise.set_opportunity_stage(uid, opp.id, STAGE_QUALIFYING).stage)
            else:
                opp = deps.enterprise.create_opportunity(uid, Opportunity(
                    id=f"opp-{email.id}", account=t.crm.account or email.from_org,
                    name=t.crm.proposed_name or email.subject, stage=STAGE_QUALIFYING, value=0.0,
                    next_step="Qualify the bid from the bids inbox"))
                previous, created, stage = None, True, opp.stage
        except Exception as exc:
            log.warning("pursue %s: enterprise call failed: %r", email_id, exc)
            return err(502, "enterprise_unavailable")
        if email.project_id:  # an existing world project (Hall B): open its intake flow (ruling B4)
            project_id, project_name, project_created, open_ = email.project_id, None, False, f"/app/p/{email.project_id}"
        else:
            project_id = "bid-" + re.sub(r"^em-", "", email.id)
            project_name, project_created, open_ = f"{opp.account} · {opp.name}", True, None
            deps.store.set_doc(project_path(uid, project_id), Project(
                id=project_id, name=project_name, client=opp.account, asset_pack=pack, state="draft", sample=False,
                updated_at=now).model_dump(mode="json"))
        result = PursueResult(email_id=email_id, project_id=project_id, project_name=project_name,
                              project_created=project_created, opportunity_id=opp.id, opportunity_name=opp.name,
                              stage=stage, previous_stage=previous, opportunity_created=created,
                              open=open_).model_dump(mode="json")
        deps.store.set_doc(overlay_path(uid, email_id), {"email_id": email_id, "status": "pursued",
                                                         "triage": prev.get("triage"), "pursue": result,
                                                         "updated_at": now})
        return result

    return router
```

In `services/api/kirchhoff/api/app.py`:
- Add `inbox_routes` to the `from . import …` line. On Task 12's file it reads `from . import inbox_routes, runs_routes, workspace_routes`; later tasks add their own modules to the same line.
- Directly after `app.include_router(runs_routes.make_router(deps, current_uid))`, add:
```python
    app.include_router(inbox_routes.make_router(deps, current_uid))
```

- [ ] **Step 13 [cut]: Run the endpoint tests and the whole suite**

Run: `cd services/api && uv run pytest tests/api/test_api_inbox.py -q && uv run pytest -q`
Expected: `11 passed`, then the whole suite passes (live tests skipped).

- [ ] **Step 14 [cut]: Commit the endpoints**

```bash
git add services/api/kirchhoff/inbox/store.py services/api/kirchhoff/api/inbox_routes.py services/api/kirchhoff/api/app.py \
  services/api/tests/api/conftest.py services/api/tests/api/test_api_inbox.py
git commit -m "feat(api): bids inbox endpoints (seed + overlay, live Hall B triage, Pursue to Qualification)

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 15 [cut-safe] (controller-run after merge, at golden capture, with P4 Task 14): Freeze the real agent's triage into the static bundle**

Run on the merged `build` branch, after I-1 and Steps 1–9 have landed:
```bash
cd services/api && GOOGLE_GENAI_USE_VERTEXAI=true GOOGLE_CLOUD_PROJECT=ordinal-mep GOOGLE_CLOUD_QUOTA_PROJECT=ordinal-mep \
  GOOGLE_CLOUD_LOCATION=global uv run python -m kirchhoff.inbox.precompute && cd ../.. && make demo-world && \
  cd services/api && uv run python ../../scenarios/demo_world/build_inbox.py --check
```
Expected:
- One line per email, for example `em-hall-b: pursue (7/7 quotes verified)` and `em-vindhya-boq: clarify (4/5 quotes verified)`.
- `wrote …/scenarios/demo_world/captures/inbox-triage.json`.
- `inbox <16 hex>: 6 emails, 12 files; triaged ['em-hall-b', …]` and `inbox up to date`.

If the real agent's verdicts differ from `VERDICTS` in `test_inbox_precompute.py`, look at the capture first. Usually a quote was not copied verbatim, so that field is shown as "Not verified" and the verdict becomes Clarify. Re-run once. Never hand-edit the capture. Commit as WS4:
```bash
git add scenarios/demo_world/captures/inbox-triage.json apps/web/public/demo/inbox.json scenarios/demo_world/out/inbox_seed.json
git commit -m "chore(demo-world): freeze the Inbox agent's triage of the seeded emails

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```
Controller-run after merge: `make seed-enterprise` (Firestore `seed/inbox` now carries the triage) and the next normal deploy. No task implementer runs these.

- [ ] **Step 16: Tell WS3, WS4 and the controller**

"I-2 landed:
- The `TriageResult` and `PursueResult` shapes are in `kirchhoff/inbox/models.py` (WS3 mirrors them in `src/lib/types.ts`).
- Endpoints: `GET /api/inbox`; `POST /api/inbox/{id}/triage` (Hall B only, 9.5 s budget, 409 `precomputed` elsewhere); `POST /api/inbox/{id}/pursue` (Hall B returns `open: "/app/p/hall-b"`). Error codes: `inbox_unavailable`, `email_not_found`, `precomputed`, `triage_rate_limit`, `triage_failed`, `timeout`, `not_triaged`, `cannot_pursue`, `enterprise_unavailable`.
- Visitor writes go to `workspaces/{uid}/inbox/{email_id}` and `workspaces/{uid}/projects/{pid}`, and reset clears them.
- At golden capture, run Step 15 before `make demo-world`."

---

### Task I-3 (WS3): Bids inbox page

Spec §20, §12 and §13. A list and detail page at `/app/inbox` and `/app/inbox/:emailId`, in the style of P3 Task 13's Integrations page.
- **Data:** static first (`/demo/inbox.json` from I-1, with the triage I-2 precomputes), live second (`GET /api/inbox` adds the visitor's overlay).
- **Detail:** attachment chips by class (scans marked), a CRM link to the Integrations page, the extracted fields with "quote verified" or "unverified (scan)" marks, the fit verdict card with every reason and the day-zero supply line, and Pursue. Pursue falls back to opening Hall B when the API is down.
- **Triage button:** on the Hall B email only, with a progress state, falling back to the recorded result.
- **Dashboard:** a "Bids inbox · N new" entry that carries an optional tour anchor. The 7-step tour is unchanged.
- **UI rules:** status is icon + text, everything is keyboard-reachable, and the progress spinner stops under reduced motion.

Steps 1–8 are **[cut-safe]** (the static page). Steps 9–13 are **[cut]** (the live Triage button).

**Branch:** `jd/inbox-i3`, cut from `build`. Can start now (it renders from its own fixture); rebase on `build` before opening the PR.

**Conflicts with in-flight work:** P3 Tasks 11–14 are live on `apps/web/src/workspace/**`, `App.tsx` and `pages/**` right now, and this task touches two of those:
- `apps/web/src/App.tsx`: the new import and the two `<Route>` lines are inserted next to an existing route, not appended at file end. **Coordinate with Mehul before merging** and rebase immediately before the PR so the route list still matches whatever P3 Task 13/14 landed.
- `apps/web/src/pages/Dashboard.tsx`: the `InboxEntry` component is a self-contained new function (effectively append-only, inserted above `Dashboard`), but the one-line call site is inserted inside the existing `Dashboard` JSX. **Coordinate with Mehul before merging** for that single line; the plan already notes it works whether or not P3 Task 14 has landed, since Task 14 does not touch those exact lines — re-verify that assumption against `build` at merge time.
- `apps/web/src/shell/AppShell.tsx` is not in the live conflict list (not under `workspace/**`, `pages/**` or `App.tsx`), so the `nav` array edit is unflagged, but confirm against the live file since multiple tasks (P3 Task 5, Task 14) have touched it historically.
- `lib/types.ts`, `data/staticData.ts`, `services/apiClient.ts`, `test/render.tsx`, `test/fixtures/index.ts` are not owned by any live workstream.

**Files:**
- Create: `apps/web/src/inbox/useInbox.ts`, `apps/web/src/inbox/inboxMeta.ts`, `apps/web/src/inbox/inboxTour.ts`, `apps/web/src/inbox/EmailDetail.tsx`, `apps/web/src/inbox/InboxPage.tsx`, `apps/web/src/inbox/TriageButton.tsx` ([cut]), `apps/web/src/test/fixtures/inbox.json`
- Modify: `apps/web/src/lib/types.ts` (append the inbox types), `apps/web/src/data/staticData.ts` (`loadInboxSnapshot`), `apps/web/src/services/apiClient.ts` (`inbox`, `triage`, `pursue`, error sentences), `apps/web/src/test/render.tsx` and `apps/web/src/test/fixtures/index.ts` (fixture wiring), `apps/web/src/App.tsx` (routes), `apps/web/src/pages/Dashboard.tsx` (entry), `apps/web/src/shell/AppShell.tsx` (nav link)
- Test: `apps/web/src/inbox/InboxPage.test.tsx`, `apps/web/src/inbox/TriageButton.test.tsx` ([cut]); append to `apps/web/src/pages/Dashboard.test.tsx` and `apps/web/src/services/apiClient.test.ts`

**Interfaces:**
- Consumes:
  - P3 Task 1: `FindingStatus`, `AssetPack` (`src/lib/types.ts`); `fmtTs`, `fmtRelative` (`src/lib/format.ts`); `SandboxLabel`, `EmptyState` (`src/components/Labels.tsx`); `StatusBadge` (`compact` shows icon + label); `readJson`/`writeJson` (`src/lib/storage.ts`, keys prefixed `kirchhoff.`).
  - P3 Task 3: `JsonFetch`, `fetchJson` (`src/data/staticData.ts`); `ApiClient`, `httpApiClient`, `ApiError`, `describeApiError`; `useServices()`; test helpers `fakeApi`, `fakeServices`, `renderWithProviders`, `STATIC_FILES`.
  - P3 Task 5: `useWorld`, `useWorldStore`, `useWorldProject(pid)`; the `/app` routes and `AppShell`'s `nav` array; the Dashboard's projects heading block.
  - P3 Task 14 (optional): `TourStep` shape `{id, route, target, title, body}` (not imported).
  - Data shapes: I-1's `inbox.json` (`InboxSeed`) and I-2's `TriageResult` and `PursueResult` and endpoints. If I-2 has not landed, `api.inbox()` fails and the static file is used.
- Produces:
  - `src/lib/types.ts`: `AttachmentKind`, `InboxFieldKey`, `Verification`, `Verdict`, `InboxAttachment`, `AttachmentTriage`, `ExtractedField`, `CrmLink`, `FitReason`, `SupplyCheck`, `FitResult`, `TriageResult`, `PursueResult`, `InboxEmail`, `InboxAppetite`, `InboxSnapshot`.
  - `loadInboxSnapshot(get) -> Promise<InboxSnapshot>` (`/demo/inbox.json`). `ApiClient.inbox()`, `.triage(emailId)`, `.pursue(emailId)`.
  - `src/inbox/useInbox.ts`: `useInboxStore`, `resetInboxStore()`, `useInbox() -> {data, live, loading, error, read}`, `markRead(id)`, `unreadCount(data, read)`, `applyTriage(id, triage)`, `applyPursue(id, pursue)`.
  - `src/inbox/inboxMeta.ts`: `VERDICT_META`, `verdictMeta(t)`, `VERIFICATION_META`, `KIND_ORDER`, `KIND_LABEL`, `appetiteLine(appetite)`.
  - Components and routes: `<InboxPage/>` at `/app/inbox` and `/app/inbox/:emailId`; `<EmailDetail email/>`, `<VerdictBadge triage/>`; `<TriageButton email/>` ([cut]).
  - Tour hook: `INBOX_TOUR_STEP` (not in `TOUR_STEPS`); anchor `[data-tour="inbox"]` on the dashboard entry. Nav link "Bids inbox".

- [ ] **Step 1 [cut-safe]: Add the fixture and write the failing tests**

`apps/web/src/test/fixtures/inbox.json`: four of the six seeded emails, exactly as I-1's generator writes them after I-2's precompute (replay backend). Each email kind is covered: Pursue (Hall B, live), not a bid, Clarify (a scan) and Decline.
```json
{
  "mailbox": "bids@meridian-power.example",
  "label": "sandbox (simulated)",
  "notice": "Demo workspace — all companies, people and data are fictional",
  "as_of": 1792132200.0,
  "appetite": {"asset_types": ["datahall", "grid", "solar"], "mw": [2.0, 120.0], "regions": [{"name": "Telangana", "places": ["Telangana", "Hyderabad"]}, {"name": "Andhra Pradesh", "places": ["Andhra Pradesh", "Anantapur", "Visakhapatnam"]}, {"name": "Karnataka", "places": ["Karnataka", "Bengaluru"]}, {"name": "Maharashtra", "places": ["Maharashtra", "Pune", "Mumbai"]}, {"name": "Madhya Pradesh", "places": ["Madhya Pradesh", "Satna"]}], "min_days_to_bid_due": 10, "lead_time_check": true},
  "emails": [
    {
      "id": "em-hall-b",
      "from_name": "Ananya Reddy",
      "from_addr": "ananya.reddy@deccan-compute.example",
      "from_org": "Deccan Compute",
      "to": "bids@meridian-power.example",
      "subject": "Tender: Deccan AI Campus Hall B, electrical and liquid-cooling design-build",
      "received_at": 1792121400.0,
      "body": "Dear Meridian bids team,\n\nDeccan Compute invites your bid for the electrical and liquid-cooling design-build of Data Hall B at our AI campus near Hyderabad, Telangana.\n\nHall B is a twin of Hall A: the attached technical requirements DC-HA-TS-001 Rev 0 apply to Hall B without change, as Addendum 1 confirms. Hall B carries 6.336 MW of IT load in 48 racks.\n\nBids are due by 13 November 2026. Please note the programme clause: all major equipment must be on site no later than 26 weeks from contract award.\n\nRegards,\nAnanya Reddy\nProcurement, Deccan Compute",
      "attachments": [{"id": "att-hall-b-tender", "name": "DC-HA-TS-001 Rev 0 technical requirements.pdf", "url": "/demo/docs/tender-hall-a.pdf", "source": "hall_a/out/tender-hall-a.pdf", "content_type": "application/pdf"}, {"id": "att-hall-b-drawing", "name": "Data hall general arrangement.pdf", "url": "/demo/docs/hall-a-plan.pdf", "source": "hall_a/out/hall-a-plan.pdf", "content_type": "application/pdf"}, {"id": "att-hall-b-addendum", "name": "Addendum 1, Hall B.pdf", "url": "/demo/inbox/hall-b-addendum-1.pdf", "source": "demo_world/out/inbox/hall-b-addendum-1.pdf", "content_type": "application/pdf"}],
      "project_id": "hall-b",
      "live_triage": true,
      "triage": {
        "email_id": "em-hall-b",
        "is_bid": true,
        "summary": "Deccan Compute invites a design-build bid for Data Hall B, a twin of Hall A with 2N power.",
        "attachments": [
          {"attachment_id": "att-hall-b-tender", "name": "DC-HA-TS-001 Rev 0 technical requirements.pdf", "kind": "tender", "scanned": false},
          {"attachment_id": "att-hall-b-drawing", "name": "Data hall general arrangement.pdf", "kind": "drawing", "scanned": false},
          {"attachment_id": "att-hall-b-addendum", "name": "Addendum 1, Hall B.pdf", "kind": "addendum", "scanned": false}
        ],
        "fields": [
          {"key": "client", "label": "Client", "value": "Deccan Compute", "unit": null, "display": "Deccan Compute", "source": "body", "source_label": "Email body", "page": null, "quote": "Deccan Compute invites your bid", "verification": "verified", "bbox": null},
          {"key": "site", "label": "Site", "value": "AI campus near Hyderabad, Telangana", "unit": null, "display": "AI campus near Hyderabad, Telangana", "source": "body", "source_label": "Email body", "page": null, "quote": "at our AI campus near Hyderabad, Telangana", "verification": "verified", "bbox": null},
          {"key": "asset_type", "label": "Asset type", "value": "datahall", "unit": null, "display": "AI data hall", "source": "body", "source_label": "Email body", "page": null, "quote": "liquid-cooling design-build of Data Hall B", "verification": "verified", "bbox": null},
          {"key": "mw", "label": "Load", "value": 6.336, "unit": "MW", "display": "6.34 MW", "source": "att-hall-b-addendum", "source_label": "Addendum 1, Hall B.pdf · p.1", "page": 1, "quote": "Hall B IT load: 6.336 MW", "verification": "verified", "bbox": [86.0, 109.8, 197.2, 119.8]},
          {"key": "redundancy", "label": "Redundancy", "value": "2N", "unit": null, "display": "2N", "source": "att-hall-b-tender", "source_label": "DC-HA-TS-001 Rev 0 technical requirements.pdf · p.4", "page": 4, "quote": "The critical power distribution shall be 2N", "verification": "verified", "bbox": [68.4, 87.4, 250.6, 97.4]},
          {"key": "bid_due", "label": "Bid due", "value": "13 November 2026", "unit": null, "display": "13 Nov 2026", "source": "att-hall-b-addendum", "source_label": "Addendum 1, Hall B.pdf · p.1", "page": 1, "quote": "Bids are due by 13 November 2026", "verification": "verified", "bbox": [86.0, 129.8, 243.3, 139.8]},
          {"key": "lead_time_weeks", "label": "Lead-time limit", "value": 26.0, "unit": "weeks", "display": "26 weeks", "source": "att-hall-b-tender", "source_label": "DC-HA-TS-001 Rev 0 technical requirements.pdf · p.2", "page": 2, "quote": "no later than 26 weeks from contract award", "verification": "verified", "bbox": [68.4, 87.4, 505.8, 111.4]}
        ],
        "crm": {"account": "Deccan Compute", "opportunity_id": "opp-hall-b", "opportunity_name": "Hall B design-build", "stage": "Design in progress", "proposed": false, "proposed_name": null},
        "fit": {
          "verdict": "pursue", "headline": "Pursue: inside our appetite; plan the transformer swap the lead-time limit needs.",
          "reasons": [
            {"rule": "asset_pack", "status": "pass", "text": "AI data hall is one of our asset packs."},
            {"rule": "mw_range", "status": "pass", "text": "6.34 MW is inside our 2–120 MW range."},
            {"rule": "region", "status": "pass", "text": "AI campus near Hyderabad, Telangana is in Telangana, one of our regions."},
            {"rule": "deadline", "status": "pass", "text": "Bid due 13 Nov 2026: 28 days from 16 Oct 2026 (minimum 10)."},
            {"rule": "supply", "status": "pass", "text": "26-week limit; the 2.5 MVA unit TX-2500 is 98 weeks with none in stock; expect an in-stock swap to TX-3150 (3.15 MVA, 6 in stock)."}
          ],
          "supply": {"status": "swap", "text": "26-week limit; the 2.5 MVA unit TX-2500 is 98 weeks with none in stock; expect an in-stock swap to TX-3150 (3.15 MVA, 6 in stock).", "topology": "2N", "mw": 6.336, "lead_limit_weeks": 26.0, "material_id": "TX-2500", "lead_time_weeks": 98, "stock": 0, "swap_to": "TX-3150", "swap_stock": 6}
        },
        "quotes_verified": 7,
        "quotes_total": 7,
        "source": "precomputed",
        "model": "gemini-3.8-flash",
        "triaged_at": 1792132200.0,
        "tokens_in": 14200,
        "tokens_out": 610
      }
    },
    {
      "id": "em-tapti-brochure",
      "from_name": "Tapti Transformers",
      "from_addr": "sales@tapti-transformers.example",
      "from_org": "Tapti Transformers",
      "to": "bids@meridian-power.example",
      "subject": "New: cast-resin transformers ex-stock",
      "received_at": 1792040400.0,
      "body": "Dear partner,\n\nOur cast-resin transformer range is now available ex-stock from our Vadodara works. The brochure is attached.\n\nTapti Transformers sales team",
      "attachments": [{"id": "att-tapti-brochure", "name": "Tapti cast-resin range.pdf", "url": "/demo/inbox/tapti-brochure.pdf", "source": "demo_world/out/inbox/tapti-brochure.pdf", "content_type": "application/pdf"}],
      "project_id": null,
      "live_triage": false,
      "triage": {
        "email_id": "em-tapti-brochure",
        "is_bid": false,
        "summary": "Vendor marketing from Tapti Transformers about its cast-resin range.",
        "attachments": [
          {"attachment_id": "att-tapti-brochure", "name": "Tapti cast-resin range.pdf", "kind": "brochure", "scanned": false}
        ],
        "fields": [],
        "crm": {"account": null, "opportunity_id": null, "opportunity_name": null, "stage": null, "proposed": false, "proposed_name": null},
        "fit": {
          "verdict": null, "headline": "Not a bid: no fit check.",
          "reasons": [
            {"rule": "not_a_bid", "status": "n/a", "text": "Not a bid; no CRM record to update."}
          ],
          "supply": null
        },
        "quotes_verified": 0,
        "quotes_total": 0,
        "source": "precomputed",
        "model": "gemini-3.8-flash",
        "triaged_at": 1792132200.0,
        "tokens_in": 2100,
        "tokens_out": 140
      }
    },
    {
      "id": "em-vindhya-boq",
      "from_name": "Neha Kapoor",
      "from_addr": "neha.kapoor@meridian-power.example",
      "from_org": "Vindhya Steel",
      "to": "bids@meridian-power.example",
      "subject": "FW: Captive power switchyard, BOQ for pricing",
      "received_at": 1791786600.0,
      "body": "Forwarding from Vindhya Steel. Their BOQ only exists as a scan; can we bid?\nNeha\n\n---------- Forwarded message ----------\nFrom: Sanjay Verma <sanjay.verma@vindhya-steel.example>\nSubject: Captive power switchyard, BOQ for pricing\n\nPlease price the attached BOQ for the 33 kV captive power switchyard at our Satna mill, Madhya Pradesh. Bids are due by 30 October 2026.\n\nSanjay Verma\nVindhya Steel",
      "attachments": [{"id": "att-vindhya-boq", "name": "Switchyard BOQ (scan).pdf", "url": "/demo/inbox/vindhya-boq-scan.pdf", "source": "demo_world/out/inbox/vindhya-boq-scan.pdf", "content_type": "application/pdf"}],
      "project_id": null,
      "live_triage": false,
      "triage": {
        "email_id": "em-vindhya-boq",
        "is_bid": true,
        "summary": "Vindhya Steel asks for pricing of a captive power switchyard; its BOQ is a scanned image.",
        "attachments": [
          {"attachment_id": "att-vindhya-boq", "name": "Switchyard BOQ (scan).pdf", "kind": "boq", "scanned": true}
        ],
        "fields": [
          {"key": "client", "label": "Client", "value": "Vindhya Steel", "unit": null, "display": "Vindhya Steel", "source": "body", "source_label": "Email body", "page": null, "quote": "Forwarding from Vindhya Steel", "verification": "verified", "bbox": null},
          {"key": "site", "label": "Site", "value": "Satna mill, Madhya Pradesh", "unit": null, "display": "Satna mill, Madhya Pradesh", "source": "body", "source_label": "Email body", "page": null, "quote": "at our Satna mill, Madhya Pradesh", "verification": "verified", "bbox": null},
          {"key": "asset_type", "label": "Asset type", "value": "grid", "unit": null, "display": "Grid", "source": "body", "source_label": "Email body", "page": null, "quote": "the 33 kV captive power switchyard", "verification": "verified", "bbox": null},
          {"key": "mw", "label": "Load", "value": null, "unit": "MW", "display": "Not verified (scan)", "source": "att-vindhya-boq", "source_label": "Switchyard BOQ (scan).pdf · p.1", "page": 1, "quote": "", "verification": "unverified_scan", "bbox": null},
          {"key": "bid_due", "label": "Bid due", "value": "30 October 2026", "unit": null, "display": "30 Oct 2026", "source": "body", "source_label": "Email body", "page": null, "quote": "Bids are due by 30 October 2026", "verification": "verified", "bbox": null}
        ],
        "crm": {"account": "Vindhya Steel", "opportunity_id": "opp-vindhya-cpp", "opportunity_name": "Captive power switchyard", "stage": "Qualification", "proposed": false, "proposed_name": null},
        "fit": {
          "verdict": "clarify", "headline": "Clarify before bidding: load (MW).",
          "reasons": [
            {"rule": "asset_pack", "status": "pass", "text": "Grid is one of our asset packs."},
            {"rule": "mw_range", "status": "warn", "text": "The load is only on a scanned page (Switchyard BOQ (scan).pdf · p.1) and is not verified; ask for a text copy."},
            {"rule": "region", "status": "pass", "text": "Satna mill, Madhya Pradesh is in Madhya Pradesh, one of our regions."},
            {"rule": "deadline", "status": "pass", "text": "Bid due 30 Oct 2026: 14 days from 16 Oct 2026 (minimum 10)."},
            {"rule": "supply", "status": "n/a", "text": "The day-zero supply check covers AI data halls only."}
          ],
          "supply": {"status": "not_assessed", "text": "The day-zero supply check covers AI data halls only.", "topology": null, "mw": null, "lead_limit_weeks": null, "material_id": null, "lead_time_weeks": null, "stock": null, "swap_to": null, "swap_stock": null}
        },
        "quotes_verified": 4,
        "quotes_total": 5,
        "source": "precomputed",
        "model": "gemini-3.8-flash",
        "triaged_at": 1792132200.0,
        "tokens_in": 2600,
        "tokens_out": 260
      }
    },
    {
      "id": "em-narmada-400kv",
      "from_name": "Rakesh Patel",
      "from_addr": "rakesh.patel@narmada-transmission.example",
      "from_org": "Narmada Transmission",
      "to": "bids@meridian-power.example",
      "subject": "RFQ: 400 kV GIS substation at Bharuch, EPC",
      "received_at": 1791360000.0,
      "body": "Dear Sir or Madam,\n\nNarmada Transmission requests EPC quotations for a new 400 kV GIS substation at Bharuch, Gujarat. The specification is attached. Quotations are due by 20 November 2026.\n\nRakesh Patel\nNarmada Transmission",
      "attachments": [{"id": "att-narmada-spec", "name": "NT-400-BH specification.pdf", "url": "/demo/inbox/narmada-400kv-spec.pdf", "source": "demo_world/out/inbox/narmada-400kv-spec.pdf", "content_type": "application/pdf"}],
      "project_id": null,
      "live_triage": false,
      "triage": {
        "email_id": "em-narmada-400kv",
        "is_bid": true,
        "summary": "Narmada Transmission requests EPC quotations for a GIS substation in Gujarat.",
        "attachments": [
          {"attachment_id": "att-narmada-spec", "name": "NT-400-BH specification.pdf", "kind": "tender", "scanned": false}
        ],
        "fields": [
          {"key": "client", "label": "Client", "value": "Narmada Transmission", "unit": null, "display": "Narmada Transmission", "source": "body", "source_label": "Email body", "page": null, "quote": "Narmada Transmission requests EPC quotations", "verification": "verified", "bbox": null},
          {"key": "site", "label": "Site", "value": "Bharuch, Gujarat", "unit": null, "display": "Bharuch, Gujarat", "source": "body", "source_label": "Email body", "page": null, "quote": "substation at Bharuch, Gujarat", "verification": "verified", "bbox": null},
          {"key": "asset_type", "label": "Asset type", "value": "substation", "unit": null, "display": "Substation", "source": "att-narmada-spec", "source_label": "NT-400-BH specification.pdf · p.1", "page": 1, "quote": "EPC of a new 400/220 kV gas-insulated substation", "verification": "verified", "bbox": [107.7, 89.8, 332.8, 99.8]},
          {"key": "bid_due", "label": "Bid due", "value": "20 November 2026", "unit": null, "display": "20 Nov 2026", "source": "body", "source_label": "Email body", "page": null, "quote": "Quotations are due by 20 November 2026", "verification": "verified", "bbox": null}
        ],
        "crm": {"account": "Narmada Transmission", "opportunity_id": null, "opportunity_name": null, "stage": null, "proposed": true, "proposed_name": "RFQ: 400 kV GIS substation at Bharuch, EPC"},
        "fit": {
          "verdict": "decline", "headline": "Decline: outside our appetite on asset type, region.",
          "reasons": [
            {"rule": "asset_pack", "status": "fail", "text": "Substation is not one of our asset packs (AI data hall, Grid, Solar)."},
            {"rule": "mw_range", "status": "warn", "text": "No load (MW) is stated."},
            {"rule": "region", "status": "fail", "text": "Bharuch, Gujarat is outside our regions (Telangana, Andhra Pradesh, Karnataka, Maharashtra, Madhya Pradesh)."},
            {"rule": "deadline", "status": "pass", "text": "Bid due 20 Nov 2026: 35 days from 16 Oct 2026 (minimum 10)."},
            {"rule": "supply", "status": "n/a", "text": "The day-zero supply check covers AI data halls only."}
          ],
          "supply": {"status": "not_assessed", "text": "The day-zero supply check covers AI data halls only.", "topology": null, "mw": null, "lead_limit_weeks": null, "material_id": null, "lead_time_weeks": null, "stock": null, "swap_to": null, "swap_stock": null}
        },
        "quotes_verified": 4,
        "quotes_total": 4,
        "source": "precomputed",
        "model": "gemini-3.8-flash",
        "triaged_at": 1792132200.0,
        "tokens_in": 2400,
        "tokens_out": 230
      }
    }
  ]
}
```

`apps/web/src/test/fixtures/index.ts`:
- Add `InboxSnapshot` to the type import.
- Add `import inbox from './inbox.json'`.
- Append:
```ts
export function fixtureInbox(): InboxSnapshot {
  return structuredClone(inbox) as unknown as InboxSnapshot
}
```

`apps/web/src/test/render.tsx`:
- Add `import inbox from './fixtures/inbox.json'`.
- In `fakeApi`'s `base`, after `fileBlob: vi.fn(offline),`, add:
```ts
    inbox: vi.fn(offline),
    triage: vi.fn(offline),
    pursue: vi.fn(offline),
```
- In `STATIC_FILES`, after the integrations entry, add `'/demo/inbox.json': inbox,`.

`apps/web/src/inbox/InboxPage.test.tsx`:
```tsx
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { vi } from 'vitest'
import { useWorldStore } from '@/data/useWorld'
import type { PursueResult } from '@/lib/types'
import { fixtureInbox } from '@/test/fixtures'
import { fakeApi, fakeServices, renderWithProviders } from '@/test/render'
import { InboxPage } from './InboxPage'
import { resetInboxStore } from './useInbox'

beforeEach(() => {
  useWorldStore.setState({ world: null, error: null, loading: false })
  resetInboxStore()
})

function inboxAt(route: string, services = fakeServices()) {
  return renderWithProviders(
    <Routes>
      <Route path="/app/inbox" element={<InboxPage />} />
      <Route path="/app/inbox/:emailId" element={<InboxPage />} />
    </Routes>,
    { route, services },
  )
}

const PURSUED: PursueResult = {
  email_id: 'em-hall-b',
  project_id: 'hall-b',
  project_name: null,
  project_created: false,
  opportunity_id: 'opp-hall-b',
  opportunity_name: 'Hall B design-build',
  stage: 'Qualification',
  previous_stage: 'Design in progress',
  opportunity_created: false,
  open: '/app/p/hall-b',
}

test('static first: the list renders from /demo/inbox.json, newest first, verdicts as icon + text', async () => {
  inboxAt('/app/inbox')
  const list = await screen.findByRole('list', { name: 'Emails' })
  const rows = within(list).getAllByRole('link')
  expect(rows.map((r) => r.getAttribute('href'))).toEqual([
    '/app/inbox/em-hall-b',
    '/app/inbox/em-tapti-brochure',
    '/app/inbox/em-vindhya-boq',
    '/app/inbox/em-narmada-400kv',
  ])
  expect(['Pursue', 'Not a bid', 'Clarify', 'Decline'].map((v, i) => within(rows[i]).getByText(v))).toHaveLength(4)
  expect(within(rows[0]).getByText('New')).toBeInTheDocument()
  expect(screen.getByText('Recorded triage (static)')).toBeInTheDocument()
  expect(screen.getByText('bids@meridian-power.example')).toBeInTheDocument()
  expect(screen.getByText(/Appetite: AI data halls, grid, solar · 2–120 MW/)).toBeInTheDocument()
  expect(screen.getByText('Select an email')).toBeInTheDocument()
})

test('with the API up, the live inbox (visitor overlay) replaces the static one', async () => {
  const live = fixtureInbox()
  live.emails[0] = { ...live.emails[0], status: 'pursued', pursue: PURSUED }
  inboxAt('/app/inbox', fakeServices({ api: fakeApi({ inbox: vi.fn(async () => live) }) }))
  expect(await screen.findByText('Live · your workspace')).toBeInTheDocument()
  expect(within(screen.getByRole('list', { name: 'Emails' })).getByText('Pursued')).toBeInTheDocument()
})

test('Hall B detail: attachment chips by class, CRM link, verified fields, fit card with the supply line', async () => {
  inboxAt('/app/inbox/em-hall-b')
  const chips = await screen.findByRole('list', { name: 'Attachments' })
  const links = within(chips).getAllByRole('link')
  expect(links.map((a) => a.textContent)).toEqual([
    'TenderDC-HA-TS-001 Rev 0 technical requirements.pdf',
    'DrawingData hall general arrangement.pdf',
    'AddendumAddendum 1, Hall B.pdf',
  ])
  expect(links[0]).toHaveAttribute('href', '/demo/docs/tender-hall-a.pdf')
  expect(screen.getByRole('link', { name: 'Deccan Compute · Hall B design-build (Design in progress)' })).toHaveAttribute(
    'href',
    '/app/integrations',
  )
  expect(screen.getByText(/recorded triage · 7\/7 quotes verified/)).toBeInTheDocument()
  const fields = screen.getByRole('table', { name: 'Extracted fields' })
  expect(within(fields).getAllByText('quote verified')).toHaveLength(7)
  expect(within(within(fields).getByRole('row', { name: /Load/ })).getByText('6.34 MW')).toBeInTheDocument()
  const fit = screen.getByRole('region', { name: 'Fit verdict' })
  expect(within(fit).getByText('Pursue')).toBeInTheDocument()
  expect(within(fit).getAllByText('Pass')).toHaveLength(5)
  expect(within(fit).getByText(/expect an in-stock swap to TX-3150 \(3\.15 MVA, 6 in stock\)/)).toBeInTheDocument()
})

test('a scanned BOQ is marked unverified (scan); only the Hall B email offers live triage', async () => {
  inboxAt('/app/inbox/em-vindhya-boq')
  const fields = await screen.findByRole('table', { name: 'Extracted fields' })
  const load = within(fields).getByRole('row', { name: /Load/ })
  expect(within(load).getByText('unverified (scan)')).toBeInTheDocument()
  expect(within(load).getByText('Not verified (scan)')).toBeInTheDocument()
  expect(within(screen.getByRole('list', { name: 'Attachments' })).getByText('scan')).toBeInTheDocument()
  expect(within(screen.getByRole('region', { name: 'Fit verdict' })).getByText('Clarify')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /triage live/i })).not.toBeInTheDocument()
})

test('declined and not-a-bid emails offer no Pursue', async () => {
  inboxAt('/app/inbox/em-narmada-400kv')
  expect(await screen.findByText('Declined by the fit rules.')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Pursue' })).not.toBeInTheDocument()
})

test('Pursue with the API up shows the CRM move and opens Hall B intake', async () => {
  const user = userEvent.setup()
  const api = fakeApi({ pursue: vi.fn(async () => PURSUED) })
  inboxAt('/app/inbox/em-hall-b', fakeServices({ api }))
  await user.click(await screen.findByRole('button', { name: 'Pursue' }))
  const card = await screen.findByRole('region', { name: 'Pursued' })
  expect(within(card).getByText(/Hall B design-build → Qualification \(was Design in progress\)/)).toBeInTheDocument()
  expect(within(card).getByRole('link', { name: /and run intake/ })).toHaveAttribute('href', '/app/p/hall-b')
  expect(api.pursue).toHaveBeenCalledWith('em-hall-b')
})

test('Pursue with the backend down still opens Hall B (static fallback)', async () => {
  const user = userEvent.setup()
  inboxAt('/app/inbox/em-hall-b')
  await user.click(await screen.findByRole('button', { name: 'Pursue' }))
  expect(await screen.findByRole('status')).toHaveTextContent('the CRM was not updated')
  expect(screen.getByRole('link', { name: /^Open .*hall.b/i })).toHaveAttribute('href', '/app/p/hall-b')
})

test('keyboard: the email rows are reachable with Tab and open with Enter; opening marks the email read', async () => {
  const user = userEvent.setup()
  inboxAt('/app/inbox')
  const first = within(await screen.findByRole('list', { name: 'Emails' })).getAllByRole('link')[0]
  first.focus()
  expect(first).toHaveFocus()
  await user.keyboard('{Enter}')
  expect(await screen.findByRole('heading', { level: 2 })).toHaveTextContent('Tender: Deccan AI Campus Hall B')
  expect(within(screen.getAllByRole('link', { name: /Deccan Compute/ })[0]).queryByText('New')).not.toBeInTheDocument()
  expect(JSON.parse(localStorage.getItem('kirchhoff.inbox.read') ?? '[]')).toEqual(['em-hall-b'])
})
```

`apps/web/src/pages/Dashboard.test.tsx`:
- After `import { useWorldStore } from '@/data/useWorld'`, add:
```ts
import { resetInboxStore } from '@/inbox/useInbox'
import { INBOX_TOUR_STEP } from '@/inbox/inboxTour'
```
- Replace the `beforeEach` line with:
```ts
beforeEach(() => {
  useWorldStore.setState({ world: null, error: null, loading: false })
  resetInboxStore()
})
```
- Append:
```tsx

test('the dashboard links the bids inbox with its count of new emails (tour hook, not a tour step)', async () => {
  localStorage.setItem('kirchhoff.welcomed', 'true')
  localStorage.setItem('kirchhoff.inbox.read', JSON.stringify(['em-hall-b']))
  shellAt('/app')
  const entry = await screen.findByRole('link', { name: 'Bids inbox · 3 new' })
  expect(entry).toHaveAttribute('href', '/app/inbox')
  expect(entry).toHaveAttribute('data-tour', 'inbox')
  expect(document.querySelector(INBOX_TOUR_STEP.target)).toBe(entry)
  expect(screen.getByRole('navigation', { name: 'Main' })).toHaveTextContent('Bids inbox')
})
```

Append to `apps/web/src/services/apiClient.test.ts`:
```ts

test('inbox calls hit the inbox routes; inbox error codes read as sentences', async () => {
  const { calls, fetcher } = recorder(json({ email_id: 'em-hall-b' }))
  const api = httpApiClient(fetcher)
  await api.inbox()
  await api.triage('em-hall-b')
  await api.pursue('em-hall-b')
  expect(calls.map((c) => [c.path, c.init?.method ?? 'GET'])).toEqual([
    ['/api/inbox', 'GET'],
    ['/api/inbox/em-hall-b/triage', 'POST'],
    ['/api/inbox/em-hall-b/pursue', 'POST'],
  ])
  expect(describeApiError(new ApiError(409, 'precomputed'))).toBe(
    'Only the Hall B email can be triaged live; this one shows the recorded triage.',
  )
})
```

- [ ] **Step 2 [cut-safe]: Run to verify failure**

Run: `cd apps/web && npx vitest run src/inbox src/pages/Dashboard.test.tsx src/services/apiClient.test.ts`
Expected: FAIL. `InboxPage.test.tsx` fails with `Failed to resolve import "./InboxPage"`, `Dashboard.test.tsx` with `Failed to resolve import "@/inbox/useInbox"`, and the apiClient test with `api.inbox is not a function`.

- [ ] **Step 3 [cut-safe]: Types, the static loader and the API client**

Append to `apps/web/src/lib/types.ts`:
```ts
/** Bids inbox (spec §20): `public/demo/inbox.json` (WS4 I-1) and `GET /api/inbox` (WS2 I-2). Hand-typed like `World`. */
export type AttachmentKind = 'tender' | 'drawing' | 'addendum' | 'boq' | 'brochure' | 'other'
export type InboxFieldKey = 'client' | 'site' | 'asset_type' | 'mw' | 'redundancy' | 'bid_due' | 'lead_time_weeks'
export type Verification = 'verified' | 'unverified_scan' | 'unverified'
export type Verdict = 'pursue' | 'clarify' | 'decline'
export interface InboxAttachment {
  id: string
  name: string
  url: string // /demo/docs/{file} or /demo/inbox/{file}
  source: string
  content_type: string
}
export interface AttachmentTriage {
  attachment_id: string
  name: string
  kind: AttachmentKind
  scanned: boolean
}
export interface ExtractedField {
  key: InboxFieldKey
  label: string
  value: string | number | null // null when withheld (unverified)
  unit: string | null
  display: string // formatted by WS2 from the verified value
  source: string
  source_label: string
  page: number | null
  quote: string // the verified verbatim quote; "" when unverified
  verification: Verification
  bbox: number[] | null
}
export interface CrmLink {
  account: string | null
  opportunity_id: string | null
  opportunity_name: string | null
  stage: string | null
  proposed: boolean
  proposed_name: string | null
}
export interface FitReason {
  rule: 'asset_pack' | 'mw_range' | 'region' | 'deadline' | 'supply' | 'not_a_bid'
  status: FindingStatus
  text: string
}
export interface SupplyCheck {
  status: 'ok' | 'swap' | 'risk' | 'not_assessed'
  text: string
  topology: string | null
  mw: number | null
  lead_limit_weeks: number | null
  material_id: string | null
  lead_time_weeks: number | null
  stock: number | null
  swap_to: string | null
  swap_stock: number | null
}
export interface FitResult {
  verdict: Verdict | null // null: not a bid
  headline: string
  reasons: FitReason[]
  supply: SupplyCheck | null
}
export interface TriageResult {
  email_id: string
  is_bid: boolean
  summary: string
  attachments: AttachmentTriage[]
  fields: ExtractedField[]
  crm: CrmLink
  fit: FitResult
  quotes_verified: number
  quotes_total: number
  source: 'live' | 'precomputed'
  model: string
  triaged_at: number
  tokens_in: number
  tokens_out: number
}
export interface PursueResult {
  email_id: string
  project_id: string
  project_name: string | null // null for an existing world project (name it from world.json)
  project_created: boolean
  opportunity_id: string
  opportunity_name: string
  stage: string
  previous_stage: string | null
  opportunity_created: boolean
  open: string | null // app route to open next (Hall B's intake)
}
export interface InboxEmail {
  id: string
  from_name: string
  from_addr: string
  from_org: string
  to: string
  subject: string
  received_at: number
  body: string
  attachments: InboxAttachment[]
  project_id: string | null
  live_triage: boolean
  triage: TriageResult | null
  status?: 'new' | 'triaged' | 'pursued' // live API only
  pursue?: PursueResult | null // live API only
}
export interface InboxAppetite {
  asset_types: AssetPack[]
  mw: [number, number]
  regions: { name: string; places: string[] }[]
  min_days_to_bid_due: number
  lead_time_check: boolean
}
export interface InboxSnapshot {
  mailbox: string
  label: string
  notice: string
  as_of: number
  appetite: InboxAppetite
  emails: InboxEmail[] // newest first
}
```

`apps/web/src/data/staticData.ts`:
- Add `type InboxSnapshot` to the `@/lib/types` import.
- Insert above `docUrl`:
```ts
/** The bids inbox with its recorded triage (spec §20; WS4 generates it). */
export async function loadInboxSnapshot(get: JsonFetch = fetchJson): Promise<InboxSnapshot> {
  return (await get('/demo/inbox.json')) as InboxSnapshot
}
```

`apps/web/src/services/apiClient.ts`:
- Add `InboxSnapshot`, `PursueResult` and `TriageResult` to the type import.
- Append to `interface ApiClient`:
```ts
  inbox(): Promise<InboxSnapshot>
  triage(emailId: string): Promise<TriageResult>
  pursue(emailId: string): Promise<PursueResult>
```
- Add to `DETAIL_TEXT`, after `timeout`:
```ts
  inbox_unavailable: 'The live inbox is unavailable; the recorded triage is shown.',
  email_not_found: 'That email is not in the bids inbox.',
  precomputed: 'Only the Hall B email can be triaged live; this one shows the recorded triage.',
  triage_rate_limit: 'You have reached the hourly limit for live triage; the recorded triage is shown.',
  triage_failed: 'The Inbox agent could not finish this triage.',
  not_triaged: 'Triage this email before pursuing it.',
  cannot_pursue: 'Only bids with a Pursue or Clarify verdict in one of our asset packs can be pursued.',
  enterprise_unavailable: 'The CRM sandbox is not answering right now.',
```
- In `httpApiClient`'s returned object, after `fileBlob`, add:
```ts
    inbox: () => call('/api/inbox'),
    triage: (emailId) => post(`/api/inbox/${encodeURIComponent(emailId)}/triage`),
    pursue: (emailId) => post(`/api/inbox/${encodeURIComponent(emailId)}/pursue`),
```
(`triage` is declared here so the client matches the API table. Nothing calls it until the [cut] Step 11.)

- [ ] **Step 4 [cut-safe]: The inbox store, labels and the tour hook**

`apps/web/src/inbox/useInbox.ts`:
```ts
// Bids inbox data (spec §20). Static first: /demo/inbox.json renders with the backend down (spec §11). Live
// second: GET /api/inbox adds the visitor's overlay (triage, Pursue) and replaces the static data when it answers.
// "New" is per browser: ids opened here are kept in localStorage `kirchhoff.inbox.read` (addendum ruling B9).
import { useEffect } from 'react'
import { create } from 'zustand'
import { loadInboxSnapshot } from '@/data/staticData'
import { readJson, writeJson } from '@/lib/storage'
import type { InboxEmail, InboxSnapshot, PursueResult, TriageResult } from '@/lib/types'
import { useServices } from '@/services/services'

const READ_KEY = 'inbox.read'

export interface InboxState {
  data: InboxSnapshot | null
  live: boolean
  loading: boolean
  error: string | null
  read: string[]
}

export const useInboxStore = create<InboxState>()(() => ({ data: null, live: false, loading: false, error: null, read: [] }))

export function resetInboxStore(): void {
  useInboxStore.setState({ data: null, live: false, loading: false, error: null, read: readJson<string[]>(READ_KEY, []) })
}

export function useInbox(): InboxState {
  const { api, getJson } = useServices()
  const state = useInboxStore()
  useEffect(() => {
    const s = useInboxStore.getState()
    if (s.data || s.loading) return
    useInboxStore.setState({ loading: true, read: readJson<string[]>(READ_KEY, []) })
    const failed = { static: null as string | null, live: false }
    const settle = () => {
      if (failed.static && failed.live && !useInboxStore.getState().data)
        useInboxStore.setState({ loading: false, error: failed.static })
    }
    loadInboxSnapshot(getJson)
      .then((data) => {
        if (!useInboxStore.getState().live) useInboxStore.setState({ data, loading: false, error: null })
      })
      .catch((e: Error) => {
        failed.static = e.message
        settle()
      })
    api
      .inbox()
      .then((data) => useInboxStore.setState({ data, live: true, loading: false, error: null }))
      .catch(() => {
        failed.live = true
        settle()
      })
  }, [api, getJson])
  return state
}

export function markRead(id: string): void {
  const { read } = useInboxStore.getState()
  if (read.includes(id)) return
  const next = [...read, id]
  writeJson(READ_KEY, next)
  useInboxStore.setState({ read: next })
}

export function unreadCount(data: InboxSnapshot | null, read: string[]): number {
  return data ? data.emails.filter((e) => !read.includes(e.id)).length : 0
}

function patchEmail(id: string, patch: (e: InboxEmail) => Partial<InboxEmail>): void {
  const { data } = useInboxStore.getState()
  if (!data) return
  useInboxStore.setState({ data: { ...data, emails: data.emails.map((e) => (e.id === id ? { ...e, ...patch(e) } : e)) } })
}

export function applyTriage(id: string, triage: TriageResult): void {
  patchEmail(id, (e) => ({ triage, status: e.status === 'pursued' ? 'pursued' : 'triaged' }))
}

export function applyPursue(id: string, pursue: PursueResult): void {
  patchEmail(id, () => ({ pursue, status: 'pursued' }))
}
```

`apps/web/src/inbox/inboxMeta.ts`:
```ts
// Labels and icons for the bids inbox. Status is always icon + text; colour is a third, redundant cue (spec §12).
import { CircleCheck, CircleMinus, CircleQuestionMark, CircleX, ScanLine, TriangleAlert, type LucideIcon } from 'lucide-react'
import type { AssetPack, AttachmentKind, InboxAppetite, TriageResult, Verification } from '@/lib/types'

interface Meta {
  label: string
  icon: LucideIcon
  cls: string
}

export const VERDICT_META: Record<'pursue' | 'clarify' | 'decline' | 'none', Meta> = {
  pursue: { label: 'Pursue', icon: CircleCheck, cls: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300' },
  clarify: { label: 'Clarify', icon: CircleQuestionMark, cls: 'border-amber-400/50 bg-amber-500/10 text-amber-300' },
  decline: { label: 'Decline', icon: CircleX, cls: 'border-rose-500/50 bg-rose-500/10 text-rose-300' },
  none: { label: 'Not a bid', icon: CircleMinus, cls: 'border-zinc-600 bg-zinc-500/10 text-zinc-300' },
}

export function verdictMeta(t: TriageResult): Meta {
  return VERDICT_META[t.fit.verdict ?? 'none']
}

export const VERIFICATION_META: Record<Verification, Meta> = {
  verified: { label: 'quote verified', icon: CircleCheck, cls: 'text-emerald-400' },
  unverified_scan: { label: 'unverified (scan)', icon: ScanLine, cls: 'text-amber-300' },
  unverified: { label: 'not verified', icon: TriangleAlert, cls: 'text-amber-300' },
}

export const KIND_ORDER: AttachmentKind[] = ['tender', 'drawing', 'addendum', 'boq', 'brochure', 'other']
export const KIND_LABEL: Record<AttachmentKind, string> = {
  tender: 'Tender',
  drawing: 'Drawing',
  addendum: 'Addendum',
  boq: 'BOQ',
  brochure: 'Brochure',
  other: 'Other',
}

const PACK_LABEL: Record<AssetPack, string> = { datahall: 'AI data halls', grid: 'grid', solar: 'solar' }

/** One line describing the fit rules. Every number comes from the inbox data (world.yaml). */
export function appetiteLine(a: InboxAppetite): string {
  const packs = a.asset_types.map((p) => PACK_LABEL[p]).join(', ')
  const regions = a.regions.map((r) => r.name).join(', ')
  return `Appetite: ${packs} · ${a.mw[0]}–${a.mw[1]} MW · ${regions} · at least ${a.min_days_to_bid_due} days to the bid deadline`
}
```

`apps/web/src/inbox/inboxTour.ts`:
```ts
// Optional tour hook (spec §20). It is NOT in TOUR_STEPS: the 7-step tour (spec §13.5) keeps its order. It has the
// shape of P3 Task 14's TourStep, so an extras tour or a hint can use it; its target is the dashboard's inbox entry.
export const INBOX_TOUR_STEP = {
  id: 'inbox',
  route: () => '/app',
  target: '[data-tour="inbox"]',
  title: () => 'Bids start in the inbox',
  body: 'Kirchhoff triages every email to bids@: it classifies the attachments, verifies the quotes, checks fit and supply, and opens the project.',
}
```

- [ ] **Step 5 [cut-safe]: The detail (with the static Pursue fallback) and the page**

`apps/web/src/inbox/EmailDetail.tsx`:
```tsx
// One email of the bids inbox (spec §20): header, attachment chips by class, body, the Inbox agent's triage (CRM
// link, extracted fields with their verification marks), the deterministic fit card with the day-zero supply line,
// and Pursue. The live Triage button (Hall B only) is added in a [cut] step.
import { cn } from 'cn'
import { ArrowLeft, ArrowRight, CircleCheck, Handshake, LoaderCircle, Paperclip, ScanLine, Truck } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { SandboxLabel } from '@/components/Labels'
import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { useWorldProject } from '@/data/useWorld'
import { fmtTs } from '@/lib/format'
import type { CrmLink, InboxEmail, PursueResult, TriageResult } from '@/lib/types'
import { describeApiError } from '@/services/apiClient'
import { useServices } from '@/services/services'
import { KIND_LABEL, KIND_ORDER, VERIFICATION_META, verdictMeta } from './inboxMeta'
import { applyPursue } from './useInbox'

const PACKS = ['datahall', 'grid', 'solar']

export function VerdictBadge({ triage, className }: { triage: TriageResult; className?: string }) {
  const m = verdictMeta(triage)
  const Icon = m.icon
  return (
    <span className={cn('inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs font-medium', m.cls, className)}>
      <Icon aria-hidden className="size-3.5" />
      {m.label}
    </span>
  )
}

function AttachmentChips({ email, triage }: { email: InboxEmail; triage: TriageResult | null }) {
  if (!email.attachments.length) return <p className="text-xs text-zinc-500">No attachments.</p>
  const byId = new Map((triage?.attachments ?? []).map((a) => [a.attachment_id, a]))
  const rank = (id: string) => KIND_ORDER.indexOf(byId.get(id)?.kind ?? 'other')
  const sorted = [...email.attachments].sort((a, b) => rank(a.id) - rank(b.id))
  return (
    <ul aria-label="Attachments" className="flex flex-wrap gap-2">
      {sorted.map((a) => {
        const t = byId.get(a.id)
        return (
          <li key={a.id}>
            <a
              href={a.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded border border-zinc-700 bg-zinc-800/60 px-2 py-1 text-xs text-zinc-200 hover:border-zinc-500 focus-visible:outline-2 focus-visible:outline-sky-400"
            >
              <Paperclip aria-hidden className="size-3.5" />
              <span className="font-medium">{t ? KIND_LABEL[t.kind] : 'Unclassified'}</span>
              <span className="text-zinc-400">{a.name}</span>
              {t?.scanned && (
                <span className="inline-flex items-center gap-0.5 text-amber-300">
                  <ScanLine aria-hidden className="size-3" />
                  scan
                </span>
              )}
            </a>
          </li>
        )
      })}
    </ul>
  )
}

function crmText(crm: CrmLink): string {
  if (crm.opportunity_id) return `${crm.account} · ${crm.opportunity_name}${crm.stage ? ` (${crm.stage})` : ''}`
  if (crm.proposed) return `New opportunity proposed for ${crm.account}: ${crm.proposed_name}`
  return crm.account ? `${crm.account}, no matching opportunity` : 'No CRM record'
}

function CrmLine({ crm }: { crm: CrmLink }) {
  return (
    <p className="flex flex-wrap items-center gap-2 text-sm">
      <Handshake aria-hidden className="size-4 text-zinc-400" />
      <span className="text-zinc-400">CRM:</span>
      <Link to="/app/integrations" className="text-sky-300 underline-offset-2 hover:underline">
        {crmText(crm)}
      </Link>
      <SandboxLabel />
    </p>
  )
}

function FieldsTable({ triage }: { triage: TriageResult }) {
  return (
    <table aria-label="Extracted fields" className="w-full text-left text-sm">
      <thead className="text-xs text-zinc-400">
        <tr>
          <th className="py-1 pr-3 font-medium">Field</th>
          <th className="py-1 pr-3 font-medium">Value</th>
          <th className="py-1 pr-3 font-medium">Check</th>
          <th className="py-1 font-medium">Source</th>
        </tr>
      </thead>
      <tbody>
        {triage.fields.map((f) => {
          const m = VERIFICATION_META[f.verification]
          const Icon = m.icon
          return (
            <tr key={f.key} className="border-t border-zinc-800 align-top">
              <th scope="row" className="py-1.5 pr-3 font-normal text-zinc-400">
                {f.label}
              </th>
              <td className="py-1.5 pr-3 font-mono tabular-nums text-zinc-100">{f.display}</td>
              <td className="py-1.5 pr-3">
                <span className={cn('inline-flex items-center gap-1 text-xs', m.cls)}>
                  <Icon aria-hidden className="size-3.5" />
                  {m.label}
                </span>
              </td>
              <td className="py-1.5 text-xs text-zinc-400">
                {f.source_label}
                {f.quote && <q className="mt-0.5 block text-zinc-300">{f.quote}</q>}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

function FitCard({ triage }: { triage: TriageResult }) {
  return (
    <section aria-label="Fit verdict" className="flex flex-col gap-2 rounded-lg border bg-card p-4">
      <div className="flex flex-wrap items-center gap-2">
        <VerdictBadge triage={triage} />
        <p className="text-sm font-medium text-zinc-100">{triage.fit.headline}</p>
      </div>
      <ul className="flex flex-col gap-1.5 text-sm">
        {triage.fit.reasons.map((r) => (
          <li
            key={r.rule}
            className={cn('flex items-start gap-2', r.rule === 'supply' && 'rounded border border-sky-500/30 bg-sky-500/5 p-2')}
          >
            <StatusBadge status={r.status} compact className="shrink-0" />
            {r.rule === 'supply' && <Truck aria-hidden className="mt-0.5 size-4 shrink-0 text-sky-300" />}
            <span className="text-zinc-300">
              {r.rule === 'supply' && <span className="font-medium text-zinc-100">Day-zero supply: </span>}
              {r.text}
            </span>
          </li>
        ))}
      </ul>
      <p className="text-[11px] text-zinc-500">Deterministic rules from the firm's appetite, the engine and the ERP; no AI in the verdict.</p>
    </section>
  )
}

function PursueCard({ result, name }: { result: PursueResult; name: string }) {
  const was = result.previous_stage && result.previous_stage !== result.stage ? ` (was ${result.previous_stage})` : ''
  return (
    <section aria-label="Pursued" className="flex flex-col gap-1.5 rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3 text-sm">
      <p className="flex items-center gap-1.5 font-medium text-emerald-300">
        <CircleCheck aria-hidden className="size-4" />
        Pursued
      </p>
      <p className="flex flex-wrap items-center gap-2 text-zinc-300">
        CRM: {result.opportunity_name} → {result.stage}
        {was}
        {result.opportunity_created ? ' · new opportunity' : ''}
        <SandboxLabel />
      </p>
      <p className="text-zinc-300">
        {result.project_created ? `Project created in your workspace: ${result.project_name} (draft)` : `Project: ${name}`}
      </p>
      {result.open && (
        <Button asChild size="sm" className="self-start">
          <Link to={result.open}>
            Open {name} and run intake <ArrowRight aria-hidden />
          </Link>
        </Button>
      )}
    </section>
  )
}

function PursueAction({ email, triage }: { email: InboxEmail; triage: TriageResult }) {
  const { api } = useServices()
  const world = useWorldProject(email.project_id ?? undefined)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const name = world?.name ?? email.project_id ?? ''
  if (email.pursue) return <PursueCard result={email.pursue} name={email.pursue.project_name ?? name} />
  const asset = triage.fields.find((f) => f.key === 'asset_type' && f.verification === 'verified')
  const pursuable = (triage.fit.verdict === 'pursue' || triage.fit.verdict === 'clarify') && PACKS.includes(String(asset?.value))
  if (!pursuable)
    return (
      <p className="text-xs text-zinc-500">
        {triage.fit.verdict === null ? 'Not a bid: nothing to pursue.' : triage.fit.verdict === 'decline' ? 'Declined by the fit rules.' : 'Pursue needs a verified asset type in one of our packs.'}
      </p>
    )
  const pursue = async () => {
    setBusy(true)
    setNote(null)
    try {
      applyPursue(email.id, await api.pursue(email.id))
    } catch (e) {
      setNote(describeApiError(e))
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="flex flex-col gap-2">
      <Button onClick={pursue} disabled={busy} className="self-start">
        {busy ? <LoaderCircle aria-hidden className="animate-spin motion-reduce:animate-none" /> : <Handshake aria-hidden />}
        Pursue
      </Button>
      {note && (
        <p role="status" className="text-xs text-amber-200">
          {note}
          {email.project_id ? ' You can still open the project; the CRM was not updated.' : ''}
        </p>
      )}
      {note && email.project_id && (
        <Link to={`/app/p/${email.project_id}`} className="inline-flex items-center gap-1 text-sm text-sky-300 hover:underline">
          Open {name} <ArrowRight aria-hidden className="size-3.5" />
        </Link>
      )}
    </div>
  )
}

export function EmailDetail({ email }: { email: InboxEmail }) {
  const triage = email.triage
  return (
    <article aria-labelledby={`subject-${email.id}`} className="flex flex-col gap-5 p-6">
      <Link to="/app/inbox" className="inline-flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-200 lg:hidden">
        <ArrowLeft aria-hidden className="size-3.5" /> All emails
      </Link>
      <header className="flex flex-col gap-1">
        <h2 id={`subject-${email.id}`} className="text-base font-semibold text-zinc-100">
          {email.subject}
        </h2>
        <p className="text-sm text-zinc-300">
          {email.from_name} &lt;{email.from_addr}&gt; · {email.from_org}
        </p>
        <p className="text-xs text-zinc-500">
          To {email.to} · {fmtTs(email.received_at)}
        </p>
      </header>
      <AttachmentChips email={email} triage={triage} />
      <div className="whitespace-pre-wrap rounded-lg border bg-zinc-900/50 p-4 text-sm text-zinc-300">{email.body}</div>
      {triage ? (
        <>
          <section aria-label="Triage" className="flex flex-col gap-3">
            <p className="text-xs text-zinc-400">
              Inbox agent · {triage.source === 'live' ? 'live triage' : 'recorded triage'} · {triage.quotes_verified}/
              {triage.quotes_total} quotes verified
            </p>
            <p className="text-sm text-zinc-200">{triage.summary}</p>
            <CrmLine crm={triage.crm} />
            {triage.fields.length > 0 && <FieldsTable triage={triage} />}
          </section>
          <FitCard triage={triage} />
        </>
      ) : (
        <p className="text-sm text-zinc-400">Not triaged yet. The recorded triage arrives with the golden capture.</p>
      )}
      <div className="flex flex-wrap items-start gap-6">
        {triage && <PursueAction email={email} triage={triage} />}
      </div>
    </article>
  )
}
```

`apps/web/src/inbox/InboxPage.tsx`:
```tsx
// Bids inbox (spec §20) at /app/inbox and /app/inbox/:emailId: the email list and one email's detail. Static first
// (/demo/inbox.json), live second (GET /api/inbox). Keyboard: every row is a link; the detail's controls are buttons.
import { cn } from 'cn'
import { Handshake, Inbox, Mail, Paperclip } from 'lucide-react'
import { useEffect } from 'react'
import { Link, useParams } from 'react-router'
import { EmptyState, SandboxLabel } from '@/components/Labels'
import { fmtRelative } from '@/lib/format'
import type { InboxEmail } from '@/lib/types'
import { EmailDetail, VerdictBadge } from './EmailDetail'
import { appetiteLine } from './inboxMeta'
import { markRead, useInbox } from './useInbox'

function EmailRow({ email, unread, active }: { email: InboxEmail; unread: boolean; active: boolean }) {
  return (
    <li className={cn('border-b', active && 'bg-accent')}>
      <Link
        to={`/app/inbox/${email.id}`}
        aria-current={active ? 'true' : undefined}
        className="flex flex-col gap-1 px-4 py-3 hover:bg-zinc-800/50 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-sky-400"
      >
        <span className="flex items-center gap-2 text-sm">
          {unread && (
            <span className="inline-flex items-center gap-1 rounded bg-sky-500/15 px-1.5 text-[11px] font-medium text-sky-200">
              <Mail aria-hidden className="size-3" />
              New
            </span>
          )}
          <span className={cn('truncate', unread ? 'font-semibold text-zinc-100' : 'text-zinc-300')}>{email.from_org}</span>
          <span className="ml-auto shrink-0 text-xs text-zinc-500">{fmtRelative(email.received_at)}</span>
        </span>
        <span className="truncate text-sm text-zinc-300">{email.subject}</span>
        <span className="flex items-center gap-2 text-xs text-zinc-400">
          {email.triage ? <VerdictBadge triage={email.triage} /> : <span>Not triaged yet</span>}
          {email.attachments.length > 0 && (
            <span className="inline-flex items-center gap-1">
              <Paperclip aria-hidden className="size-3" />
              {email.attachments.length}
            </span>
          )}
          {email.status === 'pursued' && (
            <span className="inline-flex items-center gap-1 text-emerald-300">
              <Handshake aria-hidden className="size-3" />
              Pursued
            </span>
          )}
        </span>
      </Link>
    </li>
  )
}

export function InboxPage() {
  const { emailId } = useParams()
  const { data, live, error, read } = useInbox()
  useEffect(() => {
    if (emailId) markRead(emailId)
  }, [emailId])
  if (error) return <EmptyState title="Could not load the bids inbox">{error}</EmptyState>
  if (!data) return <EmptyState title="Loading the bids inbox…" />
  const selected = data.emails.find((e) => e.id === emailId) ?? null
  return (
    <div className="mx-auto grid h-full max-w-7xl grid-cols-1 lg:grid-cols-[24rem_1fr]">
      <section aria-labelledby="inbox-h" className={cn('flex min-h-0 flex-col border-r', emailId && 'hidden lg:flex')}>
        <header className="flex flex-col gap-1 border-b p-4">
          <div className="flex items-center gap-2">
            <Inbox aria-hidden className="size-4 text-sky-300" />
            <h1 id="inbox-h" className="text-lg font-semibold">
              Bids inbox
            </h1>
            <SandboxLabel className="ml-auto" />
          </div>
          <p className="font-mono text-xs text-zinc-400">{data.mailbox}</p>
          <p className="text-xs text-zinc-500">{live ? 'Live · your workspace' : 'Recorded triage (static)'}</p>
          <p className="text-xs text-zinc-500">{appetiteLine(data.appetite)}</p>
        </header>
        <ol aria-label="Emails" className="min-h-0 flex-1 overflow-auto">
          {data.emails.map((e) => (
            <EmailRow key={e.id} email={e} unread={!read.includes(e.id)} active={e.id === emailId} />
          ))}
        </ol>
      </section>
      <section aria-label="Email" className={cn('min-h-0 overflow-auto', !emailId && 'hidden lg:block')}>
        {selected ? (
          <EmailDetail email={selected} />
        ) : (
          <EmptyState title={emailId ? 'Email not found' : 'Select an email'}>
            Kirchhoff triages every email to the bids mailbox: it classifies the attachments, verifies the quotes,
            checks fit and supply, and opens the project.
          </EmptyState>
        )}
      </section>
    </div>
  )
}
```

- [ ] **Step 6 [cut-safe] (coordinate with Mehul before merging: `App.tsx` and `pages/Dashboard.tsx` are live P3 Task 11–14 files): Route, nav link and the dashboard entry**

`apps/web/src/App.tsx`:
- Add `import { InboxPage } from './inbox/InboxPage'`.
- After `<Route path="p/:pid" element={<WorkspacePage />} />`, add:
```tsx
        <Route path="inbox" element={<InboxPage />} />
        <Route path="inbox/:emailId" element={<InboxPage />} />
```

`apps/web/src/shell/AppShell.tsx`: in the `nav` array (same in P3 Task 5's and Task 14's versions), after the Projects entry, add:
```ts
  { to: '/app/inbox', label: 'Bids inbox', end: false },
```

`apps/web/src/pages/Dashboard.tsx`:
- Add `Inbox` to the `lucide-react` import.
- After `import { useWorld } from '@/data/useWorld'`, add `import { unreadCount, useInbox } from '@/inbox/useInbox'`.
- Insert directly above `export function Dashboard() {`:
```tsx
/** Front door (spec §20): "Bids inbox · N new"; N counts emails this browser has not opened (static first). */
function InboxEntry() {
  const { data, read } = useInbox()
  return (
    <Link
      to="/app/inbox"
      data-tour="inbox"
      className="flex items-center gap-2 self-start rounded-lg border bg-card px-3 py-2 text-sm text-zinc-200 hover:border-zinc-600 focus-visible:outline-2 focus-visible:outline-sky-400"
    >
      <Inbox aria-hidden className="size-4 text-sky-300" />
      {data ? `Bids inbox · ${unreadCount(data, read)} new` : 'Bids inbox'}
    </Link>
  )
}

```
- In `Dashboard`, directly after the projects heading block, that is, after
```tsx
          <p className="text-sm text-zinc-400">{world.org.name}</p>
        </div>
```
  add `        <InboxEntry />`. This works whether or not P3 Task 14 has already edited the file, because Task 14 does not touch these lines.

- [ ] **Step 7 [cut-safe]: Run the tests and the type-check**

Run: `cd apps/web && npx vitest run src/inbox src/pages/Dashboard.test.tsx src/services/apiClient.test.ts && npx tsc -b && npm test`
Expected: `InboxPage.test.tsx` 8 passed, `Dashboard.test.tsx` 4 passed, the apiClient tests pass, `tsc -b` exits 0, and the whole suite passes.

- [ ] **Step 8 [cut-safe]: Commit**

```bash
git add apps/web/src/lib/types.ts apps/web/src/data/staticData.ts apps/web/src/services/apiClient.ts \
  apps/web/src/services/apiClient.test.ts apps/web/src/test/render.tsx apps/web/src/test/fixtures/index.ts \
  apps/web/src/test/fixtures/inbox.json apps/web/src/inbox/useInbox.ts apps/web/src/inbox/inboxMeta.ts \
  apps/web/src/inbox/inboxTour.ts apps/web/src/inbox/EmailDetail.tsx apps/web/src/inbox/InboxPage.tsx \
  apps/web/src/inbox/InboxPage.test.tsx apps/web/src/App.tsx apps/web/src/shell/AppShell.tsx \
  apps/web/src/pages/Dashboard.tsx apps/web/src/pages/Dashboard.test.tsx
git commit -m "feat(web): bids inbox page (static first), fit card, Pursue, dashboard entry

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 9 [cut]: Write the failing live-triage tests**

`apps/web/src/inbox/TriageButton.test.tsx`:
```tsx
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { vi } from 'vitest'
import { useWorldStore } from '@/data/useWorld'
import { ApiError } from '@/services/apiClient'
import { fixtureInbox } from '@/test/fixtures'
import { fakeApi, fakeServices, renderWithProviders } from '@/test/render'
import { InboxPage } from './InboxPage'
import { resetInboxStore } from './useInbox'

beforeEach(() => {
  useWorldStore.setState({ world: null, error: null, loading: false })
  resetInboxStore()
})

function hallB(services = fakeServices()) {
  return renderWithProviders(
    <Routes>
      <Route path="/app/inbox/:emailId" element={<InboxPage />} />
    </Routes>,
    { route: '/app/inbox/em-hall-b', services },
  )
}

test('live triage shows progress, then the live result', async () => {
  const user = userEvent.setup()
  const live = { ...fixtureInbox().emails[0].triage!, source: 'live' as const }
  let resolve: (v: typeof live) => void = () => {}
  const api = fakeApi({ triage: vi.fn(() => new Promise<typeof live>((r) => (resolve = r))) })
  hallB(fakeServices({ api }))
  await user.click(await screen.findByRole('button', { name: 'Triage live' }))
  const progress = screen.getByRole('status')
  expect(progress).toHaveTextContent('Reading the email and its attachments')
  expect(progress.querySelector('svg')).toHaveClass('motion-reduce:animate-none')
  resolve(live)
  expect(await screen.findByText('Live triage complete.')).toBeInTheDocument()
  expect(screen.getByText(/live triage · 7\/7 quotes verified/)).toBeInTheDocument()
  expect(api.triage).toHaveBeenCalledWith('em-hall-b')
})

test('with the API down or slow, the recorded triage stays and says why', async () => {
  const user = userEvent.setup()
  const api = fakeApi({ triage: vi.fn(async () => Promise.reject(new ApiError(504, 'timeout'))) })
  hallB(fakeServices({ api }))
  await user.click(await screen.findByRole('button', { name: 'Triage live' }))
  expect(await screen.findByRole('status')).toHaveTextContent(
    'Live triage unavailable: The engine took too long to answer; try again. The recorded triage stays on screen.',
  )
  expect(screen.getByText(/recorded triage · 7\/7 quotes verified/)).toBeInTheDocument()
  expect(within(screen.getByRole('region', { name: 'Fit verdict' })).getByText('Pursue')).toBeInTheDocument()
})
```

- [ ] **Step 10 [cut]: Run to verify failure**

Run: `cd apps/web && npx vitest run src/inbox/TriageButton.test.tsx`
Expected: 2 failed with `TestingLibraryElementError: Unable to find role="button" and name "Triage live"`.

- [ ] **Step 11 [cut]: The Triage button**

`apps/web/src/inbox/TriageButton.tsx`:
```tsx
// Live triage (spec §20): only on the Hall B email. While it runs, a two-stage progress line (motion off under
// prefers-reduced-motion); if the API is down or slow, the recorded triage stays on screen with a note.
import { LoaderCircle, Zap } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import type { InboxEmail } from '@/lib/types'
import { describeApiError } from '@/services/apiClient'
import { useServices } from '@/services/services'
import { applyTriage } from './useInbox'

const PROGRESS = ['Reading the email and its attachments…', 'Verifying quotes, checking fit and supply…']

export function TriageButton({ email }: { email: InboxEmail }) {
  const { api } = useServices()
  const [state, setState] = useState<'idle' | 'running' | 'done' | 'failed'>('idle')
  const [stage, setStage] = useState(0)
  const [note, setNote] = useState('')
  useEffect(() => {
    if (state !== 'running') return
    const t = setTimeout(() => setStage(1), 3000)
    return () => clearTimeout(t)
  }, [state])
  if (!email.live_triage) return null
  const run = async () => {
    setState('running')
    setStage(0)
    try {
      applyTriage(email.id, await api.triage(email.id))
      setState('done')
    } catch (e) {
      setNote(describeApiError(e))
      setState('failed')
    }
  }
  return (
    <div className="flex flex-col gap-1.5">
      <Button variant="outline" onClick={run} disabled={state === 'running'} className="self-start">
        <Zap aria-hidden />
        {state === 'done' ? 'Triage again' : 'Triage live'}
      </Button>
      {state === 'running' && (
        <p role="status" className="flex items-center gap-1.5 text-xs text-sky-200">
          <LoaderCircle aria-hidden className="size-3.5 animate-spin motion-reduce:animate-none" />
          {PROGRESS[stage]}
        </p>
      )}
      {state === 'done' && (
        <p role="status" className="text-xs text-emerald-300">
          Live triage complete.
        </p>
      )}
      {state === 'failed' && (
        <p role="status" className="text-xs text-amber-200">
          Live triage unavailable: {note} {email.triage ? 'The recorded triage stays on screen.' : ''}
        </p>
      )}
    </div>
  )
}
```

In `apps/web/src/inbox/EmailDetail.tsx`, add `import { TriageButton } from './TriageButton'` after the `./inboxMeta` import. In the actions row, after `{triage && <PursueAction email={email} triage={triage} />}`, add:
```tsx
        <TriageButton email={email} />
```

- [ ] **Step 12 [cut]: Run the tests**

Run: `cd apps/web && npx vitest run src/inbox && npx tsc -b && npm test`
Expected: `TriageButton.test.tsx` 2 passed, `InboxPage.test.tsx` 8 passed (Vindhya still has no Triage button), `tsc -b` exits 0, and the whole suite passes.

- [ ] **Step 13 [cut]: Commit**

```bash
git add apps/web/src/inbox/TriageButton.tsx apps/web/src/inbox/TriageButton.test.tsx apps/web/src/inbox/EmailDetail.tsx
git commit -m "feat(web): live Triage on the Hall B email with progress and recorded fallback

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 14: Tell the controller and WS4**

"I-3 landed:
- `/app/inbox` renders from `/demo/inbox.json` (I-1) and upgrades to `GET /api/inbox` when it answers.
- The dashboard shows 'Bids inbox · N new' (anchor `[data-tour="inbox"]`, `INBOX_TOUR_STEP` exported; the 7-step tour is unchanged).
- For the video beat (spec §20): open `/app/inbox/em-hall-b`, then Triage live, then Pursue, which opens Hall B's intake.
- WS4 Playwright (optional): the static suite can assert that `/app/inbox/em-hall-b` shows 'Pursue' and the supply line with the API blocked."

---

## Self-review

**Spec §20 coverage:**

| Requirement | Where |
|---|---|
| Mailbox (sandbox, simulated) with about 6 seeded emails, in the listed order and kinds | I-1 Step 3 (`world.yaml` `inbox.emails`); I-1 test `test_the_six_spec_20_emails_newest_first` |
| Hall B tender with tender PDF, drawing and an addendum (live target); a scanned BOQ (image PDF); a brochure | I-1 Steps 3 and 5 (reuse + `letter_pdf`/`scan_pdf`); `test_attachments_are_deterministic_and_labelled` |
| Inbox agent on Gemini 3.8 Flash, multimodal, thinking low | I-2 Step 4 (`INBOX`); Step 6 attaches every PDF |
| Classifies attachments (tender, drawing, addendum, BOQ, brochure, other) | I-2 `AttachmentTriage`; I-3 chips by class |
| Links a CRM account and opportunity, or proposes a new one | I-2 `link_crm`; I-3 `CrmLine` |
| Extracts client, site, asset type, MW, redundancy, bid due date and lead-time clause, following §6.3 | I-2 `verify_field` (pdfplumber `verify_quote` / body substring; `unverified_scan`; unverified numbers withheld; summary sanitized) |
| Fit check (deterministic): asset packs, MW range, regions, days to deadline → Pursue / Clarify / Decline with reasons | I-1 appetite; I-2 `assess_fit` and `test_inbox_fit.py` |
| Day-zero supply check (R15 before bidding: engine sizing, ERP lead time, swap) | I-2 `day_zero_supply` (engine `place_racks`/`power_options`/`r15_swap`); `test_day_zero_supply_for_hall_b_expects_the_in_stock_swap` |
| Pursue creates the project and moves or creates the opportunity at "Qualification"; Hall B opens Intake | I-1 sandbox (B1, B2); I-2 `pursue` (B3, B4); I-3 `PursueAction` |
| Static first: precomputed triage for every seeded email, from the real agent, frozen into the bundle | I-2 Step 15 + `precompute.py`; I-1 `load_triage_capture` / `build_inbox`; I-3 static loader |
| Live Triage only on the Hall B email | I-1 `live_triage`; I-2 409 `precomputed`; I-3 `TriageButton` |
| Cut line (Thu 16 Oct 12:00 IST) | Every step tagged [cut-safe] or [cut] |
| UI: icon + text, keyboard, reduced motion; tour order unchanged | I-3 (`VERDICT_META`, `VERIFICATION_META`, `StatusBadge`, link rows, `motion-reduce:animate-none`); `INBOX_TOUR_STEP` outside `TOUR_STEPS` |

**Validation done while writing.** Every code block was run in scratch copies of the three worktrees, with I-1 merged into the WS2 copy and P2 Tasks 8, 9 and 12 taken from the P2 plan.
- WS4 enterprise suite: 64 passed. `build_inbox.py` and `--check` were deterministic, and the seed-loader dry run reported 6 inbox emails.
- WS2 whole suite: 262 passed. The post-capture state (`precompute --backend replay` → `build_inbox.py`) also passes.
- WS3: 102 passed, and `tsc -b` exits 0.
- WS4's protocol-match test passes against WS2's extended `EnterpriseClient`.
- The scanned BOQ was rendered and inspected (no text layer, readable image).
- The fixture `apps/web/src/test/fixtures/inbox.json` is the generator's real output after a replayed precompute.

**Type consistency checked across tasks:**
- `InboxSeed`/`InboxEmail`/`InboxAttachment` (I-1) are consumed unchanged by I-2.
- `TriageResult`/`PursueResult` (I-2) match `src/lib/types.ts` (I-3). `tsc -b` passes over the generated fixture.
- The error codes in `inbox_routes.py` match `DETAIL_TEXT`.
- `STAGE_QUALIFYING == "Qualification" ∈ STAGES`.
- `create_opportunity(uid, opportunity)` has the same signature on the protocol, both WS4 clients and `FakeEnterprise`.
- Replay keys are `inbox:triage:{email_id}`, and the capture version is 1 on both sides.
