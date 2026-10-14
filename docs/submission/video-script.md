# Kirchhoff: demo video script

**Target runtime: 2:45.** The rules require a video strictly under 3:00, so 2:45 leaves 15 s of headroom. **Voiceover: 308 words.** That is about 2 words per second, a calm pace that leaves room for numbers. The in-clip voice question in beat 8 is extra (7 words) and is not counted.

**Rules for the edit**
- Use real product footage only, and capture every value on screen from the recorded run. Never type a value in post.
- Burn the voiceover in as captions.
- Speed up agent footage and label it with a burned-in "time-compressed" tag and an elapsed-time clock.
- Keep the fictional-data banner visible wherever the app shows it. The end card carries both disclaimers.
- Keep the music bed low and duck it under the voiceover.
- If the cut runs long, drop beat 10 first; integrations also appear in beat 9.
- `[SHOT: …]` marks product footage to capture, with its screen and state. `[TEAM SLOT …]` marks material the team supplies.

---

| Visual | Voiceover |
|---|---|
| **`0:00–0:10` · Cold open.** No title yet.<br>[SHOT: 3D hall, Hall A r1. The camera starts wide over 6 rows of 8 racks in the 60 × 36 m hall, then flies in to zone-2 header H-Z2 glowing red where it crosses above busway feeder FB-03 at y ≈ 24 m. A chip pops up: "R11 · Tender §6.3.4 · no liquid above electrical".]<br>[SHOT: The recorded fix applies, H-Z2 recolours, the whole hall turns green, and the revision bar ticks r1 → r2.] | Coolant piping, routed above a live power feeder. Kirchhoff caught it, cited the tender clause, and fixed it. |
| **`0:10–0:16` · Title.**<br>Title card over the green hall: "Kirchhoff by Ordinal" and "AI designs. Physics checks. An engineer signs." | This is Kirchhoff. AI designs. Physics checks. An engineer signs. |
| **`0:16–0:26` · Problem.**<br>[TEAM SLOT A, optional, 3–4 s: a clip of the team at work, supplied by the team.]<br>Then a dark caption card: "Only 6% of engineers trust AI results without verification." Source line: "Omni Calculator, AI adoption in engineering". | AI halls need power and liquid cooling designed together. And engineers check AI by hand: only 6 percent trust its results unverified. |
| **`0:26–0:42` · Tender in.**<br>[SHOT: Hall B workspace. The tender PDF and the hall DXF are dragged onto the drop zone.]<br>[SHOT: The Intake lane streams requirement cards marked "✓ quote verified", with an "N/M quotes verified" counter; take the value from the run.]<br>[SHOT: Click the §2.3 chip; the PDF opens with the clause box highlighted.]<br>[SHOT: Intake's open question: §4.2 "2N" against Appendix B "block or distributed redundancy acceptable".]<br>[SHOT: Plan gate; the engineer clicks "Approve plan".] | Drop in the tender. Gemini reads it, and a requirement only counts if its quote is found on the cited page. Intake even catches the client contradicting itself. The engineer approves the plan. |
| **`0:42–0:55` · Agents at work.** Burned-in tags: "time-compressed" and an elapsed clock.<br>[SHOT: The agent lanes run, with Power and Cooling active side by side.]<br>[SHOT: In 3D, 48 racks drop into 6 rows of 8.]<br>[SHOT: The SLD stages in: MV → transformers → boards → UPS → busways.]<br>[SHOT: The Cooling lane reads "9 × CDU · 1.2 MW" as the pipes route onto their tiers.] | Agents place 48 racks at 132 kilowatts each. Power and Cooling work in parallel: a 2N electrical system and nine 1.2-megawatt CDUs. |
| **`0:55–1:23` · Checker.**<br>[SHOT: Matrix tab. The counter fills to "149 checks · 147 pass · 2 fail".]<br>[SHOT: Finding drawer for R05 on FA-01: 82 m feeder, bar at 2.16% against 2.0%, §4.6 chip, formula with inputs.]<br>[SHOT: Fix cards "2,000 A busway · 1.66% · +$11,480" and "parallel cable · 0.84% · +$15,580", with Power's choice and reason as recorded.]<br>[SHOT: R11 drawer for H-Z2 over FB-03 with the §6.3.4 chip. Cards read "local drop · +$420 · 1 pipe" and "reroute · −$910 · 2 pipes", with Cooling's choice as recorded.]<br>[SHOT: The diff recolours the changed elements, and the matrix reads "r2 · all pass".] | Then the checker runs. It's deterministic, with no LLM in the verdict path, so the AI can't mark its own homework. 149 checks: 147 pass, two fail, each citing its clause. Feeder FA-01 drops 2.16 percent against a 2 percent limit. Every fix is re-checked against every rule before an agent may pick it. |
| **`1:23–1:40` · ERP lead-time swap.**<br>[SHOT: Procurement lane and the 2N option card: "2.5 MVA · stock 0 · lead time 98 wk > 26 wk (§2.3) · R15 fail".]<br>[SHOT: The card swaps to "3.15 MVA · stock 6 · 38.07% / 76.15%".]<br>[SHOT: Power lane re-check: "fault level 60.45 → 65.42 kA ✓".] | It checks the supply chain too. The 2.5 MVA transformer has a 98-week lead time; the tender allows 26. Kirchhoff swaps to a 3.15 MVA unit in stock, and re-checks the fault level. |
| **`1:40–1:56` · What-if by voice.**<br>[SHOT: The co-pilot panel. The user presses the voice button, and the transcript shows "What if racks go to 200 kW?"]<br>[TEAM SLOT B: a team member speaks the question; this is in-clip audio, about 3 s.]<br>[SHOT: The impact chain lights up, rack → busway → board → transformer in the power colour and rack → zone → CDU in the cooling colour. Chips read "R01 113.6%", "R02 2,343 A" and "R08 2,560 kW > 2,400 kW"; the counter reads "62 findings · 18 impact chains".] | *(In-clip: "What if racks go to 200 kilowatts?")*<br>The engine re-runs every rule in about 8 milliseconds. 18 impact chains light up across power and cooling: transformers at 113.6 percent, cooling zones over capacity. |
| **`1:56–2:12` · Engineer sign-off.**<br>[SHOT: The review page: diff, assumptions ledger with its "not checked" list, findings summary.]<br>[SHOT: Approve is clicked; the stamp reads "You (Demo Reviewer) · time · revision hash".]<br>[SHOT: New PRs appear in the ERP view, and the CRM opportunity "Hall B design-build" moves to "Design approved".] | Nothing ships until an engineer signs. The review shows the diff and every assumption, then stamps the revision hash. Approval raises purchase requisitions in the ERP and moves the CRM deal. |
| **`2:12–2:19` · Integrations.**<br>[SHOT: The Integrations page. ERP (SAP-style) sandbox shows 60 materials and 3 historical PRs plus the new ones; CRM (Salesforce-style) shows 9 opportunities; Cloud Storage documents; "sandbox (simulated)" labels and the fictional-data banner visible.] | Engineering, procurement and sales, in one workflow. |
| **`2:19–2:27` · Grid and Solar.**<br>[SHOT: Grid pack: the 132 kV line on the static map, conductor comparison cards, mini SLD.]<br>[SHOT: Solar pack: the field layout with its card "STR-28 · 327 tables · ~5,036 kWp · DC/AC 1.26 · clear-sky yield ~2,639 kWh/kWp (clear-sky only)".] | Same engine, new asset packs: a 132 kV grid line, and a five-megawatt-peak solar field. |
| **`2:27–2:37` · Proof.**<br>Hold the architecture diagram (deck slide 8) for at least 8 s. Overlay three tiles: "35/35 seeded faults caught", "0 false positives", "byte-identical output". | It caught all 35 seeded design faults, with zero false positives. Built on Gemini, ADK, Cloud Run, Firestore and Firebase. |
| **`2:37–2:45` · End card.**<br>[TEAM SLOT C: team photo of Mehul Arora and Jaydratha, supplied by the team.]<br>Text: "Kirchhoff by Ordinal · Future of Work & Enterprise Productivity · kirchhoff.web.app".<br>Small print: "Demo companies, people and data are fictional · IEC-based, illustrative values, not for construction". | Kirchhoff, by team Ordinal, for the future of work. Try it at kirchhoff dot web dot app. |

---

## Timing and word check

| Beat | In | Out | Seconds | VO words | Words per second |
|---|---|---|---|---|---|
| 1 Cold open | 0:00 | 0:10 | 10 | 18 | 1.8 |
| 2 Title | 0:10 | 0:16 | 6 | 10 | 1.7 |
| 3 Problem | 0:16 | 0:26 | 10 | 22 | 2.2 |
| 4 Tender in | 0:26 | 0:42 | 16 | 33 | 2.1 |
| 5 Agents at work | 0:42 | 0:55 | 13 | 22 | 1.7 |
| 6 Checker | 0:55 | 1:23 | 28 | 54 | 1.9 |
| 7 ERP lead-time swap | 1:23 | 1:40 | 17 | 33 | 1.9 |
| 8 What-if by voice | 1:40 | 1:56 | 16 | 26 (+7 in-clip) | 2.1 with the in-clip line |
| 9 Sign-off | 1:56 | 2:12 | 16 | 31 | 1.9 |
| 10 Integrations | 2:12 | 2:19 | 7 | 7 | 1.0 |
| 11 Grid and Solar | 2:19 | 2:27 | 8 | 15 | 1.9 |
| 12 Proof | 2:27 | 2:37 | 10 | 20 | 2.0 |
| 13 End card | 2:37 | 2:45 | 8 | 17 | 2.1 |
| **Total** | | **2:45** | **165** | **308** | 1.9 |

## Where each claim comes from

| Claim in voiceover | Backing |
|---|---|
| Coolant above a live feeder, caught, cited, fixed | R11 fails for H-Z2 over FB-03 at y ≈ 24 m (§6.3.4); engine fixes are a local drop (+$420) or a reroute (−$910) |
| Only 6 percent trust AI results unverified | Omni Calculator, *AI adoption in engineering* (source on screen) |
| A requirement counts only if its quote is found | Trust rule: pdfplumber verifies the quote on the cited page |
| 48 racks at 132 kW; 2N; nine 1.2 MW CDUs | Engine run, 14 Oct |
| 149 checks, 147 pass, two fail | First pass of the golden design, 14 Oct |
| FA-01 at 2.16% against a 2% limit | R05 finding, 14 Oct |
| Every fix re-checked before an agent may pick it | The engine re-runs the full rule pack on each fix candidate before offering it |
| 98-week lead time, 26 allowed, 3.15 MVA in stock, fault level re-checked | ERP sandbox: stock 0 against stock 6; fault level 60.45 → 65.42 kA, 14 Oct |
| About 8 ms; 18 impact chains; 113.6%; cooling over capacity | What-if at 200 kW: R01 at 113.6%, R08 at 2,560 kW > 2,400 kW, 62 findings, 18 chains |
| 132 kV line; five-megawatt-peak solar | Grid pack; Solar pack at about 5,036 kWp |
| 35 seeded faults, zero false positives | Checker benchmark, 14 Oct |
