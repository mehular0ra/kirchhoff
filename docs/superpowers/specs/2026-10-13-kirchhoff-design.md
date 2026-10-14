# Kirchhoff — design spec (v4.1)

**Product:** Kirchhoff, by team Ordinal (Mehul Arora, lead; Jayadratha).
**One-liner:** Kirchhoff turns weeks of scarce senior-engineer work into one reviewed, signed design session. Gemini agents read the tender, design power and cooling for an AI data hall, and hand off to procurement and sales; a deterministic checker proves every number; the engineer decides and signs.
**Tagline:** *AI designs. Physics checks. An engineer signs.*
**Target:** Google Cloud × Hack2skill AI Builder Cup 2026, theme *Future of Work & Enterprise Productivity*. Secondary: Hitachi Startup Challenge 2026 (Smart Engineering).
**Date:** 2026-10-13 (v4.1 after review rounds 1–4 and the user's demo-world requirement). **Submission due:** 18 Oct 2026; internal deadline Fri 17 Oct, 20:00 IST.

---

## 1. Constraints

| Constraint | Source | Consequence |
|---|---|---|
| Submissions close 18 Oct 2026 | aibuildercup.com | ~4 build days; one golden path that must work live |
| Video strictly under 3:00 | Official T&C | Storyboard targets 2:40, burned-in captions |
| Fresh code only, written during the hackathon | Official T&C | New repo `kirchhoff`, first commit 13 Oct 2026; nothing reused from other team repos; open-source libraries fine |
| Gemini/Gemma or Google agent platforms; Cloud Run/Firebase; brief explains Firebase, Firestore, Cloud Run, Gemini | Rules | Each is load-bearing (section 7) |
| Live URL works through judging (19 Oct – 6 Nov) | Rules | Phased runs with leases, static-first browsing, uptime checks, budget alert (section 11) |
| Judging 40/25/25/10; side prizes incl. Best use of Google Cloud AI, Best UI/UX | T&C | Multi-agent ADK graph, visible verification, measured impact, premium UI |
| Models on `ordinal-mep` (probed 13 Oct) | API calls | `gemini-3.8-flash` (GA, Vertex global) for all agents. `gemini-3.1-pro-preview`, `gemini-3.8-flash-lite` return 404; not used |
| Live voice (decided by the user) | Spike 13 Oct | Vertex `gemini-live-2.5-flash-native-audio` in **us-central1** (not served in asia-south1). Spike: tool call at 3.5 s, spoken answer by 7.7 s. The model may retire Oct–Dec 2026, so push-to-talk on `gemini-3.8-flash` is an automatic fallback (section 6.5) |
| App Check mandatory for Firebase AI Logic from 2 Nov 2026 | Firebase docs | App Check enabled on day 0 |
| Hosting → Cloud Run rewrites time out at 60 s | Firebase docs | Every `/api` call returns in < 10 s; long work runs in background phases |
| ADK 2.11 verified | Spike 13 Oct | `Workflow(edges=[...])` + `LlmAgent` + tools ran live in 5.7 s with env `GOOGLE_GENAI_USE_VERTEXAI=true`, `GOOGLE_CLOUD_PROJECT=ordinal-mep`, `GOOGLE_CLOUD_QUOTA_PROJECT=ordinal-mep`, `GOOGLE_CLOUD_LOCATION=global` |
| Max 4 parallel subagents during the build | User rule | At most 4 workstreams |
| Thin Grid and Solar slices | User | Two small asset packs (section 10) |
| Demo must feel like a company already uses it: synthetic data, populated integrations, onboarding | User | Demo world (section 13) |

## 2. Why this wins

### 2.1 Theme fit (Future of Work & Enterprise Productivity)

| Theme words | What Kirchhoff does, visibly |
|---|---|
| Access knowledge | Every requirement and number links to its tender sentence and its formula/clause; ask "why?" by text or voice |
| Collaborate | Humans and agents share one workspace; a Designer prepares, a Reviewer signs; engineering, procurement and sales hand off in one flow |
| Make decisions | Three costed topology options, lead-time trade-offs, what-if before committing; every decision recorded with who, when and why |
| Execute workflows | Tender PDF → checked design → signed revision → BOQ → purchase requisitions in ERP → CRM opportunity update |

**Persona:** Priya Raman, lead electrical engineer at a data-centre EPC contractor: two juniors, three hall packages due this month, a client who keeps changing rack density. Kirchhoff lets her review instead of draft.

### 2.2 What the competition lacks

From the team's competitor research (kept outside this repo; summary report "AI MEP design competitors and UX", 13 Oct 2026):
- Endra Power Studio (launched 16 Sep 2026) places, circuits and sizes a whole building in about a second, but cites no clauses, has no independent checker and shows no data-centre features.
- Nobody couples data-hall electrical design with liquid-cooling hydraulics, shows clause-cited findings on the canvas, keeps SLD/BOQ/PRs consistent, designs around ERP lead times, or shows a cross-discipline impact chain.

### 2.3 Innovation, ranked for the deck

1. **Design around what can ship.** Lead time is a checked rule (R15) fed by ERP data: the 2.5 MVA transformer's 98-week lead time breaks the tender's 26-week limit, so Kirchhoff re-sizes to a unit that ships from stock and re-checks fault levels. Speed-to-power, not just speed-to-drawing.
2. **Power and cooling as one model.** The Checker catches coolant piping routed above live electrical, a clash no single-discipline tool sees.
3. **AI designs. Physics checks. An engineer signs.** No LLM in the verdict path.
4. **Consistency and impact chains.** SLD, BOQ and PRs agree (R12); a what-if lights up every downstream failure across both disciplines.

## 3. The 2:40 demo storyboard

Real product footage only, burned-in captions, values read from the recorded run (never typed by hand). Footage of agent work is time-compressed and labelled with an elapsed-time clock. Golden-run choice: **2N with 3.15 MVA transformers**. Most memorable moment: liquid caught above live electrical, then fixed.

| Time | Beat | On screen | Caption / voice |
|---|---|---|---|
| 0:00–0:10 | Cold open | 3D hall: zone-2 coolant header glows red where it crosses busway feeder FB-03; clause chip; header drops to the low tier; turns green | "A 6 MW AI data hall. One pipe in the wrong place floods the power. Kirchhoff caught it." |
| 0:10–0:30 | Intake | Drop tender PDF and drawing; requirement cards stream in with "✓ quote verified"; click a chip → PDF opens at the clause; Intake flags §4.2 (2N) vs Appendix B (block or distributed redundancy acceptable) | "Gemini reads the whole tender, cites every requirement, and spots where the client contradicts itself." |
| 0:30–0:40 | Plan gate | Plan with the open question; engineer answers "compare all three; §4.2 governs if equal" and approves; Ask/Auto switch visible | "The engineer stays in charge of decisions." |
| 0:40–1:10 | Agents | Lanes: Layout places 48 racks; Power and Cooling in parallel; Procurement: "2.5 MVA: 98 weeks > 26-week limit (§2.3) → 3.15 MVA ships from stock"; Power re-checks fault level (value from run). Option cards with installed MVA, normal/failover loading, cost, losses, lead time; engineer picks 2N. SLD stages in; busways and pipes route in 3D | "Agents design power and cooling together — around equipment that can actually ship." |
| 1:10–1:40 | Checker | Matrix fills to N checks (counted live); 2 fail. Open R11 "coolant header above busway feeder FB-03": clause, tender chip, geometry; Cooling drops the header to the low tier. "+1 more": feeder FA-01 ΔV above the 2% limit (value from run); Power weighs "upsize to 2,000 A busway" vs "parallel cable feeder" with cost and ΔV and picks one with a reason. Diff recolours changed elements; all green | "Gemini designs. Physics checks. The AI can't mark its own homework." |
| 1:40–1:58 | What-if | Voice (or chip): "What if racks go to 200 kW?" Impact chain lights rack → busway → board → transformer and rack → CDU zone in two colours | "See everything that breaks, across disciplines, in seconds." |
| 1:58–2:18 | Sign-off and handoff | Review page: diff, assumptions ledger, Reviewer stamp with revision hash; PRs appear in ERP; CRM opportunity moves to "Design approved" | "Engineering, procurement and sales: one workflow." |
| 2:18–2:28 | Asset packs + demo world | Projects dashboard; quick switch to Grid (132 kV line, conductor choice) and Solar (PV field, strings) | "Same engine, new asset packs." |
| 2:28–2:40 | Proof | Four measured numbers (section 4); architecture diagram held 8+ s; URL | "Built on Gemini, ADK, Cloud Run, Firestore and Firebase." |

Every failure shown is computed live on the sample inputs; the sample hall is chosen to exercise the checker; outcomes are never hard-coded.

## 4. Impact metrics (measured)

1. **Time to a checker-clean revision:** upload → all-pass revision, median of 5 live runs, excluding time spent waiting at human gates.
2. **Intake accuracy:** requirements extracted correctly vs ground truth (we authored the tender) and share of citations resolving to the right clause.
3. **Checker catch rate:** seeded-fault benchmark of ~30 mutated Hall A designs across R01–R15; detected faults and false positives.
4. **Cost per design:** Gemini tokens and USD per full run.

**Baseline:** a cited industry range for a first coordinated electrical package (4–8 weeks for good-for-construction drawings in India; the 30-day first-design figure labelled as a practitioner estimate). The deck states the mismatch honestly: Kirchhoff produces concept-stage design with illustrative rules, so the comparison is "first checked concept design", not finished construction drawings.

**Business number:** "98-week transformer → shipped from stock (sandbox data)".

## 5. Scope

**Must:**
- Hall A scenario: tender PDF, hall DXF + PDF plot, catalogue, ERP/CRM seed (section 9).
- Intake with verified citations, contradiction detection and intake scoring.
- Plan gate, option gate, review gate; Ask/Auto switch.
- Four-phase runs streamed via Firestore with leases and resume (section 6.2).
- Engine and rule pack R01–R15 (incl. R04b) with tests; scenario regression lock; seeded-fault benchmark.
- Workspace UI: agent lanes, SLD, 3D hall, compliance matrix, finding drawer with PDF citations, option cards, fix loop with diff, revision timeline, review/sign-off with assumptions ledger.
- Typed what-if with impact chain.
- ERP/CRM sandbox; Procurement agent; PRs and CRM stage update on approval.
- Exports: PDF calc report and BOQ CSV.
- Demo world core and onboarding (section 13.6 Must list).
- Deployed on Firebase Hosting + Cloud Run; App Check; uptime checks; budget alerts.

**Should (in order of value):**
1. Voice what-if via Gemini Live (with push-to-talk fallback).
2. Grid and Solar asset packs (thin).
3. Demo world extras (section 13.6 Should list).
4. Cloud Trace export of agent spans; screenshot for the architecture slide.
5. Engine as an MCP server at `/mcp` (`check_design`, `what_if`).
6. DXF export.

**Cut order if behind (Thu 18:00 IST checkpoint):** MCP server → DXF export → Cloud Trace → demo world extras → asset-pack polish (cards only) → Gemini Live (typed what-if remains). Must items are never cut.

**Cancelled for the hackathon (roadmap slide):** CADCraft rendering/visual review (pre-alpha), live multi-user presence, Gemma on-prem, 800 VDC architecture, Revit/IFC round-trip, real ERP/CRM connectors, auto-layout from messy drawings, PLM integration.

## 6. Agents and run model

### 6.1 Agents

ADK 2.11 (Python) `Workflow` graphs on Cloud Run, all on `gemini-3.8-flash` with structured output and function calling. Thinking level: low for Layout, Procurement, Docs, Co-pilot and the Asset agent; medium for Intake, Orchestrator, Power and Cooling.

**First-pass placement and routes are deterministic engine defaults (candidate #1).** Agents run the tools and narrate; they make choices only where the table says "Decides".

| Agent | Colour | Decides | Tools | Writes |
|---|---|---|---|---|
| Intake | slate | Which requirements exist, their values, contradictions | Native PDF input; `verify_quote`; `parse_dxf_geometry`; drawing cross-check | `DesignBrief`; open questions; intake score |
| Orchestrator | white | Plan steps and which questions go to the human | — | Plan; gate prompts |
| Layout | cyan | Nothing (runs the deterministic default placement and routing; narrates) | `place_racks`, `route_busways`, `detect_clashes` | Rack positions; busway routes |
| Power Architect | amber | Which topologies to offer; electrical fix choice (upsize busway vs parallel cable feeder) with reason | `enumerate_topologies`, `size_power_chain`, `run_short_circuit`, `simulate_n_minus_1` | Options with metrics; electrical model |
| Cooling | blue | Cooling fix choice (tier change vs reroute) with reason | `size_cdus`, `hydraulic_zones`, `route_pipes`, `pipe_hydraulics` | CDUs, zones, pipes, flows |
| Procurement | green | Nothing (the swap is the deterministic engine function `r15_swap`, section 8.2); narrates the trade-off | `erp_search_materials`, `erp_lead_time`, `annotate_options` (calls `r15_swap`), `erp_create_pr` | Availability and swaps on options; PRs |
| Checker | red | Nothing (deterministic) | `run_rule_pack` | Findings |
| Docs | violet | Report ordering and summary text | `render_calc_report`, `export_boq`, `export_dxf` | Files in Cloud Storage |
| Co-pilot | gradient | Which tool answers the user | `what_if`, `explain_finding`, `focus_element` | Answers; UI focus |
| Asset agent | teal | Which conductor/string option to recommend | grid and solar engine tools | Asset-pack results |

**Plan gate in Auto:** each open question resolves to the tender's main body (a numbered clause beats an appendix), so §4.2 vs Appendix B resolves to 2N; the resolution is logged in the ledger.

**Option gate:** Ask — the engineer picks. Auto — options are filtered by the resolved clauses (so 2N), then the lowest-cost option with zero single points of failure and every lead time within §2.3 is chosen; the agent states why.

**Fix candidates:** the engine offers only candidates that clear the target finding without creating any new failure (it re-runs the full rule pack on each candidate before offering it). The owning agent chooses among them on cost and margin.

**Fix-loop exhaustion:** if findings remain after 2 iterations, the run stops at the review gate with Approve disabled and the open findings listed.

### 6.2 Four-phase run model

A run has four phases, each made of named **steps** (e.g. `p2.place_racks`, `p2.power_options`, `p2.cooling_sizing`, `p2.annotate_options`). Each phase starts from a POST that validates, acquires the run lease, starts a worker thread and returns 202 in < 2 s. Each step streams its events as they happen (tagged `{step, attempt}`, batched ~250 ms) and, when finished, commits its outputs and a `done {attempt}` marker (`workspaces/{uid}/runs/{rid}/steps/{stepId}`) in a Firestore transaction that first checks `lease.attempt`, so a stale worker can never commit. No ADK session state crosses a step boundary. Engine calls run off the event loop. Every `/api` call returns in < 10 s.

```
P1  Intake → Orchestrator ......................................... PLAN GATE
P2  Layout.place_racks
    → [Power.enumerate_topologies ∥ Cooling.size_cdus + hydraulic_zones]
    → Procurement.annotate_options (R15 lead times; in-stock swaps) → Power.recheck (step `p2.power_recheck`: short circuit and R01/R04/R04b on swapped options)
    ................................................................... OPTION GATE
P3  Layout.route_busways → Cooling.route_pipes → detect_clashes (solid intersections only)
    → engine derives BOQ + draft PR lines → Checker
    → fix loop: owning agent fixes (≤ 2 iterations; each iteration = one revision) → Checker
    → Docs ............................................................ REVIEW GATE (always human)
P4  (on approval) Procurement.erp_create_pr → R12 re-run on submitted PRs → CRM stage update → audit entry
```

- **Gates:** in Ask mode a gate ends the phase and the approval POST starts the next phase. In Auto mode the worker starts the next phase itself (the review gate always waits for a human). Runs parked at a gate for more than 24 h are marked `expired`.
- **Durability:** the running phase holds a lease on `workspaces/{uid}/runs/{rid}` (`lease = {owner, attempt, heartbeatAt}`) refreshed every 15 s. If the lease is older than 60 s, the client calls `POST /api/runs/{rid}/resume`. Resume takes the lease in a Firestore transaction (incrementing `attempt`), skips every step whose `done` marker exists, reuses those steps' committed outputs, and re-executes only unfinished steps. Event `seq` continues from the highest value already written. For a completed step the UI shows only events from the attempt that committed it; for the running step, events from the current attempt. Deploys during judging happen only when no lease is held.
- **Live-run cap:** only runs holding a live lease count toward the global cap of 3.
- **P4 consistency failure:** if R12 fails on submitted PRs, PR submission is blocked, the PRs are marked `blocked`, the signed revision stays signed, and an audit entry and a finding are written.

### 6.3 Trust rules

- Every number displayed comes from the engine.
- All LLM text shown in the UI (finding explanations, lane narration, co-pilot answers) may contain digits only through placeholders (`{value}`, `{limit}`) filled from engine records, or allowlisted record tokens: element ids (B-03, FA-01, CDU-4), rule ids (R11), clause ids (§4.6), topology names (2N, N+1, 3 + 1, 4-to-make-3) and catalogue ids. Any other digit causes the sentence to be replaced by a template: the rule's template sentence for findings, "{agent} completed {step}" for lane narration, and an engine-generated summary for co-pilot answers.
- Requirement cards: Gemini returns `{page, verbatim_quote, value, unit}`; accepted only if pdfplumber finds the quote on that page and the quote contains the value; bounding boxes come from pdfplumber. The lane shows "N/M quotes verified".
- Drawing cross-check: Gemini reads grid labels and overall dimensions from the PDF plot; the engine compares with the DXF; the lane shows "Drawing read · DXF agrees" or the differences.
- Agents write assumptions-ledger entries when they fill gaps; the ledger also lists what v0.1 does not check (section 8.4).

### 6.4 What-if

`what_if(revisionRef, param, value)` builds an engine-only shadow revision (no LLM) in < 3 s and returns it **without saving**. `revisionRef` is either a visitor revision (`ws:{rev}`) or a seed revision (`seed:hall-a@r2`), which the API loads from the seed bundles baked into its image. **Semantics:** loads change; equipment, ratings, routes and flows stay frozen; all rules re-run. The impact chain is the failing elements ordered along rack → busway → board → transformer and rack → zone → CDU. Parameters: rack kW, liquid fraction, ΔV limit, transformer loading cap. Available as UI chips in every mode. The chip what-ifs for Hall A are also precomputed into its static bundle, so tour step 5 works with the backend down.

### 6.5 Voice

Browser → Firebase AI Logic (`VertexAIBackend('us-central1')`) → `gemini-live-2.5-flash-native-audio` with function declarations `what_if`, `explain_finding`, `focus_element`; the browser executes them against `/api` and returns results. If the Live session fails to open, the UI switches to push-to-talk: the recorded clip goes to `/api/voice`, which calls `gemini-3.8-flash` (Vertex, audio input) with the same tools and returns text plus speech (browser speech synthesis). Typed chips remain in both cases. The Live system instruction tells the model to speak only numbers returned by tools; the digit filter (section 6.3) applies to the transcript shown on screen, and the ledger notes that spoken audio is not filtered.

## 7. Google Cloud architecture

```
Browser — React app on Firebase Hosting (kirchhoff.web.app)
  ├─ Static demo world: /demo/*.json (seed projects, golden runs, integrations snapshot) — works with backend down
  ├─ Firebase Auth (anonymous) · App Check (reCAPTCHA Enterprise; debug token for Playwright)
  ├─ Firestore onSnapshot (client read-only): visitor workspace runs, events, revisions, findings, approvals
  ├─ Firebase AI Logic → Gemini Live (us-central1), tools → /api
  └─ /api/** rewrite ──► Cloud Run "kirchhoff-api" (Python 3.12, FastAPI, ADK 2.11, asia-south1)
        instance-based billing (--no-cpu-throttling), min 1, max 3, concurrency 20, 2 vCPU / 2 GiB
        ├─ verifies Firebase ID token + App Check token + workspace ownership (except /api/health)
        ├─ ADK workflows on Vertex AI gemini-3.8-flash (global)
        ├─ kirchhoff_engine (pandapower, networkx, shapely, numpy) + rule pack
        ├─ Firestore writes (batched events, leases), Cloud Storage (uploads, exports, large models)
        ├─ /api/enterprise/* proxy to the sandbox (UI never calls the sandbox directly)
        ├─ OpenTelemetry → Cloud Trace (Should)
        └─ /mcp FastMCP (Should): bearer-token auth, sample project only
     Cloud Run "kirchhoff-enterprise" (same image, ERP/CRM sandbox routes; min 0, max 2; Firestore-backed)
  Secret Manager · Cloud Build · uptime checks on / and /api/health · budget USD 200 (alerts 50%, 90%)
```

Load-bearing roles:
- **Gemini:** long-document reading with verified citations, contradiction finding, drawing reading, planning, option and fix choices with reasons, explanations, live voice.
- **ADK on Cloud Run:** multi-agent workflow graphs, tool calling, gates, fix loop. Cloud Run rather than Agent Runtime because the engine needs native scientific Python and runs execute as background phases.
- **Firestore:** real-time event bus, revisions, findings, approvals, audit trail, leases, enterprise sandbox data.
- **Firebase:** Hosting (incl. static demo world), anonymous Auth, App Check, AI Logic for Gemini Live.
- **Cloud Run (two services):** agent/engine API and the enterprise sandbox, showing integration through APIs.

## 8. Engine and rule pack

### 8.1 Model

`kirchhoff_engine` is pure Python, no LLM calls.
- **Electrical:** 33 kV MV board with two incomers and an automatic bus-coupler; transformers (cast-resin, Dyn11) with no-load and load losses; LV main boards (no LV paralleling); UPS systems (500 kW modules, efficiency); UPS output (critical) boards; static transfer switches (block topology); feeders (busway or cable); row busways with tap-offs; racks with two feeds mapped to source systems.
- **Cooling:** CDUs, hydraulic zones, zone headers, row branches, rack manifolds (with rack Δp).
- **Geometry:** hall polygon, 12 × 12 m column grid, keep-out zone, LV rooms, CDU gallery, rack footprints, 3D route polylines on tiers `pipe_low` +2.6 m, `busway` +3.2 m, `pipe_high` +3.8 m.
- **Revision identity:** SHA-256 of canonical model JSON.

### 8.2 Calculations (each unit-tested against a hand calculation)

- Design current `I = P / (√3 · U · cosφ)`.
- Ampacity and ΔV at the worst N-1 (failover) current.
- `ΔU% = 100 · √3 · I · L · (R cosφ + X sinφ) / U`, R at operating temperature; feeder sections factor 1.0; row busway with n equal tap-offs `(n+1)/(2n)`; measured from the UPS output board to the furthest tap-off.
- Short circuit: pandapower `calc_sc` (IEC 60909, max case, `ip=True`) at LV boards, UPS output boards and busways. (Hand estimate: ~61 kA with 2.5 MVA, ~66 kA with 3.15 MVA.)
- Redundancy (generic): each rack has two feeds mapped to source systems. Normal allocation per topology (section 9.3). On loss of any component, affected feeds transfer to the rack's other feed. N-1 passes only if every rack keeps a feed and R01, R02 and R07 pass in that case. networkx graph, not repeated load flows. MV bus faults are out of scope (ledger).
- Transformer load = ((UPS-backed load) / η_UPS + non-UPS load) / cosφ. UPS-backed load = IT + CDU pumps. Aux load is split equally across systems in the normal case; a failed system's share moves with its IT load to the system that picks it up.
- Losses: transformer P0 + Pk·(S/Sn)², UPS P·(1/η − 1), busway I²R.
- `r15_swap(line)`: the requirement is the minimum rating that satisfies R01 for that line's computed normal and worst N-1 loads; candidates are catalogue/ERP items of the same category and voltage with rating ≥ the requirement and (stock ≥ required quantity or lead time ≤ 26 weeks); sorted by (rating, unit price, id); the first candidate for which R01, R04 and R04b pass after re-running short circuit is chosen. Deterministic; the Procurement agent only narrates it.
- Cooling: PG25 fixed at 35 °C (ρ 1,020 kg/m³, cp 3.95 kJ/kg·K, μ 1.5 mPa·s; 25% by mass); `ṁ = Q/(cp·ΔT)`; `v = 4·V̇/(π·D²)`; Darcy–Weisbach + Swamee–Jain; 30% fittings allowance; index circuit = zone header + row branch + rack Δp.
- Spatial: Shapely; clearance to columns; a pipe segment is "above electrical" if its tier is higher than the busway's and its plan projection intersects the busway footprint.
- BOQ and draft PR lines are derived from the model before every Checker run.

### 8.3 Rule pack v0.1 — "IEC-based, illustrative values, not for construction"

| Rule | Check | References |
|---|---|---|
| R01 | Transformer loading ≤ 80% normal and ≤ 100% in every N-1 case | Tender §4.3; IEC 60076-12 |
| R02 | Busway/feeder rating ≥ failover design current | IEC 61439-6; IEC 60364-5-52 |
| R03 | Feeder breakers: `Ib ≤ In ≤ Iz`; `I2 ≤ 1.45 Iz` (met by IEC 60947-2 breakers, I2 = 1.3 In). Incomer and UPS breakers are sized to the transformer/UPS rating and checked by R04 only (ledger) | IEC 60364-4-43 §433.1 |
| R04 | Breaker Icu ≥ prospective Ik″ | IEC 60364-4-43 §434.5.1; IEC 60909-0; IEC 60947-2 |
| R04b | Busway Icw ≥ Ik″ and ipk ≥ ip | IEC 61439-6 |
| R05 | ΔV UPS output board → furthest tap-off ≤ 2.0% at failover current | Tender §4.6; IEC 60364-5-52 §525 |
| R06 | Zero single points of failure | Tender §4.2; ISO/IEC 22237 (EN 50600); TIA-942 |
| R07 | UPS capacity per system ≥ load in every N-1 case; autonomy ≥ 5 min | Tender §4.5 |
| R08 | CDU capacity per zone ≥ zone liquid load with N+1 | Tender §6.2; ASHRAE TC 9.9 |
| R09 | Rack flow ≥ max(OEM minimum, flow for ΔT ≤ 10 K) | Tender §6.1; OEM rack guide |
| R10 | Pipe velocity ≤ 2.5 m/s | Tender §6.4 |
| R11 | No liquid piping above electrical busways; clearance to columns ≥ 300 mm | Tender §6.3.4 |
| R12 | SLD equipment = BOQ lines = PR lines (draft in P3, submitted in P4) | Internal consistency |
| R13 | CDU pumps fed from two independent UPS-backed systems | Tender §6.5 |
| R14 | Index-circuit Δp ≤ CDU available external head | Tender §6.2 |
| R15 | Every equipment line's ERP lead time ≤ tender limit (26 weeks) or in stock | Tender §2.3; ERP data |

### 8.4 Not checked in v0.1 (shown in the ledger)

Earth-fault loop impedance (IEC 60364-4-41 §411), selectivity, arc flash, harmonics, air-side cooling for the air-cooled share, MV bus faults, busway derating above 35 °C ambient (ambient assumed ≤ 35 °C).

Finding status: `pass | fail | warn | n/a`. The total number of checks is counted from the run.

## 9. Sample scenario: Hall A (fictional)

### 9.1 Site and loads

- **Client:** Deccan Compute (fictional). **Site:** AI campus near Hyderabad (fictional).
- **Hall and pinned geometry** (metres; x east, y north; origin at the hall's south-west corner; all routes on the `busway` tier unless stated):

  | Element | Position |
  |---|---|
  | Hall | x 0–60, y 0–36 |
  | Columns | 12 × 12 m grid: x ∈ {0,12,24,36,48,60}, y ∈ {0,12,24,36} (24 columns) |
  | Keep-out (fire-suppression room) | x 10–18, y 10–26 |
  | Rows R1–R6 (N–S, 8 racks each, racks y 15.6–20.4) | centre x = 6, 22, 28, 34, 40, 46 |
  | LV room A (outside east wall, south) | x 60–72, y 0–10; A-side feeder exit (66, 4) |
  | LV room B (outside north wall, centre) | x 24–36, y 36–46; B-side feeder exit (30, 40) |
  | A-side primary corridor | along y = 2; feeders turn north along the row centreline to the row's south end (y 15.6) |
  | B-side primary corridor | along y = 35; feeders turn south along the row centreline to the row's north end (y 20.4) |
  | CDU gallery | inside the hall along the north wall, y 28–33; CDUs CDU-1…CDU-9 in zone order |

  | Busway offsets | each row's A busway at x − 0.3 m, B busway at x + 0.3 m (row centre x) |
  | Feeder bundles (0.4 m pitch, farthest-going outermost) | A side along the south corridor: FA-01 y 2.0, FA-02 2.4, FA-03 2.8, FA-04 3.2, FA-05 3.6, FA-06 4.0. B side along the north corridor: westbound FB-01 y 35.0, FB-02 34.6, FB-03 34.2; eastbound FB-06 y 35.0, FB-05 34.6, FB-04 34.2 |
  | CDU bays (in the gallery) | Z1 x 7–21, Z2 x 28.6–33.4, Z3 x 40.6–45.4 |
  | H-Z2 crossing | H-Z2 runs from the Z2 bay south to R3/R4 and crosses above feeder FB-03 at about y 24 |

  Feeder length = horizontal route + 2 × 3.2 m vertical. Feeders route from their source room's corridor (in DR, a system in room A routes along the south corridor even when it feeds a B busway). Pipe routing default: zone main headers on `pipe_high` (the tier the tender's containment schedule reserves for mechanical mains), row branches on `pipe_low`. Exact header polylines are authored in `scenarios/hall_a/geometry.yaml` so that exactly one header segment (H-Z2) crosses above an electrical run (feeder FB-03) in plan; the regression test locks this.
- **Id scheme:** rows R1–R6; row busways A-01…A-06 and B-01…B-06; feeders FA-01…FA-06 and FB-01…FB-06; LV boards A1–A3, B1–B3; zones Z1 (R1–R2), Z2 (R3–R4), Z3 (R5–R6); headers H-Z1…H-Z3.
- **IT:** 48 racks, 6 rows × 8, 600 × 1,200 mm, 132 kW each (GB300 NVL72-class), 6.336 MW. Heat split 80% liquid / 20% air as a tender assumption (OEM figures closer to 90/10; ledger notes it).
- **Aux on the LV system:** 0.30 MW total (CDU pumps 9 × 15 kW UPS-backed; fan walls; controls); in 2N that is 0.05 MW per board normal, 0.10 MW failover.
- **Power:** 33 kV MV board with incomers A/B and bus-coupler; source fault level 1,000 MVA, R/X 0.1; 415 V, 50 Hz, cosφ 0.95; each row has an A and a B busway (12 row busways).

### 9.2 Tender clauses (authored by us)

§2.3 equipment on site ≤ 26 weeks from award · §4.2 "2N" · Appendix B "block or distributed redundancy acceptable" (the deliberate contradiction) · §4.3 transformer loading ≤ 80% normal, ≤ 100% under any single failure · §4.5 UPS autonomy ≥ 5 min · §4.6 ΔV ≤ 2.0% UPS output → tap-off at worst-case current · §6.1 supply 30 °C, ΔT 10 K · §6.2 CDUs N+1 per zone, index Δp within CDU head · §6.3.4 no liquid above electrical · §6.4 velocity ≤ 2.5 m/s · §6.5 continuous cooling from two independent UPS-backed supplies.

### 9.3 Topology inputs (all generated from the same 12 busways)

| Option | Systems | Busway mapping | Normal / failover allocation | Transformers (after R15 swap) | Installed |
|---|---|---|---|---|---|
| 2N | Boards A1–A3 (room A), B1–B3 (room B) | A1 → A-01, A-02; A2 → A-03, A-04; A3 → A-05, A-06; same pattern for B | 50/50; survivor takes 100% | 6 × 3.15 MVA | 18.9 MVA |
| Distributed redundant (4-to-make-3) | Systems S1, S2 (room A), S3, S4 (room B) | pairs in lexicographic order (S1,S2), (S1,S3), (S1,S4), (S2,S3), (S2,S4), (S3,S4) map to R1…R6; the lower-numbered system feeds the row's A busway, the higher its B busway (3 busways per system) | 50/50; on loss the 3 partners each take one extra half-row | 4 × 3.15 MVA | 12.6 MVA |
| Block redundant (3 + 1) | Blocks K1–K3 (room A), reserve KR (room B) | K1 → A-01, A-02; K2 → A-03, A-04; K3 → A-05, A-06; each B busway is fed from KR's critical board through its own STS (preferred source KR UPS, alternate KR bypass) | rack PSUs draw from the A feed while it is healthy (ledger assumption); KR carries 0 normally and takes a failed block | 4 × 3.15 MVA + 6 STS | 12.6 MVA |

In the scenario regression, every option is generated and checked through P3 and must reach all-pass within 2 fix iterations; a live run only takes the selected option through P3. Only 2N is the golden-run path.

### 9.4 Catalogue (`scenarios/hall_a/catalogue.yaml`)

- Transformers: 2.5 MVA (uk 6%, P0 3.5 kW, Pk 21 kW) and 3.15 MVA (uk 7%, P0 4.2 kW, Pk 25 kW); cast-resin Dyn11. (Illustrative values.)
- Busways 1,600 / 2,000 / 2,500 A with R, X at operating temperature (1,600 A: R·cosφ + X·sinφ ≈ 0.0395 mΩ/m; 2,000 A ≈ 0.030 mΩ/m), Icw 85 kA (1 s), ipk 187 kA.
- Breakers: ACB frames 1,600 / 2,000 / 2,500 / 4,000 / 5,000 A with adjustable In; Icu 100 kA, Ics 100%; I2 = 1.3 In; all in ERP stock. Model positions: transformer LV incomer (5,000 A frame for 3.15 MVA, 4,000 A for 2.5 MVA), UPS input, critical-board incomer, one feeder breaker per busway feeder.
- UPS: 500 kW modules, η 97%, frames up to 6 modules; battery autonomy 7 min at full module load. STS 1,600 A.
- Parallel-cable feeder option: 8 × 1C 240 mm² Cu per phase (R 0.0958 mΩ/m, X 0.08 mΩ/m per conductor at 90 °C; group rating 2,500 A after derating; illustrative).
- CDU: 1,200 kW at ΔT 10 K, 150 kPa available external head, 15 kW pump.
- Pipes: DN100/150/200 with internal diameters (DN150 154 mm, DN200 206 mm). Rack + manifold Δp 60 kPa. OEM minimum rack flow 71 L/min.

### 9.5 ERP and CRM seed

- Transformer 2.5 MVA: stock 0, lead time 98 weeks. Transformer 3.15 MVA: stock 6, 12 weeks for more. Every other line the design can use (UPS modules, busways incl. 2,000 A, STS, CDUs, pipes, breakers, cables) is in stock in sufficient quantity or ≤ 26 weeks, so only the transformer fails R15 (generator constraint, asserted by a test). The sandbox does not decrement stock when PRs are created. Prices and vendors for all (section 13 adds the wider catalogue).
- CRM: "Hall A design-build" is seeded at "Design approved" (Hall A is already signed). "Hall B design-build" is seeded at "Design in progress" and moves to "Design approved" when a visitor signs Hall B (stored as the visitor's overlay).

### 9.6 Verified numbers (hand-calculated 13 Oct; locked by the scenario regression test Tue 14 Oct)

- Rack 193 A; row busway 773 A normal / 1,546 A failover (97% of 1,600 A; ambient ≤ 35 °C, no derating).
- Transformer loading (incl. UPS losses, section 8.2): 2N board 2,399 kVA in failover → 2.5 MVA: 48% normal / 96% failover (passes R01) → R15 fails (98 weeks) → `r15_swap` picks 3.15 MVA: 38% / 76%.
- DR: 2.5 MVA 72% / 96%; 3.15 MVA 57% / 76%. Block: 2.5 MVA 96% normal (fails R01, never offered); 3.15 MVA 76% / 76%.
- Short circuit (hand estimate; pandapower is authoritative): Ik″ ≈ 61 kA with 2.5 MVA, ≈ 66 kA with 3.15 MVA; ip ≈ 167 kA ≤ busway ipk 187 kA; Icu 100 kA.
- UPS per 2N board in failover ≈ 2.16 MW → 5 × 500 kW modules.
- ΔV (1,600 A busway ≈ 0.0255 %/m at failover; row busway adds ≈ 0.07%): FA-01 82 m → **2.16% (fails R05)**; FA-02 66 m → 1.75%; FA-03…FA-06 1.60–1.14%; FB-01…FB-06 1.34–0.78%. Fix candidates for FA-01: upsize to 2,000 A busway → 1.66%; parallel cable feeder → 0.84%. Both pass; re-feeding from another board is not offered because it would overload that board (R01).
- Cooling: 105.6 kW liquid per rack → 157 L/min (≥ OEM 71). Zone = 2 rows = 1.69 MW → N = 2, N+1 = 3 per zone, 9 CDUs. Zone header DN200 1.26 m/s; row branch DN150 1.13 m/s. Index Δp ≈ 70 kPa ≤ 150 kPa.
- The **zone-2 main header** H-Z2 on `pipe_high` crosses above feeder FB-03 at about y 24 (fails R11); fix: a local drop to `pipe_low` at the crossing (or reroute). H-Z1 and H-Z3 cross no electrical run.
- Golden option (2N) first pass yields exactly two findings: R05 (FA-01) and R11 (H-Z2 over FB-03). DR's first pass fails R05 on both R1 feeders (both from room A, ≈ 82 m); block's first pass matches 2N's.
- What-if 200 kW (frozen equipment): row busway 2,343 A (fails R02), 2N board 3,579 kVA = 114% of 3.15 MVA (fails R01), zone liquid 2.56 MW > 2.4 MW N capacity (fails R08); R03, R05, R07 and R09 also fail. Regression asserts at least R01, R02, R08.

## 10. Asset packs (thin, user-requested)

Both reuse the shell, Checker, finding drawer and revision timeline, with one Asset agent. Maps are static SVG by default; Google Maps JS API only if time allows.
- **Grid:** 132 kV double-circuit line, ~18 km, to the campus substation (2 × 50 MVA 132/33 kV). Three ACSR conductors compared on ampacity, voltage regulation and I²R losses; pandapower fault level at the connection point; mini SLD.
- **Solar:** ~5 MWp ground-mount field on a polygon beside the hall; pvlib clear-sky yield (no runtime weather API); string sizing from module Voc at minimum site temperature vs inverter max DC voltage; table layout with Shapely.

## 11. Reliability and judging-window operations

- **Judge's first 10 seconds:** landing has one primary CTA, "Enter the demo workspace (no login)" → welcome screen → guided tour (section 13.5). "Run it live" and "Replay a recorded run" are secondary.
- **Static first:** seed projects (including the signed Hall A) and an integrations snapshot load from static JSON on Hosting, so browsing never depends on Cloud Run, Gemini or App Check. Browsing never reads Firestore `seed/*`; those collections serve the API only.
- **Live runs:** "Run it live" designs **Hall B**, which has inputs identical to Hall A's (same tender, drawing and catalogue), in the visitor's own workspace. The scenario regression therefore covers Hall B.
- **One bundle format:** the UI renders everything from a `ProjectBundle` (section 14), loaded either from static JSON (seed projects, replay) or assembled live from Firestore by an adapter.
- **Golden capture:** `scenarios/hall_a/capture.py` exports a completed Hall B run as a `ProjectBundle`, rewrites ids, authors (Priya Raman signs) and timestamps to Hall A, recomputes revision hashes and every `approval.rev`, and hands the result to the demo-world generator, which derives Hall A's PRs and the integrations snapshot from it. Seed ERP PR ids and Hall A's PRs therefore always agree.
- **Limits:** global cap of 3 concurrent live runs (overflow offered replay); 5 runs per visitor per hour.
- **Gemini:** retries with backoff, per-agent timeouts, structured-output validation with one repair attempt. Vertex Gemini runs on Google's shared pay-as-you-go capacity, so no per-project quota request is needed; 429s are retried with backoff.
- **Firestore writes:** events batched ~250 ms; `runs/{rid}` ≤ 1 update/s (lease heartbeats included); event docs < 10 KB; models > 500 KB to Cloud Storage with hash pointer; single writer assigns `seq` per phase.
- **Monitoring:** uptime checks on `/` and `/api/health`; budget USD 200 with 50%/90% alerts.
- **Freeze:** golden path frozen Thu 16 Oct 22:00 IST; post-submission changes only via tagged releases, deployed with no runs active.

## 12. UI design

Dark, dense, Linear/Vercel-like; one accent per agent; monospace numerals; Inter. Effects only on landing. Motion shows progress (staging, matrix fill, diff recolour) and respects `prefers-reduced-motion`. Status uses icon + text, never colour alone. WCAG AA contrast; full keyboard access.

**Screens:**
1. **Landing:** statement, primary CTA, Run live / Replay.
2. **Projects dashboard** (section 13.2): project cards by asset pack and state, activity feed, team.
3. **Workspace:**
   ```
   ┌ Kirchhoff ▸ Deccan AI Campus · Hall A (sample)  [Asset pack ▾] ●agents [Ask|Auto] [Request sign-off] ┐
   ├─────────────┬──────────────────────────────────────────────┬───────────────┤
   │ Agent lanes │ [3D Hall] [SLD] [Matrix] [Options] [Docs]    │ Co-pilot      │
   │ ● Intake ✓  │                                              │ plan · ask    │
   │ ● Layout ✓  │   canvas: checker highlights, diff recolour  │ what-if chips │
   │ ● Power ⋯   │                                              │ voice         │
   │ ● Cooling ⋯ │                                              │ citations     │
   │ ● Procure ✓ │                                              │               │
   │ ● Checker ✕2│                                              │               │
   ├─────────────┴──────────────────────────────────────────────┴───────────────┤
   │ Revisions  r1 (2 fail) ── r2 ✓ ── signed by Priya Raman (Reviewer)          │
   └─────────────────────────────────────────────────────────────────────────────┘
   ```
4. **Plan gate:** steps with owners, Intake's open questions, Approve.
5. **Options:** three cards with installed MVA, normal and failover loading, cost, losses, max lead time, swaps applied; select.
6. **Finding drawer:** rule, clause chips, tender chip (PDF at the pdfplumber box), formula with inputs, value vs limit bar, explanation, chosen fix and rejected alternative with their deltas, "show on canvas".
7. **Review page:** diff, assumptions ledger incl. "not checked", findings summary, Approve with stamp (name, role, time, revision hash). Visitor stamps read "You (Demo Reviewer)".
8. **Integrations** (section 13.3).
9. **Grid** and **Solar** asset-pack screens.

**SLD:** racks grouped per busway; stages in by level (MV → transformers → boards → UPS → busways → rack groups). **3D:** instanced racks; tube geometry for busways and pipes on their tiers; column grid; keep-out volume; coloured by status. No agent cursors.

**Libraries:** Vite + React + TypeScript, Tailwind + shadcn/ui, Motion, @xyflow/react + elkjs, @react-three/fiber + drei, react-pdf, TanStack Table, a spotlight-tour component built in-house on shadcn Popover, Firebase JS SDK 13 (Auth, Firestore, App Check, AI Logic).

## 13. Demo world and onboarding

### 13.1 Organisation (all fictional; banner "Demo workspace — all companies, people and data are fictional")

- **Firm:** Meridian Power Engineering, a data-centre and grid EPC contractor.
- **People:** Priya Raman (Lead Electrical Engineer, Reviewer), Arjun Mehta (Design Engineer), Kavya Iyer (Cooling Engineer), Rohan Das (Procurement Lead), Neha Kapoor (Account Manager). The visitor is "You (Demo Reviewer)".
- **Clients (CRM accounts):** Deccan Compute, Narmada Transmission, Suryodaya Renewables, Konkan Cloud, Vindhya Steel.

### 13.2 Projects

| Project | Asset pack | State | Source | Must/Should |
|---|---|---|---|---|
| Deccan AI Campus · Hall A | AI data hall | Signed (hero): 2 revisions, findings, approval, PRs, CRM update | Golden run JSON | Must |
| Deccan AI Campus · Hall B | AI data hall | Not started — "Run it live" target (twin of Hall A) | Live in visitor workspace | Must |
| Konkan Cloud · Pune Edge Phase 1 | AI data hall | Signed 2 weeks ago; PRs issued | Precomputed JSON | Should |
| Deccan campus · 132 kV intake | Grid | Checked | Precomputed JSON (asset pack can re-run) | Should |
| Deccan campus · 5 MWp solar | Solar | Draft | Precomputed JSON (asset pack can re-run) | Should |
| Vindhya Steel · Mill LV upgrade | — | Archived, read-only | Precomputed JSON | Should |

Each carries realistic timestamps over the past 6 weeks, authors from the team, comments and activity entries.

### 13.3 Integrations page

Connected systems with status, last sync, record counts and a "View data" drawer. Labels say "sandbox (simulated)" except Google services.

| Integration | Type | Seeded data |
|---|---|---|
| ERP (SAP-style) | Sandbox (`kirchhoff-enterprise`) | ~60 materials (transformers, boards, busways, UPS, STS, CDUs, pipes, breakers, cables) with stock, lead times, prices, vendors; ~15 historical PRs |
| CRM (Salesforce-style) | Sandbox | 5 accounts, 9 opportunities across stages with values and next steps |
| Document store | Cloud Storage (real) | Tender PDFs, drawings, calc reports, BOQs for every project |
| Notifications | Sandbox | In-app inbox of approval and finding notifications |
| PLM | "Coming soon" card | Roadmap only |

Seed data comes from deterministic generators in `scenarios/demo_world/` (fixed random seed). If the API is unreachable, the page renders the static integrations snapshot with a "showing cached snapshot" note.

### 13.4 Per-visitor workspace

Shared seed data is read-only (static JSON for the browser; Firestore `seed/*` for the API). Each anonymous visitor gets `workspaces/{uid}` holding only what they change: live runs on Hall B, revisions, findings, approvals, PRs they create, CRM stage overlays. Tour and checklist progress live in the browser's localStorage, so they work with the backend down. "Reset demo workspace" deletes the visitor's Firestore overlay and clears localStorage.

### 13.5 Onboarding

- **Welcome screen (first visit):** one sentence on Kirchhoff; "Take the 2-minute tour" (primary) or "Explore on my own".
- **Guided tour (spotlight, skippable, restartable from "?"):**
  1. Projects dashboard — "Your firm's live projects."
  2. Hall A signed design — "Every number is checked and cited." (matrix row)
  3. Finding drawer — open a finding; click the tender chip; PDF jumps to the clause.
  4. Agent lanes / run history — "{n} agents designed this; here's what each did." (n counted from the bundle)
  5. What-if chip — "Try it: racks to 200 kW." (< 3 s)
  6. Integrations — "Approval pushed these PRs to ERP and moved the CRM deal."
  7. Hall B — "Now run it live yourself." (or replay)
- **Getting-started checklist** (bottom-left, progress per visitor): open a signed design · inspect a finding and its source · run a what-if · ask the co-pilot (voice or text) · run Hall B live · approve a revision.
- **Contextual hints:** explanatory empty states; one-line first-hover tips on lanes, gates and the Ask/Auto switch.
- **Keyboard:** `?` shortcuts and tour; `g p` projects; `g i` integrations.

### 13.6 Scope split

- **Must:** organisation and people, Hall A (signed) and Hall B (live target), projects dashboard, Integrations page with ERP and CRM sandbox data and Cloud Storage documents, welcome screen, guided tour, checklist, per-visitor workspace, reset, fictional-data banner.
- **Should:** the other four projects, notifications inbox, activity feed depth, keyboard shortcuts.

## 14. Data model and security

**ProjectBundle** (one schema, defined once in Pydantic and generated to TypeScript): `{project, runs[], events[], steps[], revisions[] (model inline or modelUrl), findings[], approvals[], prs[], crmOverlay, whatIfs[] (precomputed chips, seed bundles only)}`. Two adapters produce it: static JSON (seed projects, replay) and Firestore (visitor workspace).

```
(static, Hosting)  /demo/world.json · /demo/projects/{pid}.json (ProjectBundle) · /demo/integrations.json
seed/erp_materials/{mid}            category, rating, stock, leadTimeWeeks, unitPrice, vendor      (API read-only)
seed/erp_prs/{prid}                 historical PRs incl. Hall A's                                   (API read-only)
seed/crm_opportunities/{oid}        account, stage, value, nextStep                                 (API read-only)
workspaces/{uid}                    createdAt, lastRunAt
workspaces/{uid}/runs/{rid}         projectId, status (running|at_gate|done|expired|failed), autonomy, phase, lease{owner, attempt, heartbeatAt}, plan[], openQuestions[], metrics, startedAt, finishedAt
workspaces/{uid}/runs/{rid}/steps/{stepId}   phase, status, done, attempt, outputsRef, startedAt, finishedAt
workspaces/{uid}/runs/{rid}/events/{eid}   seq, phase, step, attempt, agent, kind, title, detail, payload (<10 KB), ts
workspaces/{uid}/revisions/{rev}    projectId, parentRev, author, hash, model | modelRef, summary, checkSummary, status, ledger[]
workspaces/{uid}/revisions/{rev}/findings/{fid}   rule_id, element_id, clause_refs, tender_refs, formula, inputs, value, limit, unit, status, explanation, fix, rejected_fix
workspaces/{uid}/approvals/{aid}    rev, approverName, role, decision, comment, ts
workspaces/{uid}/prs/{prid}         rev, lines[], status, createdAt
workspaces/{uid}/crm/{oid}          stage overlay
```

- **Firestore rules:** clients read only their own `workspaces/{uid}/**`; `seed/*` is not client-readable; all client writes denied. Every mutation goes through `/api`.
- **API auth:** `kirchhoff-api` is public (Hosting rewrites need it) and verifies the Firebase ID token, App Check token and workspace ownership on every call except `/api/health`. `/mcp` uses a bearer token and serves only the sample project.
- **Storage rules:** visitor exports readable by their owner; seed documents public-read; writes only via API signed URLs.

## 15. Repository layout

```
kirchhoff/
  apps/web/                 React app (incl. public/demo/*.json built from scenarios)
  services/api/             FastAPI + ADK workflows + kirchhoff_engine + rule pack + enterprise routes + tests
  scenarios/hall_a/         tender PDF, hall DXF/PDF, catalogue.yaml, ERP/CRM seed, golden-run capture
  scenarios/demo_world/     organisation, projects, integrations seed generators (fixed seed)
  infra/                    firebase.json, firestore.rules, storage.rules, deploy scripts, monitoring/budget setup
  docs/                     architecture, submission brief, this spec
```

GitHub repo created private, made public before submission.

## 16. Testing

- **Engine:** pytest per calculation against section 9.6 values.
- **Rule pack:** passing and failing fixture per rule.
- **Scenario regression (Tue 14 Oct):** golden option (2N) first pass yields exactly R05 (FA-01, ΔV in [2.1%, 2.4%]) and R11 (H-Z2 over FB-03); both fix candidates for each pass with no new failures; `r15_swap` deterministically picks 3.15 MVA and only transformer lines fail R15 before the swap; DR and block each reach all-pass within 2 fix iterations; re-checking the signed model with rack load set to 200 kW (equipment frozen) fails at least R01, R02, R08 (Tue, via `check` on a load-modified model; the `what_if` facade lands Thu).
- **Capture determinism:** `capture.py` + demo-world generator produce the same Hall A bundle and integrations snapshot hash from the same Hall B run.
- **Seeded-fault benchmark:** ~30 mutated designs → catch rate and false positives.
- **Intake scoring:** extraction vs ground truth; citation resolution rate.
- **Agents:** schema tests with recorded Gemini responses; one live smoke run per day.
- **Demo world:** generator determinism test (same seed → same JSON hash).
- **End to end:** Playwright on the deployed URL (welcome → tour → Hall A finding → what-if → Integrations → Hall B live run through all gates → sign-off → PR visible), App Check debug token; before each deploy and daily during judging.

## 17. Schedule (4 workstreams: WS1 engine + scenarios; WS2 agents + API; WS3 web UI; WS4 infra + enterprise sandbox + demo world)

| Day | WS1 | WS2 | WS3 | WS4 |
|---|---|---|---|---|
| **Mon 13** | Spec review done; implementation plan; repo scaffold; engine model types + catalogue.yaml + geometry.yaml | Tender PDF, hall DXF + PDF plot and intake ground truth (scenario authoring) | Shared schemas frozen (Pydantic → TypeScript: ProjectBundle, events, findings) and UI fixtures | Hello world end to end (Hosting → Cloud Run → Firestore events in browser); infra already provisioned (Auth, bucket, App Check key) |
| **Tue 14** | Electrical calcs, short circuit, redundancy, cooling, routing; rule pack R01–R15 + tests; `r15_swap`; regression lock | Intake (verified citations, contradiction, scoring); P1/P2 workflows; steps, leases, resume; event streaming | App shell, landing, dashboard, workspace layout; SLD and 3D on fixtures; welcome screen | Enterprise sandbox service + seed; demo-world generators; Procurement tools; Firestore/Storage rules; uptime + budget alerts |
| **Wed 15** | Seeded-fault benchmark; asset-pack engines (grid, solar) | P2 option gate, P3 fix loop, P4, Docs (stubbed exports); full P1–P4 live run; workspace create/reset and run limits API | Matrix, finding drawer + PDF citations, options cards, gates, revisions + diff; tour + checklist | Integrations page + API proxy; capture.py. Evening: record a full run |
| **Thu 16** | What-if engine + impact chain; precomputed chip what-ifs | Co-pilot + voice (Live + push-to-talk); Asset agent; Docs exports (PDF, BOQ) | Review/sign-off page, what-if UI, asset-pack screens, polish | Golden capture → static Hall A + demo world; Should items by value; Playwright. Checkpoint 18:00; freeze 22:00; record |
| **Fri 17** | Record 09:00; deck; video < 3:00; brief; repo public; submit by 20:00 IST | | | |
| **Sat 18** | Buffer only | | | |

## 18. Risks

| Risk | Mitigation |
|---|---|
| ADK details beyond the spike | Phases are small graphs; fallback to plain `google-genai` function calling with the same phase shape |
| Gemini Live retirement / App Check | Push-to-talk fallback; typed chips; App Check from day 0 |
| Run latency | Parallel branches; engine-heavy; stream partial results; replay; time-compressed, labelled video footage |
| UI scope (workspace + demo world + onboarding) | Fixed component catalogue; static JSON for seed projects; cut order in section 5; daily recordings |
| Copyrighted tables | Clause numbers only; illustrative catalogue values |
| Deployment breaks during judging | Static-first browsing, leases + resume, uptime alerts, freeze, deploy only with no active runs |
| Over-claiming | Measured metrics only; "fictional", "sandbox (simulated)", "illustrative, not for construction" labels |

## 19. Submission deliverables

- Deck in the 16-slide template (team, idea, opportunities/USP, features, process flow, wireframes, architecture, technologies, cost, snapshots, benchmarks, future development, links).
- Video under 3:00 per section 3.
- Live URL, public GitHub repo, brief (section 7 is its source; states why Cloud Run over Agent Runtime and why native PDF input with verified quotes over File Search).
- Benchmarks slide uses only section 4's measured values.

## 20. Bids inbox (added 14 Oct, user-approved; Should, after Must items)

**Why:** an EPC bid starts in a shared `bids@` mailbox, not in an upload box. The inbox is Kirchhoff's front door: "the first step of a bid, handled before anyone opens the email". It reuses Intake, the trust rules, the CRM sandbox and the demo world.

**What:**
- **Mailbox (sandbox, simulated):** `bids@meridian-power.example` holds about 6 seeded emails in the demo world:
  1. Deccan Compute: Hall B tender (tender PDF, hall drawing, one addendum). This is the live target.
  2. Konkan Cloud: a clarification reply on the existing Pune Edge project.
  3. A forwarded chain with a scanned BOQ (image PDF).
  4. Narmada Transmission: a 400 kV substation request (outside appetite).
  5. A vendor brochure (not a bid).
  6. Suryodaya Renewables: a solar EPC enquiry (in appetite, thin).
- **Inbox agent** (Gemini 3.8 Flash, multimodal, low thinking):
  - Classifies each attachment: tender, drawing, addendum, BOQ, brochure or other.
  - Links the email to a CRM account and opportunity, or proposes a new one.
  - Extracts client, site, asset type, MW, redundancy, bid due date and lead-time clause. Extraction follows §6.3 trust rules: verbatim quotes are verified with pdfplumber where the PDF has text, and scanned pages are marked "unverified (scan)".
- **Fit check (deterministic, no LLM):** rules from `world.yaml` give a verdict of Pursue / Clarify / Decline, each with its reasons.
  - The rules cover asset packs the firm does, MW range, regions, and days to the bid deadline.
  - The **day-zero supply check** applies R15 logic before bidding. It sizes the transformer implied by the extracted MW and redundancy and checks its ERP lead time against the tender's lead-time clause. Example: "26-week limit; the 2.5 MVA unit is 98 weeks; expect an in-stock swap".
- **Pursue** creates the project and moves or creates the CRM opportunity at "Qualification" (the existing CRM stage; no stage is renamed). For Hall B it then opens the normal Intake flow.
- **Static first:** triage results for all seeded emails are precomputed (run once with the real agent, then frozen into the demo bundle). A live "Triage" button exists only on the Hall B email.

**Cut line (checkpoint Thu 16 Oct 12:00 IST):** if Must items are behind, ship only the static inbox page with precomputed triage. Drop the live Triage button and the endpoint.

**Video:** the 0:10–0:30 beat becomes "the tender lands in the bids inbox; Kirchhoff triages it, checks fit and supply, and opens the project". The intake card stream follows.
