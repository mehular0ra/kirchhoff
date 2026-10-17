# Kirchhoff: demo video script, v2 (proposal)

**Runtime: 3:28** without Jayadratha's intro, **3:35** with it. Both are inside the form's 3:00 to 4:00 and near the 3:30 to 3:50 target; the ceiling is 3:59. The first version of this script ran 2:39 and 2:46, under the form's minimum; four extra beats (5b, 10b, 15b, 16b) bring it up. The original `video-script.md` stays as it is; this file replaces it only if the team agrees.

**What changed from v1**
- **A product demo first.** The video opens on real footage, follows one workflow end to end, and gives about three quarters of the runtime to product footage and the flow scenes. The YC notes (`video/yc-video-notes.md`) are inspiration for pacing only.
- **The client's systems come first.** Requirements arrive from the client's Gmail, an SAP Ariba RFQ and a Google Drive spec folder. Kirchhoff triages them, agents design, physics checks, and an engineer signs. Purchase requisitions then go to SAP S/4HANA, the documents are filed to Google Drive, and the CRM stage moves.
- **A short team intro.** Mehul speaks over his photo, or a short clip if he records one. A lower third and a live waveform play from his voice. Jayadratha's intro is optional and drops cleanly. No titles such as founder or CEO appear anywhere.
- **Natural voice.** Each beat gives talking points and one suggested line. Mehul speaks in his own Indian English. He may paraphrase freely. **Only the numbers and product names must be said exactly as written.**
- **Captions come from his recording.** `video/transcribe.py` builds them, not this script (see `video/edit-plan-v2.md`).

**Rules that do not change**
- The trust thesis stays at the centre: every number is checked by a deterministic engine, and an engineer signs.
- Every number on screen and in the voiceover is **from capture**. The scenes read their numbers from `apps/web/public/demo/` at render time, so re-render after the golden capture. Before recording, check each number marked *(from capture)* against the rendered scenes and the recorded clips. If a number changed, say the new one.
- Every connector on screen carries a "connector · sandbox" or "simulated" tag. Never say "integrated with SAP" or "live Gmail". Say "a sandbox", "a simulated inbox" or "connectors".
- Keep the fictional-data banner wherever the app shows it. The end card carries both disclaimers.
- Use British and Indian spelling on screen and in captions: organise, colour, programme, centre, metre.

**How to read the beats.** `[SCENE sN]` is a motion-graphic clip from `video/scenes/` (rendered to `scenes/out/sN-*.mp4`). `[SHOT: …]` is product footage on the new light theme. Numbers in **bold** with *(from capture)* must match the capture; the current values are shown.

---

## Beat table

| # | In–out | Seconds | Picture | Voice |
|---|---|---|---|---|
| 1 | 0:00–0:07 | 7 | [SHOT: cold open. Hall A in 3D; the camera flies to header H-Z2 glowing red over feeder FB-03; chip "R11 · Tender §6.3.4"; the fix applies and the hall turns green, r1 → r2.] | Mehul, line 1 |
| 2 | 0:07–0:12 | 5 | [SCENE s1-title] "Kirchhoff by Ordinal", then "AI designs. Physics checks. An engineer signs." | Mehul, line 2 |
| 3 | 0:12–0:22 | ~10 | [SCENE s1b-intro-mehul] Photo (or clip), lower third "Mehul Arora · AI engineer · Team Ordinal", live waveform from his voice. | **Intro, Mehul reads** (in-clip audio) |
| 3b | (optional, +7) | ~7 | [SCENE s1c-intro-jayadratha] Photo, lower third "Jayadratha Gayen · AI research engineer · Team Ordinal". | **Intro, Jayadratha reads** (in-clip audio) |
| 4 | 0:22–0:31 | 9 | [SCENE s2-problem] "132 kW per rack" counts up; power and liquid cooling meet at one node; "In weeks, not ~~months~~." | Mehul, line 4 |
| 5 | 0:31–0:45 | 14 | [SCENE s3-requirements-in] The tender lands in Gmail (sandbox); the drawing and addendum come from a Drive spec folder and an Ariba RFQ (simulated); all three fly into the Kirchhoff bids inbox; the fields show "✓ found"; the fit card shows **Pursue**. | Mehul, line 5 |
| 5b | 0:45–0:59 | 14 | [SHOT: the bids inbox, six emails, newest first; the Hall B tender opens with its fit verdict **Pursue** and its reasons, including the day-zero supply check that already expects the in-stock swap; the Vindhya BOQ email is a decline (a substation is not one of our asset packs) and its load, only on a scanned page, is marked "Not verified (scan)". Nothing is clicked that writes.] | Mehul, line 18 |
| 6 | 0:59–1:12 | 13 | [SHOT: Hall B intake lane: "✓ quote verified" cards and the "N/M quotes verified" counter; click the §2.3 chip and the PDF opens with the clause highlighted; the §4.2 vs Appendix B open question; "Approve plan".] | Mehul, line 6 |
| 7 | 1:12–1:19 | 7 | [SCENE s4-agents] Lanes for Intake, Power, Cooling and Procurement on Gemini · Vertex AI; the hall plan draws itself from the model. | Mehul, line 7 |
| 8 | 1:19–1:29 | 10 | [SHOT: agents at work, with racks dropping in 3D, the SLD staging and pipes routing. Burned-in "time-compressed ×N" and an elapsed clock.] | Mehul, line 8 |
| 9 | 1:29–1:37 | 8 | [SCENE s5-checks] "149 checks", "147 pass · 2 fail", two finding cards, fixes, "r2 · 149 pass · 0 fail". | Mehul, line 9 |
| 10 | 1:37–1:52 | 15 | [SHOT: the R05 drawer for FA-01 with its formula and both fix cards; the R11 drawer for H-Z2; the diff recolours; the matrix reads "r2 · all pass".] | Mehul, line 10 |
| 10b | 1:52–2:04 | 12 | [SHOT: the R05 drawer for FA-01; click "Open tender §4.6" and the tender PDF opens on that page with a box around the quote, marked "Verified quote".] | Mehul, line 19 |
| 11 | 2:04–2:14 | 10 | [SHOT: the Procurement option card "2.5 MVA · stock 0 · 98 wk > 26 wk", which swaps to "3.15 MVA · stock 6"; the fault-level re-check.] | Mehul, line 11 |
| 12 | 2:14–2:26 | 12 | [SHOT: the co-pilot voice what-if "What if racks go to 200 kW?" and the impact chain lighting in two colours.] | In-clip question, then Mehul, line 12 |
| 13 | 2:26–2:32 | 6 | [SCENE s6-sign] The review card, "Approve and sign", then the stamp with name, time and revision hash. | Mehul, line 13 |
| 14 | 2:32–2:38 | 6 | [SHOT: the approved Hall A r2 review page and its stamp: "Priya Raman · Lead Electrical Engineer (Reviewer) · time · hash".] | (silence or a short line) |
| 15 | 2:38–2:50 | 12 | [SCENE s7-connectors] From the signed revision: **7 PRs** to SAP S/4HANA (sandbox), documents to Google Drive (sandbox), and the CRM stage moves "Design in progress → Design approved". | Mehul, line 15 |
| 15b | 2:50–3:01 | 11 | [SHOT: the 132 kV grid intake (conductor options and its checks), then the 5 MWp solar project (string options, checks, site geometry), both projects in the same app.] | Mehul, line 20 |
| 16 | 3:01–3:09 | 8 | [SCENE s8-google-cloud] Firebase → Cloud Run → Gemini on Vertex AI → engine and checker (no LLM) → Firestore. | Mehul, line 16 |
| 16b | 3:09–3:21 | 12 | [SCENE s10-numbers] Four measured numbers, each with its source: **35 of 35** planted faults caught with no false alarms, **25 of 26** tender quotes verified, a **149 s** median, **$0.066** per design. | Mehul, line 21 |
| 17 | 3:21–3:28 | 7 | [SCENE s9-end] kirchhoff.web.app, repo link, disclaimers. | Mehul, line 17 |

---

## Talking points and suggested lines

Speak as you would to a senior engineer friend: plain, warm, direct, one breath per sentence. Paraphrase freely, but say the **numbers and product names** exactly. Avoid American idioms and startup slang ("gonna", "super excited", "game-changer", "ship it", "crush").

### 1 · Cold open (footage, 7 s)
- Coolant pipe routed over a live power feeder; that is a real-world clash.
- Kirchhoff caught it, cited the tender clause **§6.3.4** *(from capture)*, and fixed it.

> Suggested: "This coolant pipe was running over a live power feeder. Kirchhoff caught it, showed the tender clause, and fixed it."

### 2 · Title (5 s)
- Say the name and the three-part promise.

> Suggested: "This is Kirchhoff. AI designs. Physics checks. An engineer signs."

### 3 · Intro, Mehul reads (in-clip audio, about 8–12 s, 25–30 words)
- Who you are, in one line. No title.
- What Kirchhoff does for an AI data-centre team, in one line.
- One honest outcome, measured: from a tender to a checked design in minutes (median 149 s over 3 live runs, time at the gates excluded), with an engineer still signing.

> Suggested: "Hi, I'm Mehul. Jayadratha and I built Kirchhoff, so AI data-centre teams can go from a tender to a checked power and cooling design in minutes, and an engineer still signs it."

### 3b · Intro, Jayadratha reads (optional, about 6 s, about 15 words)
- Name, background in one line, what he ran on this project.

> Suggested: "I'm Jayadratha. I'm an electrical engineer, I worked in solar before AI, and I ran Kirchhoff's cloud and testing."

### 4 · Problem (9 s)
- AI halls now run at **132 kW per rack** *(from capture)*, with most of the heat going to liquid.
- Power and liquid cooling have to be designed together.
- The client wants it in weeks, and senior MEP engineers are few.

> Suggested: "AI halls now run at 132 kilowatts a rack. Power and liquid cooling must be designed together. And the client wants it in weeks, not months."

### 5 · Requirements arrive (14 s)
- The tender comes from the client's own systems: an email in Gmail, an RFQ from SAP Ariba, a spec folder on Google Drive. All three are sandboxes here.
- Kirchhoff reads them, and every extracted field has its quote found in the source.
- A deterministic fit check says **Pursue** *(from capture)*. It also warns early that the **2.5 MVA** transformer has a **98-week** lead time against a **26-week** clause *(from capture)*.

> Suggested: "The tender comes in the way clients actually send it: Gmail, an Ariba RFQ, a Drive folder. Kirchhoff reads all of it, checks the fit, and says pursue. It even flags the transformer lead time on day zero."

### 5b · The bids inbox, footage (14 s) · voice file `b18-inbox.wav`
- The same triage, now in the product: six emails, newest first.
- **Pursue** on the Hall B tender, with the reasons the fit check gives, including the day-zero supply check, which already expects the in-stock swap *(from capture)*.
- The Vindhya BOQ is a **decline** for its asset type: a substation is not one of our asset packs. Separately, its load is only on a scanned page, so the card marks it "Not verified (scan)" and asks for a text copy. Do not say the scan caused the decline.

> Suggested: "Every email is triaged, with reasons. Pursue on the Hall B tender. And a decline for the substation BOQ: not our asset type, and its load is only on a scan."

### 6 · Intake, footage (13 s)
- Gemini reads the tender PDF, and a requirement counts only if its quote is found on the cited page: **N/M quotes verified** *(from capture)*.
- Intake catches the client contradicting itself: §4.2 says 2N, Appendix B allows block redundancy.
- The engineer approves the plan.

> Suggested: "Gemini reads the tender. A requirement counts only if its quote is found on that page. It even catches the client contradicting itself. The engineer approves the plan."

### 7 · Agents at work, scene (7 s)
- Four agents on Gemini, one shared engineering model.
- Power: **2N**, **6 × 3.15 MVA** transformers. Cooling: **9 CDUs of 1.2 MW**. Procurement swaps **TX-2500 → TX-3150** *(all from capture)*.

> Suggested: "Then four agents get to work on Gemini: intake, power, cooling and procurement, all on one model."

### 8 · Agents at work, footage (10 s, time-compressed)
- **48 racks** at **132 kW** *(from capture)* drop into the hall; power and cooling route in parallel.
- Say that the footage is sped up; the burned-in tag shows the real multiple.

> Suggested: "They place 48 racks at 132 kilowatts. Power and cooling work side by side. This part is sped up."

### 9 · Physics checks, scene (8 s)
- The checker is deterministic code, with no LLM in the verdict path; the AI cannot mark its own homework.
- **149 checks · 147 pass · 2 fail** *(from capture)*; each failing one cites its clause.

> Suggested: "Now the checker runs. It is plain physics code, no LLM, so the AI cannot mark its own homework. 149 checks. Two fail."

### 10 · Checker, footage (15 s)
- Feeder **FA-01** drops **2.16%** against a **2.0%** limit, tender **§4.6** *(from capture)*.
- Every fix is re-checked against every rule before an agent may pick it; Power chose the parallel cable (**+$15,580**), Cooling the local drop (**+$420**) *(from capture)*.
- Revision **r2**: all pass.

> Suggested: "Feeder FA-01 drops 2.16 percent against a 2 percent limit. Every fix is re-checked against every rule before an agent can pick it. Revision two: all pass."

### 10b · From a finding to the tender page, footage (12 s) · voice file `b19-trust.wav`
- A failing finding cites its tender clause, here **§4.6** *(from capture)*. Say "failing": 37 of the 149 checks (R02, R03, R12) carry no clause chip.
- Click the chip and the PDF opens on that page, with a box around the exact quote, marked "Verified quote". The quote was found word for word, so anyone can check it.

> Suggested: "A failing finding cites its tender clause. Click it, and the PDF opens on that page, with a box around the exact quote. You can check us yourself."

### 11 · Lead-time swap, footage (10 s)
- The **2.5 MVA** unit has **0** in stock and a **98-week** lead time; the tender allows **26** *(from capture)*.
- Kirchhoff swaps to the **3.15 MVA** unit with **6** in stock and re-checks the fault level.

> Suggested: "It checks the supply chain too. The 2.5 MVA transformer is 98 weeks away. The tender allows 26. So it picks the 3.15 MVA unit in stock, and re-checks the fault level."

### 12 · What-if by voice, footage (12 s)
- In-clip question: "What if racks go to 200 kilowatts?"
- The engine re-runs every rule in about **8 ms**; **18 impact chains** light up across power and cooling *(from capture)*.

> Suggested: "Every rule re-runs in milliseconds, and you see exactly what breaks, across power and cooling."

### 13 · Sign-off, scene (6 s)
- Nothing ships until an engineer signs.
- The stamp carries the name, the time and the revision hash.

> Suggested: "Nothing goes out until an engineer signs. The stamp records who, when, and the exact revision."

### 14 · Review page, footage (6 s)
- Let the real stamp read. Optional line: "The review shows the diff and every assumption."

### 15 · Hand-off, scene (12 s)
- One signature updates every system: **7 purchase requisitions** *(from capture)* go to SAP S/4HANA, the documents are filed to Google Drive, and the CRM stage moves to **Design approved**.
- All three connectors are sandboxes in this demo.

> Suggested: "Once it is signed, the purchase requisitions go to SAP, the documents go to Google Drive, and the deal moves in the CRM. In this demo they are sandboxes."

### 15b · Beyond halls: grid and solar, footage (11 s) · voice file `b20-platform.wav`
- The same app and engine also handle a **132 kV** grid intake and a **5 MWp** solar plant, each with its own checks (the project names in the demo bundle).
- Say it lightly: this shows breadth, it is not a second product. Do not say the solar project is checked or signed; it is a draft.

> Suggested: "It is not only data-centre halls. The same engine also handles a 132 kV grid intake and a 5 MWp solar plant, each with its own checks."

### 16 · Google Cloud, scene (8 s)
- Gemini on Vertex AI proposes; the engine decides.
- It runs on Cloud Run, Firestore and Firebase.

> Suggested: "It runs on Google Cloud. Gemini on Vertex AI proposes, and our engine decides. Cloud Run, Firestore and Firebase do the rest."

### 16b · Measured numbers, scene (12 s) · voice file `b21-numbers.wav`
- Four numbers, each measured, each with its source on the card: **35 of 35** planted faults caught and no false alarms; **25 of 26** tender quotes verified; a **149 s** median from upload to a checker-clean design, time at the gates excluded; **$0.066** of Gemini per design.
- Say "6.6 cents" for $0.066, and say "about": it is one recorded run, not a promise.
- The card reads these numbers from the engine's own benchmark, the deck data and the recorded run; `tests/enterprise/test_video_numbers.py` fails if they drift.

> Suggested: "Four numbers, all measured. 35 of 35 planted faults caught. 25 of 26 quotes verified. 149 seconds, median, to a checked design. About 6.6 cents a design."

### 17 · End card (7 s)
- Say the URL slowly.

> Suggested: "Kirchhoff, by Team Ordinal. Try it at kirchhoff dot web dot app."

---

## Runtime check

| Block | Seconds |
|---|---|
| Product footage (beats 1, 5b, 6, 8, 10, 10b, 11, 12, 14, 15b) | 110 |
| Flow scenes (beats 5, 7, 9, 13, 15) | 47 |
| Title, intro, problem, Google Cloud, numbers, end (beats 2, 3, 4, 16, 16b, 17) | 51 |
| **Total without Jayadratha** | **208 (3:28)** |
| Jayadratha's optional intro | +7 → 215 (3:35) |

The intro scene lasts as long as the recording, plus 1 s. If Mehul's intro runs to 12 s, add 2 s; the total stays under 3:59. If the cut runs long, trim beat 14 first, then beat 8 to 8 s, then beat 5b to 12 s.

## Where each number comes from

| Number | Source read by the scenes |
|---|---|
| 132 kW per rack, 48 racks, 6.336 MW, 2N, 6 × 3.15 MVA, 9 × CDU 1.2 MW | `projects/hall-a.json`, last revision `model` |
| 149 checks, 147 pass, 2 fail; r2 149 pass, 0 fail | `projects/hall-a.json`, `revisions[].check_summary` |
| FA-01 2.16% > 2.0% (§4.6); H-Z2 over FB-03 (§6.3.4); fix costs | `projects/hall-a.json`, `findings.r1` |
| TX-2500 98 wk, stock 0 → TX-3150 stock 6; 26-week clause | ledger entry plus `integrations.json` ERP materials; R15 limit |
| Pursue, 6.34 MW, Telangana, 28 days to bid due, supply-swap sentence | `inbox.json` (`em-hall-b`) captured triage: `fit.reasons`, `fit.supply.text`, `fields` |
| 7 PRs, 13 lines, $5.83M; 4 documents; CRM "Design in progress → Design approved" | `projects/hall-a.json` `prs` and `crm`, `integrations.json` |
| Approver, time, hash cc379d7570ef | `projects/hall-a.json` `approvals`, `revisions[-1].hash` |
| 25/26 quotes verified (S4 intake lane, S10 numbers card) | `projects/hall-a.json` `brief.requirements[].verified` |
| 35 of 35 planted faults caught, 0 false alarms (S10 numbers card) | the engine's own benchmark, `kirchhoff.engine.benchmark`, run by `tests/engine/test_benchmark.py` |
| 149 s median over 3 live runs, $0.066 per design (S10 numbers card) | `deck/fill.yaml` (`upload_to_clean_median`, `usd_per_run`), kept in `scenes/lib/measured.js` and tied to it by `tests/enterprise/test_video_numbers.py` |
| 8 ms, 18 impact chains | product footage only (beat 12); read them off the recorded clip |
