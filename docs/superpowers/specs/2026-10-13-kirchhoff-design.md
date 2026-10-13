# Kirchhoff — design spec (v2)

**Product:** Kirchhoff, by team Ordinal (Mehul Arora, lead; Jaydratha).
**One-liner:** Kirchhoff turns weeks of scarce senior-engineer work into one reviewed, signed design session. Gemini agents read the tender, design power and cooling for an AI data hall, and hand off to procurement and sales; a deterministic checker proves every number; the engineer decides and signs.
**Tagline:** *AI designs. Physics checks. An engineer signs.*
**Target:** Google Cloud × Hack2skill AI Builder Cup 2026, theme *Future of Work & Enterprise Productivity*. Secondary: Hitachi Startup Challenge 2026 (Smart Engineering).
**Date:** 2026-10-13 (v2 after review round 1). **Submission due:** 18 Oct 2026; internal deadline Fri 17 Oct, 20:00 IST.

---

## 1. Constraints that shape everything

| Constraint | Source | Consequence |
|---|---|---|
| Submissions close 18 Oct 2026 | aibuildercup.com | ~4 build days. One golden path that must work live. |
| Video strictly under 3:00 | Official T&C | Storyboard targets 2:40 with burned-in captions. |
| Fresh code only, written during the hackathon | Official T&C | New repo `kirchhoff`, first commit 13 Oct 2026. Nothing reused from other team repos. Open-source libraries are fine. |
| Gemini/Gemma or Google agent platforms; deploy on Cloud Run/Firebase; brief explains Firebase, Firestore, Cloud Run, Gemini | Rules + submission instructions | Each is load-bearing (section 7). |
| Live URL must work through judging (19 Oct – 6 Nov) | Rules | Phased runs, replay from static files, uptime check, budget alert (section 11). |
| Judging 40/25/25/10; side prizes incl. Best use of Google Cloud AI and Best UI/UX | T&C | Multi-agent ADK graph, visible verification, measured impact, premium UI. |
| Models on project `ordinal-mep` (probed 13 Oct) | Direct API calls | `gemini-3.8-flash` (GA) works on Vertex global. `gemini-3.1-pro-preview` and `gemini-3.8-flash-lite` return 404; not used. |
| Live voice: Firebase AI Logic Live is Preview; `gemini-live-2.5-flash-native-audio` retires around Oct–Dec 2026; App Check becomes mandatory for AI Logic on 2 Nov 2026 | Firebase docs | Voice spike and App Check setup happen on day 0. Target `gemini-3.8-live`. Typed what-if is the guaranteed path; voice is a layer on top (section 6.4). |
| Firebase Hosting → Cloud Run rewrites time out at 60 s | Firebase docs | Every `/api` call returns in under 10 s; long work runs in background phases (section 6.2). |
| ADK 2.11 verified | Spike, 13 Oct | `Workflow(edges=[...])` with `LlmAgent` + tools ran live on `gemini-3.8-flash` in 5.7 s. Env: `GOOGLE_GENAI_USE_VERTEXAI=true`, `GOOGLE_CLOUD_PROJECT=ordinal-mep`, `GOOGLE_CLOUD_QUOTA_PROJECT=ordinal-mep`, `GOOGLE_CLOUD_LOCATION=global`. |
| Max 4 parallel subagents during the build | User rule | At most 4 workstreams. |
| User asked for thin Grid and Solar slices | User | Both ship as small "asset packs" (section 10). |

## 2. Why this wins

### 2.1 Theme fit (Future of Work & Enterprise Productivity)

| Theme words | What Kirchhoff does, visibly |
|---|---|
| Access knowledge | Every requirement and every number links to the tender sentence it came from and the formula/clause behind it. The engineer can ask "why?" in text or by voice. |
| Collaborate | Humans and agents work in one live workspace. A Designer prepares, a Reviewer signs. Engineering, procurement and sales hand off in one flow. |
| Make decisions | Three costed topology options, lead-time trade-offs, and what-if before committing. Decisions are recorded with who, when and why. |
| Execute workflows | Tender PDF → checked design → signed revision → BOQ → purchase requisitions in ERP → CRM opportunity update. |

**Persona:** Priya, lead electrical engineer at a data-centre EPC contractor. She has two juniors, three hall packages due this month, and a client who keeps changing rack density. Kirchhoff lets her review instead of draft.

### 2.2 What the competition lacks

Competitor teardown (`../../research_notes/AI MEP design competitors and UX/`, report at `../../reports/AI MEP design competitors and UX.md`):
- Endra Power Studio (launched 16 Sep 2026) places, circuits and sizes a whole building in about a second, but cites no clauses, has no independent checker, and shows no data-centre features (busways, CDUs, redundant power topologies).
- Nobody couples data-hall electrical design with liquid-cooling hydraulics, shows clause-cited findings on the canvas, keeps SLD/BOQ/PRs consistent, designs around ERP lead times, or shows a cross-discipline impact chain.

### 2.3 Innovation, ranked for the deck

1. **Design around what can ship.** The Procurement agent reads ERP lead times during design; the engine re-sizes around in-stock equipment (98-week transformer → in-stock alternative). This is speed-to-power, not just speed-to-drawing.
2. **Power and cooling as one model.** The Checker catches coolant piping routed above live electrical, a clash no single-discipline tool sees.
3. **AI designs. Physics checks. An engineer signs.** The verdict path contains no LLM. Gemini reads, plans, chooses and explains; a deterministic engine computes and checks; a human signs.
4. **Cross-document consistency and impact chains.** SLD, BOQ and purchase requisitions agree by construction (R12); a what-if lights up every downstream failure across both disciplines.

## 3. The 2:40 demo storyboard

Burned-in captions throughout. Footage is the real product; no rendered "AI art". The single most memorable moment is liquid caught above live electrical, then fixed.

| Time | Beat | On screen | Caption / voice line |
|---|---|---|---|
| 0:00–0:10 | Cold open | 3D hall: a coolant header glows red where it crosses a busway; a clause chip appears; the header drops a tier and turns green. | "This is a 6 MW AI data hall. One pipe in the wrong place floods the power. Kirchhoff caught it." |
| 0:10–0:30 | Intake | Drop the tender PDF and hall drawing. Requirement cards stream in with "✓ quote verified in PDF". Click one chip: the PDF opens at the highlighted clause. Intake flags a contradiction: §4.2 requires 2N, Appendix B allows block redundancy. | "Gemini reads the whole tender, cites every requirement, and spots where the client contradicts itself." |
| 0:30–0:40 | Plan gate | The plan appears with the open question. The engineer answers ("evaluate both, keep zero single points of failure") and approves. Ask/Auto switch visible. | "The engineer stays in charge of decisions." |
| 0:40–1:10 | Agents | Lanes animate: Layout places 48 racks; Power and Cooling work in parallel; Procurement flags "2.5 MVA transformer: 98-week lead time, 0 in stock" and proposes "3.15 MVA: 6 in stock". Option cards: 2N, distributed redundant, block redundant, with cost, worst failover loading, losses, lead time. Engineer picks. SLD stages in; busways and pipes route in 3D. | "Specialist agents design power and cooling together — around equipment that can actually ship." |
| 1:10–1:40 | Checker | Matrix fills to N checks (N counted live). Two fail. Open "coolant header above busway B-03" (R11): clause, tender chip, geometry. The Cooling agent drops the header to the low tier. "+1 more": far-row feeder voltage drop 2.3% > 2%; the Power agent weighs re-feed vs upsize (cost, ΔV) and picks one with a one-line reason. Diff recolours changed elements. All green. | "Gemini designs. Physics checks. The AI can't mark its own homework." |
| 1:40–1:58 | What-if | Engineer asks by voice (or taps the chip) "What if racks go to 200 kW?". Impact chain lights up: rack → busway → LV board → transformer, and rack → CDU zone, in two colours. | "Ask what-if and see everything that breaks, across disciplines, in seconds." |
| 1:58–2:18 | Sign-off and handoff | Review page: diff, assumptions ledger ("did / assumed / not checked"), Reviewer stamp with revision hash. Purchase requisitions appear in the ERP sandbox; CRM opportunity moves to "Design approved". | "Engineering, procurement and sales: one workflow." |
| 2:18–2:28 | Asset packs | Quick switch: Grid pack (132 kV feeder on a map, conductor choice) and Solar pack (PV field with strings). | "Same engine, new asset packs." |
| 2:28–2:40 | Proof | Four measured numbers (section 4) and the architecture diagram held for 8+ s; URL. | "Built on Gemini, ADK, Cloud Run, Firestore and Firebase." |

Every failure shown is computed live by the engine on the sample inputs. The sample hall is chosen to exercise the checker; outcomes are never hard-coded.

## 4. Impact metrics (measured, not claimed)

Shown on the Benchmarks slide and in the video's proof beat:
1. **Time to a checker-clean revision:** wall-clock from upload to all-pass revision, median of 5 live runs.
2. **Intake accuracy:** requirements extracted correctly vs ground truth (we authored the tender, so ground truth exists); share of citations that resolve to the right clause.
3. **Checker catch rate:** on a seeded-fault benchmark of ~30 mutated Hall A designs covering R01–R14, report detected faults and false positives.
4. **Cost per design:** Gemini tokens and dollars per full run.

**Baseline:** a cited industry range for producing a first coordinated electrical package (from the research notes; 4–8 weeks for good-for-construction drawings in India, with the 30-day first-design figure labelled as a practitioner estimate). Claims are scoped as "concept-stage design with illustrative rules".

**Business number:** "transformer lead time 98 → 12 weeks by designing around stock (sandbox data)".

## 5. Scope

**Must:**
- Hall A sample scenario: tender PDF, hall DXF and PDF plot, equipment catalogue, ERP seed (section 9).
- Intake agent with verified citations and a flagged contradiction.
- Plan gate, option gate, review gate; Ask/Auto switch.
- Phased agent runs streamed live via Firestore (section 6).
- Engine and rule pack R01–R14 (incl. R04b) with tests (section 8).
- Workspace UI: agent lanes, SLD, 3D hall, compliance matrix, finding drawer with PDF citations, option cards, revision timeline with diff, review/sign-off page, assumptions ledger.
- Typed what-if with impact chain.
- ERP/CRM sandbox service; Procurement agent; purchase requisitions on approval.
- Exports: PDF calc report and BOQ CSV.
- Landing page with "Open the signed sample design (no login)" and a 4-step guided tour; "Run it live"; replay from static files.
- Deployed on Firebase Hosting + Cloud Run; App Check on; uptime check; budget alert.

**Should (in order of value):**
1. Voice what-if via Gemini Live.
2. Grid and Solar asset packs (thin).
3. ADK eval set + seeded-fault benchmark feeding section 4.
4. Cloud Trace export of agent spans (OpenTelemetry), screenshot for the architecture slide.
5. Engine exposed as an MCP server at `/mcp` with `check_design` and `what_if` (FastMCP).
6. DXF export (ezdxf).
7. CRM update on approval.

**Cut order if behind (Thu 18:00 IST checkpoint):** CRM update → MCP server → DXF export → asset-pack maps (fall back to static SVG) → Gemini Live (typed what-if chips remain).

**Cancelled for the hackathon (roadmap slide only):** CADCraft rendering and visual review (pre-alpha, created 7 Oct 2026), live multi-user presence, Gemma on-prem mode, 800 VDC architecture, Revit/IFC round-trip, real ERP/CRM connectors, auto-layout from messy real drawings.

## 6. Agents and run model

### 6.1 Agents

ADK 2.11 (Python) `Workflow` graphs on Cloud Run. Every agent uses `gemini-3.8-flash` with structured output and function calling, and an explicit thinking level (low for Layout/Procurement/Docs, medium for Intake/Power/Cooling/Orchestrator). Tools compute; agents decide among engine-generated candidates and explain.

| Agent | Colour | Decides | Tools | Writes |
|---|---|---|---|---|
| Intake | slate | Which requirements exist, their values, and contradictions | Native PDF input; `verify_quote` (pdfplumber); `parse_dxf_geometry`; drawing cross-check | `DesignBrief` with verified citations; open questions |
| Orchestrator | white | Plan steps and owners; which open questions go to the human | — | Plan; gate prompts |
| Layout | cyan | Rack row placement strategy among engine candidates; busway route choice | `place_racks`, `route_busways`, `detect_clashes` | Rack positions; busway routes |
| Power Architect | amber | Which topologies to offer; fix choice for electrical findings (re-feed vs upsize) with a stated reason | `enumerate_topologies`, `size_power_chain`, `run_short_circuit`, `simulate_n_minus_1`, `erp_lead_time` | Options with metrics; selected electrical model |
| Cooling | blue | Zone split; header route tier; fix choice for cooling findings | `size_cdus`, `hydraulic_zones`, `route_pipes`, `pipe_hydraulics` | CDUs, zones, pipes, flows |
| Procurement | green | Which in-stock alternatives to propose | `erp_search_materials`, `erp_lead_time`, `annotate_options`, `erp_create_pr` | Availability on options; PRs after approval |
| Checker | red | Nothing (deterministic) | `run_rule_pack` | Findings |
| Docs | violet | Report section ordering and summary text | `render_calc_report`, `export_boq`, `export_dxf` | Files in Cloud Storage |
| Co-pilot | gradient | Which tool answers the user's question | `what_if`, `explain_finding`, `focus_element` | Answers; UI focus |

**Option gate behaviour:** Ask: the engineer picks. Auto: the agent picks the lowest-cost option with zero single points of failure and lead time within the tender limit, and states why.

### 6.2 Phased run model (fixes Cloud Run lifetime and the 60 s rewrite limit)

A run is three phases. Each phase starts from a POST that validates, writes a `phase` doc, starts a worker thread, and returns 202 in under 2 s. Each phase reads its inputs from Firestore, writes its outputs to Firestore, and ends either at a gate or at completion. No ADK session state crosses a phase boundary. Engine calls run off the event loop. Every `/api` call returns in under 10 s.

```
P1  Intake → Orchestrator ................................ ends at PLAN GATE (human, or auto)
P2  Layout.place_racks
    → [Power.enumerate_topologies ∥ Cooling.size_cdus + hydraulic_zones]
    → Procurement.annotate_options ....................... ends at OPTION GATE (human, or auto)
P3  Layout.route_busways → Cooling.route_pipes → detect_clashes
    → Checker → fix loop (owning agent fixes, ≤ 2 iterations) → Checker
    → Docs ............................................... ends at REVIEW GATE (always human)
P4  (on approval) Procurement.erp_create_pr → CRM update → audit entry
```

Gate approvals are POSTs to `/api` that write the decision and start the next phase.

### 6.3 Trust rules

- Every number displayed comes from the engine.
- LLM explanation text uses placeholders (`{value}`, `{limit}`, `{clause}`) filled from the finding record. Any digit appearing in LLM free text is rejected and replaced with the template sentence.
- Requirement cards: Gemini returns `{page, verbatim_quote, value, unit}`. A card is accepted only if pdfplumber finds the quote on that page and the quote contains the value. Bounding boxes come from pdfplumber, not from Gemini. The lane shows "N/M quotes verified".
- Drawing cross-check: Gemini reads grid labels and overall dimensions from the PDF plot; the engine compares them with the DXF. The lane shows "Drawing read · DXF agrees" or lists differences.
- Each agent writes an assumptions-ledger entry when it fills a gap. The ledger also lists what v0.1 does not check (section 8.3).

### 6.4 What-if

`what_if(param, value)` builds an engine-only shadow revision (no LLM) and returns in under 3 s. The impact chain is the list of failing elements ordered along the rack → busway → LV board → transformer path and the rack → zone → CDU path. The Co-pilot narrates it with placeholders. Parameters: rack kW, liquid fraction, ΔV limit, transformer loading cap. Judges can use it from the UI chips.

## 7. Google Cloud architecture

```
Browser — React app on Firebase Hosting (kirchhoff.web.app)
  ├─ Firebase Auth (anonymous) · App Check (reCAPTCHA Enterprise; debug token for Playwright)
  ├─ Firestore onSnapshot (read-only for clients): runs, events, revisions, findings, approvals
  ├─ Firebase AI Logic → Gemini Live (voice; function calls → /api/what_if, /api/explain)
  ├─ Replay mode: static golden-run.json from Hosting (works with backend down)
  └─ /api/** rewrite ──► Cloud Run "kirchhoff-api" (Python 3.12, FastAPI, ADK 2.11, asia-south1)
        instance-based billing (--no-cpu-throttling), min 1, max 3, concurrency 20, 2 vCPU / 2 GiB
        ├─ verifies Firebase ID token + project ownership on every call
        ├─ ADK workflows on Vertex AI gemini-3.8-flash (global endpoint)
        ├─ kirchhoff_engine (pandapower, networkx, shapely, numpy) + rule pack
        ├─ Firestore writes (batched events), Cloud Storage (uploads, exports, large models)
        ├─ OpenTelemetry → Cloud Trace (Should)
        └─ /mcp FastMCP server: check_design, what_if (Should)
     Cloud Run "kirchhoff-enterprise" (same image, ERP/CRM sandbox routes; min 0, max 2)
  Secret Manager · Cloud Build · Cloud Monitoring uptime checks · budget USD 200 (alerts at 50%, 90%)
```

How each required technology is load-bearing:
- **Gemini:** long-document reading with verified citations, contradiction finding, drawing reading, planning, choosing among options and fixes, explanations, and live voice.
- **ADK on Cloud Run:** the multi-agent workflow graphs, tool calling, gates and fix loop. Cloud Run rather than Agent Runtime because the engine needs native scientific Python dependencies and runs execute as background phases.
- **Firestore:** real-time event bus the UI renders from; design revisions, findings, approvals and audit trail; enterprise sandbox data.
- **Firebase:** Hosting, anonymous Auth for judges, App Check, AI Logic for Gemini Live.
- **Cloud Run (two services):** agent/engine API and the enterprise sandbox, showing integration through APIs.

## 8. Engine and rule pack

### 8.1 Model

`kirchhoff_engine` is pure Python with no LLM calls.
- **Electrical:** source systems, transformers (cast-resin, Dyn11), LV switchboards (no LV paralleling), UPS systems, feeders (busway or cable), row busways with tap-offs, racks. Each rack has two feeds mapped to source systems.
- **Cooling:** CDUs, hydraulic zones, headers, branches, rack manifolds.
- **Geometry:** hall polygon, 12 × 12 m column grid, keep-out zone, LV room and CDU positions, rack footprints, 3D polylines for routes on named tiers: `pipe_low` +2.6 m, `busway` +3.2 m, `pipe_high` +3.8 m.
- **Revision identity:** SHA-256 of the canonical model JSON.

### 8.2 Calculations (each unit-tested against a hand calculation)

- Design current `I = P / (√3 · U · cosφ)`.
- Ampacity and voltage drop are evaluated at the worst N-1 (failover) current.
- Voltage drop `ΔU% = 100 · √3 · I · L · (R cosφ + X sinφ) / U`, with R at operating temperature. Feeder sections use factor 1.0; a row busway with n equal tap-offs uses `(n+1)/(2n)`. Cumulative from LV switchboard to the furthest tap-off.
- Short circuit: pandapower `calc_sc` (IEC 60909, max case, `ip=True`) for Ik″ and ip at each LV board and busway.
- Redundancy: generic allocation model. Normal: each rack's load splits 50/50 across its two feeds (block-redundant reserve feeds via STS carry 0). Outage of any component: affected feeds transfer to the surviving feed. N-1 passes only if every rack keeps a feed and R01, R02 and R07 pass in that outage case. Implemented on a networkx graph, not repeated load flows.
- Cooling: PG25 properties fixed at 35 °C (ρ 1,020 kg/m³, cp 3.95 kJ/kg·K, μ 1.5 mPa·s; 25% by mass); `ṁ = Q / (cp · ΔT)`; `v = 4·V̇ / (π·D²)`; Darcy–Weisbach with Swamee–Jain friction factor and a 30% fittings allowance for the index circuit.
- Spatial: Shapely; clearance to columns; a pipe segment is "above electrical" if its tier is higher than the busway tier and its plan projection intersects the busway's plan footprint.

### 8.3 Rule pack v0.1 — "IEC-based, illustrative values, not for construction"

Clause references only; no copyrighted table text. Limits come from the tender wherever it specifies them.

| Rule | Check | References |
|---|---|---|
| R01 | Transformer loading ≤ tender cap (80%) in normal and every N-1 case | Tender §4.3; IEC 60076-12 (dry-type loading guide) |
| R02 | Busway/feeder rating ≥ failover design current | IEC 61439-6; IEC 60364-5-52 |
| R03 | `Ib ≤ In ≤ Iz`; `I2 ≤ 1.45 Iz` met by IEC 60947-2 breakers (I2 = 1.3 In) | IEC 60364-4-43 §433.1 |
| R04 | Breaker Icu ≥ prospective Ik″ | IEC 60364-4-43 §434.5.1; IEC 60909-0; IEC 60947-2 |
| R04b | Busway Icw ≥ Ik″ and ipk ≥ ip | IEC 61439-6 |
| R05 | ΔV LV board → furthest tap-off ≤ tender limit (2.0%) at failover current | Tender §4.6; IEC 60364-5-52 §525 |
| R06 | Zero single points of failure in the chosen topology | Tender §4.2; ISO/IEC 22237 (EN 50600) availability classes; TIA-942 |
| R07 | UPS capacity per system ≥ load in every N-1 case; autonomy ≥ 5 min | Tender §4.5 |
| R08 | CDU capacity per zone ≥ zone liquid load with N+1 | Tender §6.2; ASHRAE TC 9.9 liquid-cooling guidance |
| R09 | Supplied rack flow ≥ max(OEM minimum flow, flow for ΔT ≤ 10 K) | Tender §6.1; OEM rack guide |
| R10 | Pipe velocity ≤ 2.5 m/s | Tender §6.4 |
| R11 | No liquid piping above electrical busways; clearance to columns ≥ 300 mm | Tender §6.3.4 |
| R12 | SLD equipment = BOQ lines = PR lines | Internal consistency |
| R13 | CDU pumps fed from UPS-backed A and B supplies (continuous cooling) | Tender §6.5 |
| R14 | Index-circuit Δp ≤ CDU available external head | Tender §6.2 |

**Not checked in v0.1 (shown in the ledger):** earth-fault loop impedance (IEC 60364-4-41 §411), selectivity/discrimination, arc flash, harmonics, air-side cooling for the 20% air-cooled heat.

**Finding status:** `pass | fail | warn | n/a`. The total number of checks is counted from the run, never narrated.

## 9. Sample scenario: Hall A (fictional)

All names fictional, labelled "Sample project".

- **Client:** Deccan Compute. **Site:** an AI campus near Hyderabad.
- **Hall:** 60 m (x) × 36 m (y); column grid 12 × 12 m (6 × 4 lines, 24 columns including perimeter); keep-out zone (fire-suppression room) at the hall's centre-west; LV rooms A and B along the east wall; CDU gallery along the north wall.
- **IT load:** 48 racks in 6 rows of 8, 600 × 1,200 mm, 132 kW per rack (GB300 NVL72-class), 6.336 MW. Heat split 80% liquid / 20% air as a tender assumption (OEM figures are closer to 90/10; ledger notes it).
- **Mechanical auxiliary load on the A/B LV system:** 0.30 MW (CDU pumps, fan walls, controls).
- **Power:** two 33 kV incomers (A/B); source fault level 1,000 MVA, R/X 0.1; 415 V, 50 Hz, cosφ 0.95; each row has an A busway and a B busway (12 row busways); three LV boards per side, each feeding two rows.
- **Tender clauses (authored by us):** §4.2 "2N"; Appendix B table "block redundancy acceptable" (the deliberate contradiction); §4.3 transformer loading ≤ 80% under any single failure; §4.5 UPS autonomy ≥ 5 min; §4.6 ΔV ≤ 2.0% LV board → tap-off at worst-case current; §6.1 supply 30 °C, ΔT 10 K; §6.2 CDUs N+1 per zone; §6.3.4 no liquid above electrical; §6.4 velocity ≤ 2.5 m/s; §6.5 continuous cooling.
- **Catalogue (`scenarios/hall_a/catalogue.yaml`):** transformers 2.5 MVA (uk 6%) and 3.15 MVA (uk 7%); busways 1,600 / 2,000 / 2,500 A with R and X at operating temperature, Icw and ipk; breakers with Icu/Ics; UPS modules; CDU 1,200 kW at ΔT 10 K with 150 kPa available external head; pipe DN → internal diameter; OEM minimum rack flow.
- **ERP seed:** 2.5 MVA transformer — stock 0, lead time 98 weeks; 3.15 MVA — stock 6, 12 weeks for more; plus UPS modules, busway runs, CDUs, with indicative prices.

**Verified numbers (hand-calculated 13 Oct, to be locked by the scenario regression test on Tue 14 Oct):**
- Rack current 193 A; row busway 773 A normal, 1,546 A failover → 1,600 A busway.
- LV board in 2N failover: 2,328 kVA → 93% on 2.5 MVA (fails R01's 80% cap) and 74% on 3.15 MVA (passes). Six 3.15 MVA units are in stock, which is exactly the 3 + 3 needed.
- 1,600 A busway feeder at failover: about 0.0255 %/m, so 2.0% is reached at about 78 m. The first-pass route for the far-west row's feeder detours around the keep-out zone; tuning target: first-pass ΔV in [2.1%, 2.6%] (fails R05); both candidate fixes must pass: re-feed from the nearer board or upsize to 2,000 A (about 0.0194 %/m).
- Liquid heat 105.6 kW per rack → 157 L/min at ΔT 10 K. Zone of 2 rows = 1.69 MW → CDUs N = 2, N+1 = 3 per zone, 9 total. Zone header DN200 at 1.26 m/s.
- First-pass main header for one zone runs on `pipe_high` and crosses busway B-03 (fails R11); fix: drop to `pipe_low` at the crossing.
- What-if 200 kW: row busway failover 2,343 A (> 1,600 A, fails R02), LV boards and transformers fail R01, zone liquid load 2.56 MW > 2.4 MW N capacity (fails R08).

## 10. Asset packs (thin, user-requested)

Both reuse the shell, Checker, finding drawer and revision timeline, with a single "Asset agent" that runs the engine and explains results.

- **Grid:** a 132 kV double-circuit overhead line, about 18 km, to the campus substation (2 × 50 MVA 132/33 kV). Compare three ACSR conductors on ampacity, voltage regulation and I²R losses; pandapower fault level at the point of connection; mini SLD. Map of the line route.
- **Solar:** a ~5 MWp ground-mount field on a polygon beside the hall. pvlib clear-sky yield (no external weather API at runtime); string sizing from module Voc at minimum site temperature vs inverter maximum DC voltage; table layout with Shapely; DC string voltage drop. Map with table rows.

Maps use the Google Maps JavaScript API; if behind schedule, a static SVG.

## 11. Reliability and judging-window operations

- **Judge's first 10 seconds:** the landing page has one primary call to action, "Open the signed sample design (no login)". It opens the completed, signed Hall A with a 4-step guided tour: citations → agents → checker → sign-off. Secondary buttons: "Run it live (~N min)" and "Replay a recorded run". What-if chips work in every mode.
- **Event-sourced UI:** the UI renders from one in-browser event store. Live mode feeds it from Firestore; replay mode feeds it from `golden-run.json` on Hosting (events carry revision and finding snapshots), so replay works with Cloud Run down and no Gemini quota. Replay is labelled as such.
- **Concurrency limits:** global cap of 3 concurrent live runs; overflow is offered replay. Per anonymous user: 5 runs per hour.
- **Gemini:** retries with backoff, per-agent timeout, structured-output validation with one repair attempt. Request a quota increase before 19 Oct.
- **Firestore write discipline:** events batched every ~250 ms; `runs/{rid}` updated at most once per second; event docs under 10 KB; design JSON over 500 KB moved to Cloud Storage with a hash pointer; a single writer assigns `seq` per phase.
- **Monitoring:** uptime checks on `/` and `/api/health` with email alerts; budget USD 200 with 50% and 90% alerts.
- **Freeze:** golden path frozen Thu 16 Oct 22:00 IST. After submission, only fixes via tagged releases.

## 12. UI design

Dark, dense, Linear/Vercel-like. Neutral greys; one accent per agent; monospace numerals; Inter for text. Effects only on the landing page. Motion shows progress (nodes staging in, matrix cells filling, diff recolouring), with `prefers-reduced-motion` respected. Status never relies on colour alone: icons and text accompany pass/fail/warn. WCAG AA contrast; keyboard access to all controls.

**Screens:**
1. **Landing:** statement, primary CTA, Run live / Replay, three asset-pack cards.
2. **Workspace:**
   ```
   ┌ Kirchhoff ▸ Deccan AI Campus · Hall A (sample)  [Asset pack ▾] ●agents [Ask|Auto] [Request sign-off] ┐
   ├─────────────┬──────────────────────────────────────────────┬───────────────┤
   │ Agent lanes │ [3D Hall] [SLD] [Matrix] [Options] [Docs]    │ Co-pilot      │
   │ ● Intake ✓  │                                              │ plan · ask    │
   │ ● Layout ⋯  │   canvas: checker highlights, diff recolour  │ what-if chips │
   │ ● Power ⋯   │                                              │ voice         │
   │ ● Cooling ⋯ │                                              │ citations     │
   │ ● Procure ⋯ │                                              │               │
   │ ● Checker ✕2│                                              │               │
   ├─────────────┴──────────────────────────────────────────────┴───────────────┤
   │ Revisions  r1 ── r2 (2 fail) ── r3 ✓ ── signed by Demo Reviewer             │
   └─────────────────────────────────────────────────────────────────────────────┘
   ```
3. **Plan gate:** steps with owners, open questions from Intake, Approve.
4. **Options:** three cards (2N, distributed redundant 4-to-make-3, block redundant with reserve) with installed MVA, worst N-1 loading %, cost, losses, max lead time, availability flags; select.
5. **Finding drawer:** rule, clause chips, tender chip (opens PDF at the pdfplumber box), formula with inputs, value vs limit bar, explanation, the fix the agent chose and the alternative it rejected, "show on canvas".
6. **Review page:** diff (changed elements recoloured on SLD and 3D, changed-element table), assumptions ledger incl. "not checked", findings summary, Approve with stamp (name, role, time, revision hash). Live demo stamp reads "Demo Reviewer"; the video uses the team members' names.
7. **Enterprise panel:** "ERP/CRM sandbox (simulated)": PRs, opportunity stage.
8. **Grid** and **Solar** asset-pack screens.

**SLD:** racks grouped per busway; the graph stages in by level (sources → transformers → boards → busways → rack groups). **3D:** instanced racks, tube geometry for busways and pipes on their tiers, column grid, keep-out volume; elements coloured by check status. No agent cursors.

**Libraries:** Vite + React + TypeScript, Tailwind + shadcn/ui, Motion, @xyflow/react + elkjs, @react-three/fiber + drei, react-pdf, TanStack Table, Google Maps JS API, Firebase JS SDK 13 (Auth, Firestore, App Check, AI Logic).

## 13. Data model and security

```
projects/{pid}                           name, assetPack, ownerUid, createdAt, status, sample:boolean
projects/{pid}/documents/{did}           kind, storagePath, pages, extraction
projects/{pid}/runs/{rid}                status, autonomy, phase, plan[], openQuestions[], metrics, startedAt, finishedAt
projects/{pid}/runs/{rid}/events/{eid}   seq, phase, agent, kind (plan|tool_call|tool_result|message|artifact|finding|gate|ledger), title, detail, payload (<10 KB), ts
projects/{pid}/revisions/{rev}           parentRev, author, hash, model | modelRef, summary, checkSummary, status (draft|checked|signed), ledger[]
projects/{pid}/revisions/{rev}/findings/{fid}  rule_id, element_id, clause_refs, tender_refs, formula, inputs, value, limit, unit, status, explanation, fix, rejected_fix
projects/{pid}/approvals/{aid}           rev, approverName, role, decision, comment, ts
enterprise/erp/materials/{mid}           category, rating, stock, leadTimeWeeks, unitPrice
enterprise/erp/prs/{prid}                projectId, rev, lines[], status, createdAt
enterprise/crm/opportunities/{oid}       account, stage, value, notes
```

- **Firestore rules:** clients may only read projects they own (and the shared signed sample); all client writes are denied. Plan edits, option picks, approvals and what-ifs go through `/api`.
- **API auth:** `kirchhoff-api` is public (Hosting rewrites require it), so it verifies the Firebase ID token and App Check token, and checks project ownership, on every call.
- **Storage rules:** owner-only read of uploads and exports; writes only via the API's signed URLs.

## 14. Repository layout

```
kirchhoff/
  apps/web/                 React app
  services/api/             FastAPI + ADK workflows + kirchhoff_engine + rule pack + enterprise routes + tests
  scenarios/hall_a/         generators for the tender PDF, hall DXF/PDF, catalogue.yaml, ERP seed, golden-run.json
  infra/                    firebase.json, firestore.rules, storage.rules, deploy scripts, monitoring/budget setup
  docs/                     architecture, submission brief, this spec
```

The GitHub repo is created private and made public before submission.

## 15. Testing

- **Engine:** pytest per calculation against hand-worked values (section 9's verified numbers become test cases).
- **Rule pack:** one passing and one failing fixture per rule.
- **Scenario regression (Tue 14 Oct):** first pass yields exactly R05 (far-row feeder) and R11 (header over B-03) failures within the target bands; both fixes pass; the 200 kW what-if yields failures in R01, R02 and R08.
- **Seeded-fault benchmark:** ~30 mutated designs; catch rate and false positives feed section 4.
- **Agents:** schema tests with recorded Gemini responses; ADK eval set for Intake extraction; one live smoke run per day.
- **End to end:** Playwright against the deployed URL (sample design tour → run live → plan gate → option gate → checker → fix → sign-off → PRs), with an App Check debug token; before every deploy and daily during judging.

## 16. Schedule

| Day | Deliverables |
|---|---|
| Mon 13 Oct | Spec v2 reviewed; plan; repo scaffold; hello-world end to end (Hosting → Cloud Run → Firestore events in browser); App Check on; Gemini Live spike (model + function calling) |
| Tue 14 Oct | Engine, catalogue, rule pack R01–R14 with tests; scenario generators and regression lock; Intake with verified citations; phased workflow skeleton streaming events |
| Wed 15 Oct | Workspace UI (lanes, SLD, 3D, matrix, finding drawer, PDF citations, revisions), landing + tour; full live run P1–P3; evening screen recording |
| Thu 16 Oct | Option gate + ERP sandbox + Procurement; fix loop + diff; review/sign-off + PRs; exports; what-if + voice; asset packs; golden-run.json replay; Should items by value; checkpoint 18:00; freeze 22:00; evening screen recording |
| Fri 17 Oct | Record 09:00; deck; video (< 3:00); brief; Playwright pass; repo public; submit by 20:00 IST |
| Sat 18 Oct | Buffer only |

Parallelism: at most 4 workstreams (engine + scenario; agents + API; web UI; infra + enterprise sandbox + replay), integrated daily.

## 17. Risks

| Risk | Mitigation |
|---|---|
| ADK workflow details beyond the spike | Phases are small graphs; fallback is plain `google-genai` function calling with the same phase shape |
| Gemini Live model/App Check | Day-0 spike; typed what-if is the guaranteed path |
| Run latency | Parallel branches; engine does the heavy lifting; stream partial results; replay for judges who don't want to wait |
| UI polish eats the schedule | Fixed component catalogue; cut order in section 5; daily recordings as insurance |
| Copyrighted standard tables | Clause numbers only; catalogue values labelled illustrative |
| Deployment breaks during judging | Phased runs, static replay, uptime alerts, freeze, App Check enforced before 2 Nov |
| Over-claiming | Measured metrics only; "sample project", "sandbox (simulated)", "illustrative, not for construction" labels |

## 18. Submission deliverables

- Deck in the 16-slide template (team, idea, opportunities/USP, features, process flow, wireframes, architecture, technologies, cost, snapshots, benchmarks, future development, links).
- Video under 3:00 following section 3.
- Live URL, public GitHub repo, and the brief (section 7 is its source; it states why Cloud Run over Agent Runtime and why native PDF input with verified quotes over File Search).
- Benchmarks slide uses only section 4's measured values.
