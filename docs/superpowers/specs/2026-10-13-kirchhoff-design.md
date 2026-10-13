# Kirchhoff — design spec

**Product:** Kirchhoff, by team Ordinal (Mehul Arora, lead; Jaydratha).
**One-liner:** the AI engineering team for the AI build-out. Agents design power and cooling for AI data centres from grid to rack in under an hour; an independent, deterministic checker verifies and cites every number; a senior engineer signs off.
**Target:** Google Cloud × Hack2skill AI Builder Cup 2026, theme *Future of Work & Enterprise Productivity*. Secondary: Hitachi Startup Challenge 2026 (Smart Engineering).
**Date:** 2026-10-13. **Submission due:** 18 Oct 2026; internal deadline 17 Oct, 20:00 IST.

---

## 1. Constraints that shape everything

| Constraint | Source | Consequence |
|---|---|---|
| Submissions close 18 Oct 2026 | aibuildercup.com | ~4 build days. Scope is cut to one scripted golden path that must work live. |
| Video strictly under 3:00 | Official T&C | Storyboard is 2:50. Every feature must earn screen time. |
| Fresh code only, written during the hackathon | Official T&C | New repo (`kirchhoff`), first commit 13 Oct 2026. Reuse nothing from other team repos. Open-source libraries are fine. |
| Must use Gemini/Gemma or Google agent platforms; deploy on Cloud Run/Firebase; brief must explain Firebase, Firestore, Cloud Run, Gemini | Rules + submission instructions | Each of those has a load-bearing role (section 6), not a token one. |
| Live URL must work throughout judging (19 Oct – 6 Nov) | Rules | min-instances, uptime check, budget alert, replay fallback (section 10). |
| Judging: 40% technical merit/GenAI ("Google Cloud architectural depth"), 25% impact, 25% innovation, 10% UX; side prizes for best use of Google Cloud AI and best UI/UX | T&C | Multi-agent ADK graph, visible verification, premium UI. |
| Available models (probed 13 Oct on project `ordinal-mep`) | Direct API calls | `gemini-3.8-flash` (GA, works). `gemini-3.1-pro-preview` and `gemini-3.8-flash-lite` return 404 for this project, so we do not depend on them. Live voice: `gemini-live-2.5-flash-native-audio` (Vertex catalogue); confirm a newer Live model on day 1. |
| Max 4 parallel subagents during the build | User rule | Build is split into at most 4 parallel workstreams. |

## 2. Why this product wins

The competitor teardown (`../research_notes/AI MEP design competitors and UX/`) found:
- **Endra** (the best-funded AI MEP design company) automates placement, circuiting and routing inside a 3D building view, but its violation flags cite no clauses, it has no independent checker, no data-centre features, no voice, and no ERP/PLM links.
- **Nobody** couples data-centre electrical design with liquid cooling, shows clause-cited checks on the canvas, keeps SLD/schedule/BOQ consistent live, or shows impact chains through MEP systems.
- Past Google hackathon winners share four traits: role-separated multi-agent systems, one obvious Gemini strength, visible verification/explainability, and an enterprise workflow with a quantified headline.

Kirchhoff's three differentiators, each visible on screen:
1. **AI checks AI.** A deterministic Checker (no LLM in the verdict path) re-computes every value, cites the clause and the tender sentence, and forces a fix on camera.
2. **Grid-to-rack, power and cooling together.** One typed model holds electrical and liquid-cooling systems; clashes and impact chains cross both.
3. **Enterprise-native.** Procurement agent reads ERP lead times and redesigns around stock; approved designs push purchase requisitions to ERP and update the CRM opportunity.

## 3. The 2:50 demo storyboard (the build serves this)

| Time | Beat | What the viewer sees | Features exercised |
|---|---|---|---|
| 0:00–0:15 | Hook | Narration over the hall in 3D: AI needs gigawatts of new halls; each needs an engineered power and cooling chain; first designs take weeks today. | Landing, 3D hall |
| 0:15–0:35 | Intake | Drop the client requirements PDF and the hall drawing. Requirement cards stream in ("48 racks × 132 kW, 2N, 80% liquid, ΔV ≤ 3%…"), each with a chip that opens the PDF at the highlighted clause. Gemini's reading of the drawing is cross-checked against the DXF ("24 columns found · DXF agrees"). | Intake agent, citations, PDF viewer |
| 0:35–0:50 | Plan gate | The Orchestrator proposes a plan; the engineer edits one step (e.g. "prefer 3.15 MVA transformers") and approves. Ask/Auto switch visible. | Plan gate, autonomy switch |
| 0:50–1:30 | Agents in parallel | Agent lanes animate. Power Architect streams the SLD node by node. Layout places racks and routes busways around columns in 3D. Cooling places CDUs and pipe loops. Procurement flags a 98-week transformer lead time from ERP and proposes an in-stock rating. Three topology options appear side by side with cost, losses, lead time and single-point-of-failure count. Engineer picks one. | Multi-agent run, SLD, 3D, options compare, ERP sim |
| 1:30–1:55 | Checker catches errors | The Checker (own colour, own cursor) fills the compliance matrix: ~150 checks. Two real failures from the first pass: busway B-07 voltage drop exceeds the 3% project limit; a coolant header routed above an electrical busway breaks the "no liquid over electrical" clause. Each opens to clause, formula, inputs, value vs limit. Designer fixes; visual diff on SLD and 3D; re-check all green. | Checker, matrix, finding drawer, fix loop, diff |
| 1:55–2:15 | Voice what-if | Engineer asks aloud: "What if next year's racks go to 200 kW?" The co-pilot answers while the engine re-runs; an impact chain lights up rack → busway → UPS → transformer → CDU, with the items that now fail. | Gemini Live, impact chain |
| 2:15–2:30 | Sign-off and enterprise | Design review page: diff, "did / assumed / left undone" ledger, approve with stamp. Purchase requisitions appear in the ERP panel; CRM opportunity moves to "Design approved". Exports: DXF, PDF calc report, BOQ. | Review, approvals, ERP/CRM sim, exports |
| 2:30–2:45 | Playbooks | Switch to Grid: 132 kV feeder on a map, conductor choice, fault level at the connection point. Switch to Solar: on-site PV field on a map with strings and DC voltage drop. "Same engine, new playbook." | Grid and Solar slices |
| 2:45–2:50 | Close | Architecture card (Gemini · ADK · Cloud Run · Firestore · Firebase) and the measured headline: time from upload to signed, checker-verified design. | — |

All failures shown are real outputs of the engine on the seeded inputs, not staged animations. The headline time is measured from the real run.

## 4. Scope tiers

**Must (demo cannot work without):**
- Seeded scenario "Hall A" (section 8) with the requirements PDF and hall DXF/PDF.
- Intake agent: requirements extraction with page/box citations; DXF geometry parse plus Gemini drawing cross-check.
- Plan gate with editable steps and Ask/Auto switch.
- Agent run streamed live to the UI via Firestore (lanes, tool calls, artifacts).
- Engine: electrical model, sizing, voltage drop, short circuit (pandapower IEC 60909), redundancy (N-1 simulation), cooling loop sizing, spatial routing and clash checks.
- Three topology options with metrics; engineer selects one.
- Checker with clause-cited findings, compliance matrix, finding drawer, fix loop (max 2 iterations), re-check.
- SLD view (React Flow + ELK), 3D hall view (react-three-fiber) with busways, pipes, racks, CDUs coloured by check status.
- Revision timeline, visual diff, review page with sign-off stamp, assumptions ledger.
- ERP simulator with lead times and purchase requisitions; Procurement agent uses it.
- Exports: DXF (ezdxf), PDF calc report, BOQ CSV.
- Deployed on Firebase Hosting + Cloud Run with a one-click demo mode (anonymous auth).

**Should (in the video, cut only if day 3 slips):**
- Voice co-pilot (Gemini Live) with the what-if and impact chain.
- CRM update on approval.
- Grid playbook slice. Solar playbook slice.

**Stretch (only after everything above is solid):**
- CADCraft headless render of the exported DXF, reviewed visually by Gemini ("does the drawing match the model?").
- Engine exposed as an MCP server.
- Live multi-user presence.
- Gemma on-prem mode on the team's RTX 4090.

**Out of scope:** auto-layout from messy real-world architectural drawings, Revit/IFC round-trip, real ERP/CRM connectors, user accounts beyond anonymous demo sessions, certified calculations.

## 5. Agent design

Built with **ADK 2.0 (Python)** as a graph workflow, served from Cloud Run. Every agent runs on `gemini-3.8-flash` with structured output and function calling. Agents decide and explain; tools compute. Every tool result is validated by a Pydantic schema before it enters the design model.

| Agent | Colour | Reads | Tools | Writes |
|---|---|---|---|---|
| **Intake** | slate | Requirements PDF (native PDF input), hall drawing PDF | `parse_dxf_geometry`, Gemini vision boxes on the drawing | `DesignBrief` (typed requirements, each with `{doc, page, bbox, quote}` citations); geometry cross-check result |
| **Orchestrator** | white | Brief | — | Editable plan (ordered steps with owner agent); waits at the plan gate when autonomy = Ask |
| **Power Architect** | amber | Brief, ERP availability | `size_power_chain`, `enumerate_topologies`, `run_short_circuit`, `simulate_n_minus_1` | Three topology options with metrics; selected electrical model |
| **Layout & Routing** | cyan | Brief, geometry, electrical model | `place_racks`, `route_busways`, `route_pipes`, `detect_clashes` | Rack positions, busway and pipe routes in 3D |
| **Cooling** | blue | Brief, rack loads, layout | `size_cdus`, `size_headers`, `hydraulic_zones` | CDUs, zones, pipe sizes, flows |
| **Procurement** | green | Bill of materials | `erp_search_materials`, `erp_lead_time`, `erp_create_pr` (sim) | Availability flags, alternatives, cost; PRs after approval |
| **Checker** | red | Whole revision | `run_rule_pack` (deterministic, no LLM) | Findings; Gemini is used only to write the plain-English explanation and propose a fix, never to decide pass/fail |
| **Docs** | violet | Approved revision | `export_dxf`, `render_calc_report`, `export_boq` | Files in Cloud Storage |
| **Co-pilot (voice)** | gradient | Current revision, findings | `what_if(param, value)`, `explain(finding_id)`, `focus(element_id)` | Spoken answers; triggers engine re-runs and UI focus |

**Run flow:** Intake → Orchestrator (plan gate) → Power ∥ Layout ∥ Cooling (Layout waits for Power's topology choice before routing busways) → Procurement → Checker → if failures and iterations < 2: owning agent receives findings and revises → Checker → Docs → review gate (human sign-off) → Procurement creates PRs and the CRM update.

**Determinism and trust rules:**
- Every numeric value displayed comes from the engine. LLM text that contains numbers is post-checked against the engine values it claims to describe; mismatches are dropped.
- Each finding stores `{rule_id, clause_refs[], tender_refs[], formula, inputs, value, limit, unit, status, explanation}`.
- Each agent writes an assumptions ledger entry when it fills a gap the brief did not specify (e.g. "assumed PG25 coolant; brief silent on glycol mix").

## 6. Google Cloud architecture

```
Browser (React app on Firebase Hosting, kirchhoff.web.app)
  ├─ Firebase Auth (anonymous demo sessions)
  ├─ Firestore onSnapshot: runs/events, revisions, findings, approvals (live UI)
  ├─ Firebase AI Logic → Gemini Live API (voice co-pilot; tool calls hit /api)
  └─ /api/** rewrite ──► Cloud Run "kirchhoff-api" (Python 3.12, FastAPI, ADK 2.0, asia-south1)
                            ├─ ADK agent graph on Vertex AI gemini-3.8-flash (global endpoint)
                            ├─ Engine (pandapower, shapely, networkx, fluids, pvlib, ezdxf)
                            ├─ Firestore writes (event stream, revisions, audit)
                            └─ Cloud Storage (uploads, exports)
                         Cloud Run "kirchhoff-enterprise" (FastAPI; simulated ERP + CRM over REST, Firestore-backed)
  Secret Manager · Cloud Build (deploys) · Cloud Monitoring uptime check · budget alert
```

How each mandatory technology is load-bearing:
- **Gemini:** reads multi-page PDFs and drawings with page-level citations and boxes; plans; chooses among engine-generated options; explains findings; powers live voice.
- **ADK on Cloud Run:** the multi-agent graph, tool calling, plan gate and fix loop.
- **Firestore:** the real-time event bus the UI renders from, the design revision history, findings, approvals and audit trail.
- **Firebase:** Hosting, anonymous Auth for judge sessions, AI Logic for the Live voice session.
- **Cloud Run (two services):** agent/engine API and the enterprise simulator, which shows how the agents integrate with external systems.

## 7. Engine and rule pack

The engine is a pure Python package (`kirchhoff_engine`) with no LLM calls. It owns a typed design model:

- **ElectricalNode** (utility_intake, transformer, lv_switchboard, ups, busway, tap_off, rack) with ratings.
- **ElectricalEdge** (cable or busway) with length, cross-section/rating, R/X per metre, route id.
- **CoolingNode** (cdu, header, rack_manifold) and **CoolingEdge** (pipe) with diameter, length, flow.
- **Geometry:** hall polygon, column grid, keep-out zones, rack footprints, 3D polylines for routes at named tiers (busway tier +3.2 m, pipe tier +2.6 m).

Calculations (each unit-tested against a hand calculation):
- Design current: `I = P / (√3 · U · cosφ)` for three-phase AC.
- Voltage drop: `ΔU% = 100 · √3 · I · L · (R cosφ + X sinφ) / U`, with distributed-load factor 0.5 for busways with evenly spaced tap-offs; cumulative from the LV switchboard to the furthest rack tap-off.
- Short circuit: pandapower `calc_sc` (IEC 60909) at every LV switchboard and busway, max case.
- Redundancy: remove each component in turn and re-run load allocation; any rack losing supply is a single point of failure.
- Cooling: `ṁ = Q / (cp · ΔT)`; pipe velocity `v = 4·V̇ / (π·D²)`; pressure drop by Darcy–Weisbach via `fluids`.
- Spatial: route polylines as Shapely geometry; clearance and "liquid above electrical" tests by projecting pipe segments onto busway footprints where the pipe tier is above the busway tier at the crossing.

Rule pack v0.1, "IEC-based demo rules, illustrative values". Clause references point to standards by number and clause; no copyrighted table text is reproduced. Limits come from the project's own requirements document wherever it specifies them.

| Rule | Check | References |
|---|---|---|
| R01 | Transformer loading ≤ 100% in normal and failover states | IEC 60076-7 (loading guide); tender clause |
| R02 | Busway/cable rating ≥ design current | IEC 61439-6 (busbar trunking); IEC 60364-5-52 |
| R03 | Protective device coordination `Ib ≤ In ≤ Iz` | IEC 60364-4-43 §433.1 |
| R04 | Breaking capacity ≥ prospective Ik″ | IEC 60909-0; IEC 60947-2 |
| R05 | Voltage drop LV board → rack ≤ project limit | Tender clause; IEC 60364-5-52 §525 |
| R06 | No single point of failure in the chosen topology | Tender clause; TIA-942 (redundancy concepts) |
| R07 | UPS capacity per side ≥ load; autonomy ≥ spec minutes | Tender clause |
| R08 | CDU capacity per zone ≥ liquid heat load with N+1 | Tender clause; ASHRAE TC 9.9 liquid-cooling guidance |
| R09 | Coolant flow meets each rack's required flow at design ΔT | Tender clause |
| R10 | Pipe velocity ≤ limit | Tender clause |
| R11 | Clearance to structure ≥ minimum; no liquid piping above electrical busways | Tender clause |
| R12 | Cross-document consistency: SLD equipment = BOQ lines = PR lines | Internal consistency rule |

## 8. Seeded scenario: Hall A (fictional)

All names are fictional and labelled so in the UI ("Sample project").

- **Client:** Deccan Compute (fictional). **Site:** an AI campus near Hyderabad (fictional).
- **Hall A:** 60 m × 36 m, column grid 12 m × 9 m (24 columns), one keep-out zone for a fire-suppression room.
- **IT load:** 48 racks in 4 rows of 12, 132 kW per rack (GB300 NVL72-class), 6.336 MW total; 80% liquid / 20% air.
- **Power:** two 33 kV incomers (A/B) from the campus substation; 2N preferred, alternatives allowed if no single point of failure; LV 415 V, 50 Hz; cosφ 0.95; UPS autonomy ≥ 5 min; voltage drop ≤ 3% LV board → rack tap-off; breaking capacity ≥ prospective fault level.
- **Cooling:** secondary loop with PG25, supply 30 °C, ΔT 10 K, CDUs N+1 per hydraulic zone, pipe velocity ≤ 2.5 m/s, no liquid piping above electrical busways.
- **Requirements PDF:** 8–10 pages, numbered clauses, authored by us with ReportLab so every citation target is real.
- **Hall drawing:** a DXF authored with ezdxf (columns, walls, keep-out, grid labels) plus a PDF plot of it for Gemini to read.
- **ERP sim seed:** transformers 2.5 MVA (98-week lead time, 0 in stock) and 3.15 MVA (12 weeks, in stock), UPS modules, busway runs, CDUs, with indicative prices.
- **Tuning:** the first-pass layout's shortest path for busway B-07 runs around the keep-out zone, giving a real voltage-drop failure; the Cooling agent's first header route crosses above a busway. Both fixes (re-feeding B-07 from the nearer board or upsizing; dropping the header to the lower tier) are found by the agents, and the Checker's re-run passes. Tuning means choosing realistic inputs; the engine never hard-codes outcomes.

## 9. Playbooks (thin slices)

**Grid (transmission intake):** a 132 kV double-circuit overhead line, about 18 km, from a grid substation to the campus substation (2 × 50 MVA 132/33 kV transformers). Engine: compare three ACSR conductors by ampacity, voltage regulation and I²R losses; pandapower fault level at the point of connection; mini SLD of the campus substation. UI: map with the line route, three conductor cards, recommendation with checks. Uses the same Checker with a small grid rule set.

**Solar (on-site PV):** a ~5 MWp ground-mount field on a polygon next to the hall. Engine: pvlib clear-sky yield estimate (no external weather API at runtime), string sizing from module Voc at minimum site temperature against inverter maximum DC voltage, table layout on the polygon with Shapely, DC string cable voltage drop. UI: map with table rows, string and inverter cards, checks.

Both reuse the shell, Checker, findings drawer and revision timeline. Neither has its own agents beyond a single "Playbook agent" that runs the engine and explains results.

## 10. Reliability and judging-window operations

- **Demo mode:** one button on the landing page creates an anonymous session and a private copy of Hall A. No login, no setup.
- **Live by default, replay as fallback:** every completed run's events are stored. If Gemini errors or quota is exhausted, the UI offers "Replay a recorded run", clearly labelled as a replay. The live path is what the video shows.
- **Cloud Run:** `kirchhoff-api` min-instances 1, max 5, 2 vCPU / 4 GiB, request timeout 900 s; runs execute as background tasks with progress in Firestore. Enterprise sim min-instances 1.
- **Gemini calls:** retries with exponential backoff; per-agent timeout; structured-output validation with one repair attempt.
- **Rate limit:** 10 runs per anonymous user per hour.
- **Monitoring:** Cloud Monitoring uptime check on the landing page and `/api/health` with email alert; GCP budget alert at USD 100.
- **Freeze:** after submission, only fixes go to production, via a tagged release.

## 11. UI design

Visual direction: dark, dense, Linear/Vercel-like. Neutral greys, one accent colour per agent, monospace numerals for engineering values, Inter for text. Effects (glow, gradients) only on the landing page. Motion is used to show progress (nodes streaming in, matrix cells filling, diff cross-fades), never decoration.

**Screens:**
1. **Landing:** product statement, "Open demo project" button, three playbook cards (AI Data Centre, Grid, Solar).
2. **Workspace (main):**
   ```
   ┌ Kirchhoff ▸ Deccan AI Campus · Hall A  [Playbook ▾] ●5 agents live [Ask|Auto] [Request sign-off] ┐
   ├─────────────┬──────────────────────────────────────────────┬───────────────┤
   │ Agent lanes │ [3D Hall] [SLD] [Matrix] [Options] [Docs]    │ Co-pilot      │
   │ ● Intake ✓  │                                              │ plan · chat   │
   │ ● Power ⋯   │   live canvas: agent cursors, checker        │ voice         │
   │ ● Layout ⋯  │   highlights, ghost diffs                    │ citations     │
   │ ● Cooling ⋯ │                                              │               │
   │ ● Procure ⋯ │                                              │               │
   │ ● Checker ✕2│                                              │               │
   ├─────────────┴──────────────────────────────────────────────┴───────────────┤
   │ Revisions  r1 ── r2 ── r3 (2 fails) ── r4 ✓ signed                          │
   └─────────────────────────────────────────────────────────────────────────────┘
   ```
3. **Plan gate:** editable step list, owner agent per step, Approve / Ask / Auto.
4. **Options compare:** three cards (2N, distributed redundant 4-to-make-3, block redundant with reserve) with cost, losses, lead time, footprint, SPOF count; select.
5. **Finding drawer:** rule, clause chips, tender chip (opens PDF at the highlight), formula with inputs, value vs limit bar, explanation, proposed fix, "show on canvas".
6. **Review page:** revision diff (SLD and 3D side by side, changed elements list), assumptions ledger, findings summary, Approve with stamp (name, time, revision hash).
7. **Enterprise panel:** ERP PRs created, CRM opportunity stage.
8. **Grid** and **Solar** playbook screens (section 9).

**Libraries:** Vite + React + TypeScript, Tailwind + shadcn/ui, Motion, @xyflow/react + elkjs (SLD, IEC-style custom symbol nodes), @react-three/fiber + drei (3D), react-pdf (citations), Google Maps JavaScript API (grid and solar maps), TanStack Table (matrix), Firebase JS SDK (Auth, Firestore, AI Logic).

## 12. Data model (Firestore)

```
projects/{pid}                      name, playbook, ownerUid, createdAt, status, briefRef
projects/{pid}/documents/{did}      kind (requirements|drawing), storagePath, pages, extraction
projects/{pid}/runs/{rid}           status, autonomy, plan[], startedAt, finishedAt, metrics
projects/{pid}/runs/{rid}/events/{eid}  seq, agent, kind (plan|tool_call|tool_result|message|artifact|finding|gate), title, detail, payload, ts
projects/{pid}/revisions/{rev}      parentRev, author (agent|human), model (design JSON), summary, checkSummary, status (draft|checked|signed), ledger[]
projects/{pid}/revisions/{rev}/findings/{fid}  rule_id, element_id, clause_refs, tender_refs, formula, inputs, value, limit, unit, status, explanation, fix
projects/{pid}/approvals/{aid}      rev, approver, decision, comment, ts
enterprise/erp/materials/{mid}      category, rating, stock, leadTimeWeeks, unitPrice
enterprise/erp/prs/{prid}           projectId, lines[], status, createdAt
enterprise/crm/opportunities/{oid}  account, stage, value, notes
```

Security rules: an anonymous user can read and write only projects they own; runs, revisions, findings and enterprise collections are written only by the backend service account; reads are scoped by project ownership.

## 13. Repository layout

```
kirchhoff/
  apps/web/                  React app
  services/api/              FastAPI + ADK agents + engine (kirchhoff_engine package) + tests
  services/enterprise/       ERP/CRM simulator
  scenarios/hall_a/          generators for the requirements PDF, hall DXF/PDF, ERP seed
  infra/                     firebase.json, firestore.rules, deploy scripts, budget/uptime setup
  docs/                      architecture, submission brief, this spec
```

The public GitHub repo is created private today and made public before submission.

## 14. Testing

- **Engine:** pytest unit tests for every calculation against hand-worked values (design current, voltage drop, short circuit sanity vs `Ik ≈ In/uk`, N-1 simulation, coolant flow, pipe velocity, clash geometry).
- **Rule pack:** each rule has a passing and a failing fixture.
- **Scenario regression:** the seeded first pass must produce exactly the two planted-by-tuning failures, and the fixed revision must pass all checks.
- **Agents:** schema-validation tests with recorded Gemini responses; one live smoke test per day.
- **End to end:** a Playwright script walks the demo path against the deployed URL (open demo → run → approve plan → wait for checker → fix → sign off); run before every deploy and daily during judging.

## 15. Schedule

| Day | Deliverables |
|---|---|
| Mon 13 Oct | Spec, plan, repo, scaffold; hello-world deployed end to end (Hosting → Cloud Run → Firestore event stream visible in the browser) |
| Tue 14 Oct | Engine and rule pack with tests; Hall A scenario files; Intake agent with citations; agent graph skeleton streaming events |
| Wed 15 Oct | Workspace UI: lanes, SLD, 3D hall, matrix, finding drawer, PDF citations, revisions; full agent run on the seeded scenario |
| Thu 16 Oct | Options compare, ERP sim + Procurement, fix loop + diff, review/sign-off, exports; voice co-pilot; grid and solar slices |
| Fri 17 Oct | Polish, Playwright pass, deck (16-slide template), screen capture, video cut (< 3:00), brief, repo public, submit by 20:00 IST |
| Sat 18 Oct | Buffer only |

Build parallelism: at most 4 workstreams (engine; agents/API; web UI; infra/enterprise sim/scenario), integrated daily.

## 16. Risks

| Risk | Mitigation |
|---|---|
| ADK 2.0 API details differ from expectations | Day-1 spike before building agents; fall back to plain `google-genai` function calling in the same graph shape if blocked |
| Gemini Live model availability in Firebase AI Logic | Day-3 spike; fallback is push-to-talk with Gemini transcription + TTS |
| Run latency too long for the video | Parallel agents, small prompts, engine does heavy lifting; stream partial results; video uses real-time footage with jump cuts labelled |
| 3D/SLD polish eats the schedule | Fixed component catalogue; no free-form generated layouts; cut grid/solar before cutting checker polish |
| Copyrighted standard tables | Use clause numbers only and illustrative values labelled as such |
| Deployment breaks during judging | min-instances, uptime alert, replay fallback, feature freeze |

## 17. Submission deliverables (owned by this project)

- Deck in the fixed 16-slide template (team details, idea, opportunities/USP, features, process flow, wireframes, architecture, technologies, cost, prototype snapshots, benchmarks, future development, links).
- Video under 3:00 following section 3.
- Live URL, public GitHub repo, and a brief explaining Firebase, Firestore, Cloud Run and Gemini usage (section 6 is its source).
- Benchmarks slide uses measured values only: run time, checks executed, findings caught, engine test results.
