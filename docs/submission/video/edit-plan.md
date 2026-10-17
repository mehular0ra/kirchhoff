# Kirchhoff demo video — edit decision list

Built from `docs/submission/video-script.md` (2:45 storyboard, 308 VO words, locked wording)
and GitHub issue #25 (clip naming, capture rules). This is the kit for Friday's edit: it does not
change a word of the script. Clip names below assume Jayadratha follows issue #25's naming —
`vNN-<beat>.mp4`, one clip per storyboard beat, in storyboard order, with 2 s handles before and
after each clip.

**Do not type any on-screen value in post.** Every number burned into a lower-third or caption
must come from the actual recorded clip for that beat. Where this plan shows a number from the
script, it is a placeholder to match against the real footage, not a value to re-create by hand.

## Clip map (per issue #25 naming)

| Beat | Clip file |
|---|---|
| 1 Cold open | `v01-cold-open.mp4` |
| 2 Title | `v02-title.mp4` |
| 3 Problem | `v03-problem.mp4` |
| 4 Tender in | `v04-tender-in.mp4` |
| 5 Agents at work | `v05-agents-at-work.mp4` |
| 6 Checker | `v06-checker.mp4` |
| 7 ERP lead-time swap | `v07-erp-swap.mp4` |
| 8 What-if by voice | `v08-what-if-voice.mp4` |
| 9 Sign-off | `v09-sign-off.mp4` |
| 10 Integrations | `v10-integrations.mp4` |
| 11 Grid and Solar | `v11-grid-solar.mp4` |
| 12 Proof | `v12-proof.mp4` |
| 13 End card | `v13-end-card.mp4` |

If Jayadratha's actual filenames differ even slightly, rename to this table before running
`assemble.sh` — the script matches by exact filename.

---

## Beat-by-beat EDL

### Beat 1 — Cold open (`0:00–0:10`, 10 s)
- **Clip:** `v01-cold-open.mp4` — in at clip 0:02.0 (past the 2 s handle), out at clip 0:12.0.
- **VO:** "Coolant piping, routed above a live power feeder. Kirchhoff caught it, cited the tender clause, and fixed it."
- **On-screen text:** none — let the chip "R11 · Tender §6.3.4 · no liquid above electrical" and the revision tick r1 → r2 read as recorded. Fictional-data banner must stay visible throughout.
- **Zoom/crop/speed:** none. This is the hook; keep it full speed and let the camera move (wide → fly-in) play as shot.
- **Transition in:** hard cut from black (cold open, no logo).
- **Transition out:** hard cut to title card.
- **Verify against golden capture:** the chip text and the revision bar values (r1 → r2) must match exactly what's on screen — no retyping.

### Beat 2 — Title (`0:10–0:16`, 6 s)
- **Clip:** `v02-title.mp4` (title card over the held green-hall frame from beat 1's end state) — static, 6 s.
- **VO:** "This is Kirchhoff. AI designs. Physics checks. An engineer signs."
- **On-screen text:** "Kirchhoff by Ordinal" + "AI designs. Physics checks. An engineer signs." (verbatim from script/deck tagline).
- **Zoom/crop/speed:** none.
- **Transition in:** cut from beat 1's green hall.
- **Transition out:** cut to TEAM SLOT A or the problem caption card.

### Beat 3 — Problem (`0:16–0:26`, 10 s)
- **Clip:** `v03-problem.mp4` = [TEAM SLOT A, optional, 3–4 s] + dark caption card (remainder of the 10 s).
- **VO:** "AI halls need power and liquid cooling designed together. And engineers check AI by hand: only 6 percent trust its results unverified."
- **On-screen text:** dark card: "Only 6% of engineers trust AI results without verification." Source line (small, bottom): "Omni Calculator, AI adoption in engineering."
- **Zoom/crop/speed:** none.
- **Transition in:** cut from title card.
- **Transition out:** cut to Hall B workspace.
- **Open item:** TEAM SLOT A is optional — if the team doesn't supply it, hold the dark caption card for the full 10 s instead; no runtime change either way.

### Beat 4 — Tender in (`0:26–0:42`, 16 s)
- **Clip:** `v04-tender-in.mp4`.
- **VO:** "Drop in the tender. Gemini reads it, and a requirement only counts if its quote is found on the cited page. Intake even catches the client contradicting itself. The engineer approves the plan."
- **On-screen text/lower-thirds:**
  - On the Intake lane: let the "✓ quote verified" cards and the "N/M quotes verified" counter read as recorded — **do not type the N/M value**.
  - On the §2.3 chip / PDF open: none extra, the clause box highlight is the visual.
  - On the contradiction shot: optional lower-third "§4.2 '2N' vs Appendix B 'block or distributed'" if the on-screen text is too small to read at 1080p; otherwise let the UI carry it.
  - Fictional-data banner visible.
- **Zoom/crop/speed:** a light push-in (105–110%) on the "quotes verified" counter and on the §2.3 chip click can help legibility; no speed change.
- **Transition in:** cut.
- **Transition out:** cut to agent lanes.
- **Verify against golden capture:** the "N/M quotes verified" counter value.

### Beat 5 — Agents at work (`0:42–0:55`, 13 s)
- **Clip:** `v05-agents-at-work.mp4`.
- **VO:** "Agents place 48 racks at 132 kilowatts each. Power and Cooling work in parallel: a 2N electrical system and nine 1.2-megawatt CDUs."
- **On-screen text/lower-thirds:** burned-in "TIME-COMPRESSED" tag (top corner) + elapsed-time clock running throughout the beat, both per the script's own rule for this beat.
- **Zoom/crop/speed:** **this is the compressed beat.** Measure the real captured run length `L` (agent lanes → 48-rack drop → SLD staging → cooling pipe routing) and set the speed factor to `L / 13 s`, rounded to a clean multiple (e.g. 4×, 6×, 8×). **Label whatever the real multiple is** — do not default to "sped up 8×" unless the math actually gives ~8×. `assemble.sh` takes this factor as a parameter; compute it after Friday's capture.
- **Transition in:** cut from tender beat.
- **Transition out:** cut to the compliance matrix.
- **Verify against golden capture:** 48 racks, 132 kW, "2N", "9 × CDU · 1.2 MW" must all read from the Cooling lane / SLD as captured.

### Beat 6 — Checker (`0:55–1:23`, 28 s) — longest beat
- **Clip:** `v06-checker.mp4`.
- **VO:** "Then the checker runs. It's deterministic, with no LLM in the verdict path, so the AI can't mark its own homework. 149 checks: 147 pass, two fail, each citing its clause. Feeder FA-01 drops 2.16 percent against a 2 percent limit. Every fix is re-checked against every rule before an agent may pick it."
- **On-screen text/lower-thirds:**
  - "Every number checked against IEC-based rules" as a lower-third over the matrix fill, first 4–5 s of the beat.
  - On the R05 finding drawer: let "82 m feeder", "2.16% vs 2.0%", "§4.6" chip read as recorded.
  - On the fix cards: "2,000 A busway · 1.66% · +$11,480" and "parallel cable · 0.84% · +$15,580" as recorded, plus a small checkmark/highlight on whichever Power actually picked.
  - On the R11 drawer: "§6.3.4" chip, "local drop · +$420 · 1 pipe" / "reroute · −$910 · 2 pipes", highlight Cooling's actual pick.
  - Fictional-data banner visible throughout.
- **Zoom/crop/speed:** this beat has four sub-shots (matrix fill → R05 drawer → R11 drawer → diff/"r2 all pass"). If the fix-selection process itself was a long agent loop on camera, time-compress just that sub-segment with its own honest multiplier and tag, same rule as beat 5. The matrix counter fill and drawer reads should stay full speed for legibility.
- **Transition in/out:** cuts between the four sub-shots; cut out to the ERP beat.
- **Verify against golden capture:** 149/147/2 split, "2.16% against a 2%" (FA-01), the fix dollar deltas, and the final "r2 · all pass" — all five numbers must match the actual recorded run exactly, including which fix each agent actually chose (the VO is generic enough not to name the chosen fix, so no VO change is needed even if the choice differs from the script's example).

### Beat 7 — ERP lead-time swap (`1:23–1:40`, 17 s)
- **Clip:** `v07-erp-swap.mp4`.
- **VO:** "It checks the supply chain too. The 2.5 MVA transformer has a 98-week lead time; the tender allows 26. Kirchhoff swaps to a 3.15 MVA unit in stock, and re-checks the fault level."
- **On-screen text:** none needed beyond the UI's own card text ("2.5 MVA · stock 0 · lead time 98 wk > 26 wk (§2.3) · R15 fail" → "3.15 MVA · stock 6 · 38.07% / 76.15%" → "fault level 60.45 → 65.42 kA ✓"), let it read as recorded.
- **Zoom/crop/speed:** push-in on the card swap transition so the before/after numbers are both legible; no speed ramp (this is a fast UI swap, not a long agent run).
- **Transition in/out:** cuts.
- **Verify against golden capture:** 98-week vs 26-week, 2.5 MVA vs 3.15 MVA, stock 0 vs 6, the two loading percentages, and the fault-level numbers (60.45 → 65.42 kA) — six separate values to confirm.

### Beat 8 — What-if by voice (`1:40–1:56`, 16 s)
- **Clip:** `v08-what-if-voice.mp4`. In-clip audio: team member asks "What if racks go to 200 kilowatts?" (~3 s, live on the clip's own audio track, not VO — do not record this as part of `vo.wav`).
- **VO (after the in-clip question):** "The engine re-runs every rule in about 8 milliseconds. 18 impact chains light up across power and cooling: transformers at 113.6 percent, cooling zones over capacity."
- **On-screen text:** none required — the chips "R01 113.6%", "R02 2,343 A", "R08 2,560 kW > 2,400 kW" and the "60 findings · 18 impact chains" counter should read as recorded.
- **Zoom/crop/speed:** none; real-time is the point (the ~8 ms re-run is literally instant on screen, so don't speed this one up).
- **Transition in:** cut from the ERP beat.
- **Transition out:** cut to the review page.
- **Open item:** the in-clip question's real spoken length (TEAM SLOT B) will not be exactly 3 s — once recorded, shift the VO-start marker in this beat to right after the question actually finishes, and re-time this beat's two caption cues (cues 25–28 in `captions.srt`) to match.
- **Verify against golden capture:** "about 8 milliseconds" response time, "18 impact chains", "113.6 percent", and the "60 findings" counter.

### Beat 9 — Engineer sign-off (`1:56–2:12`, 16 s)
- **Clip:** `v09-sign-off.mp4`.
- **VO:** "Nothing ships until an engineer signs. The review shows the diff and every assumption, then stamps the revision hash. Approval raises purchase requisitions in the ERP and moves the CRM deal."
- **On-screen text/lower-thirds:** lower-third "An engineer signs" when the review page appears (reinforces the tagline; the default static `v09-sign-off` clip, the approved Hall A r2 review page, has no Approve click); let its stamp "Priya Raman · Lead Electrical Engineer (Reviewer) · time · revision hash" read as recorded. A signed live run (`v09-sign-off-live`) would instead show "You (Demo Reviewer)", the Approve click, and the PRs and the CRM stage. The stamp is a must-show item (see checklist below).
- **Zoom/crop/speed:** push-in on the stamp once the review page has settled (with a signed live run, `v09-sign-off-live`: at the Approve click); none elsewhere.
- **Transition in/out:** cuts.
- **Verify against golden capture:** the revision hash and timestamp on the stamp (don't fabricate a hash if the recorded one is hard to read — crop tighter instead).

### Beat 10 — Integrations (`2:12–2:19`, 7 s) — first to cut if over time
- **Clip:** `v10-integrations.mp4`.
- **VO:** "Engineering, procurement and sales, in one workflow."
- **On-screen text:** keep the "sandbox (simulated)" labels and the fictional-data banner visible (required disclaimer, not optional even if this beat is trimmed).
- **Zoom/crop/speed:** none; this beat is already the shortest non-title beat.
- **Transition in/out:** cuts.
- **Open item:** per the script's own rule, drop this beat first if the cut runs long — integrations are repeated conceptually in beat 9 (ERP/CRM) and beat 12 (Cloud Run/Firestore/Firebase), so cutting it loses no must-show item, only the explicit "ERP (SAP-style)/CRM (Salesforce-style)" screens. If dropped, also remove its two caption cues and VO line from the mix, which brings the runtime to 2:38.

### Beat 11 — Grid and Solar (`2:19–2:27`, 8 s)
- **Clip:** `v11-grid-solar.mp4`.
- **VO:** "Same engine, new asset packs: a 132 kV grid line, and a five-megawatt-peak solar field."
- **On-screen text:** none beyond the UI's own cards; let "STR-28 · 327 tables · ~5,036 kWp · DC/AC 1.26 · clear-sky yield ~2,639 kWh/kWp (clear-sky only)" read as recorded if legible, otherwise crop in.
- **Zoom/crop/speed:** crop-in on the Solar field card if the full card text is too small at 1080p.
- **Transition in/out:** cuts.
- **Verify against golden capture:** the solar field numbers (5,036 kWp, DC/AC 1.26, 2,639 kWh/kWp).

### Beat 12 — Proof (`2:27–2:37`, 10 s)
- **Clip:** `v12-proof.mp4` = static hold on the architecture diagram (deck slide 8), minimum 8 s per the script, plus the three overlay tiles.
- **VO:** "It caught all 35 seeded design faults, with zero false positives. Built on Gemini, ADK, Cloud Run, Firestore and Firebase."
- **On-screen text/lower-thirds:** three overlay tiles — "35/35 seeded faults caught", "0 false positives", "byte-identical output" — timed to appear as each clause is spoken. This is the single beat carrying the most must-show tech-stack mentions (Gemini, ADK, Cloud Run, Firestore, Firebase all appear here, either in the diagram or the VO) — do not trim below 8 s.
- **Zoom/crop/speed:** slow, continuous push-in across the full 10 s on the architecture diagram (keeps a static slide from feeling dead); tiles fade in/out, no speed ramp on the diagram itself.
- **Transition in/out:** cuts.
- **Verify against golden capture:** "35/35", "0 false positives", "byte-identical" are deck/benchmark numbers (14 Oct checker run), not from Friday's live capture — confirm they still hold if the checker rule pack changes before Friday.

### Beat 13 — End card (`2:37–2:45`, 8 s)
- **Clip:** `v13-end-card.mp4` = [TEAM SLOT C: team photo of Mehul Arora and Jayadratha].
- **VO:** "Kirchhoff, by team Ordinal, for the future of work. Try it at kirchhoff dot web dot app."
- **On-screen text:** "Kirchhoff by Ordinal · Future of Work & Enterprise Productivity · kirchhoff.web.app" + small print: "Demo companies, people and data are fictional · IEC-based, illustrative values, not for construction." Both disclaimers must appear here per the script's own rule, even if dropped elsewhere.
- **Zoom/crop/speed:** none; hold static.
- **Transition in:** cut from the proof beat.
- **Transition out:** fade to black (end of video).
- **Open item:** TEAM SLOT C (team photo) must be supplied before final assembly — without it, fall back to text-only end card (logo + URL + disclaimers), which still satisfies every must-show item except the photo.

---

## Runtime budget table

| Beat | In | Out | Duration | Running total |
|---|---|---|---|---|
| 1 Cold open | 0:00 | 0:10 | 10 s | 0:10 |
| 2 Title | 0:10 | 0:16 | 6 s | 0:16 |
| 3 Problem | 0:16 | 0:26 | 10 s | 0:26 |
| 4 Tender in | 0:26 | 0:42 | 16 s | 0:42 |
| 5 Agents at work | 0:42 | 0:55 | 13 s | 0:55 |
| 6 Checker | 0:55 | 1:23 | 28 s | 1:23 |
| 7 ERP lead-time swap | 1:23 | 1:40 | 17 s | 1:40 |
| 8 What-if by voice | 1:40 | 1:56 | 16 s | 1:56 |
| 9 Sign-off | 1:56 | 2:12 | 16 s | 2:12 |
| 10 Integrations | 2:12 | 2:19 | 7 s | 2:19 |
| 11 Grid and Solar | 2:19 | 2:27 | 8 s | 2:27 |
| 12 Proof | 2:27 | 2:37 | 10 s | 2:37 |
| 13 End card | 2:37 | 2:45 | 8 s | **2:45** |

**Total: 2:45 (165 s).** Hard limit: strictly under 3:00 (180 s). **Headroom: 15 s (8.3%).**

If beat 10 is dropped (first cut per the script's rule), total falls to **2:38 (158 s)**, 22 s of
headroom. Do not drop any other beat without re-checking the must-show list below — every other
beat carries at least one item nothing else covers.

---

## Must-show checklist (for judges, muted or not)

- [ ] Live URL on screen: `kirchhoff.web.app` — beat 13 end card (also check beat 11's title bar / browser chrome if visible in any clip).
- [ ] "Gemini" mentioned or shown — beat 4 VO ("Gemini reads it"), beat 12 VO + diagram.
- [ ] "Vertex AI" shown — beat 12 architecture diagram only (not in VO; confirm the diagram slide actually has "Vertex AI" legible at 1080p, crop in if needed).
- [ ] "Cloud Run" mentioned — beat 12 VO + diagram.
- [ ] "Firebase" mentioned — beat 12 VO + diagram (Firestore also called out separately in the same line).
- [ ] "ADK" shown — beat 12 VO + diagram.
- [ ] The trust rule (no LLM in the verdict path / deterministic checker) — beat 6 VO, first sentence.
- [ ] The engineer signing — beat 9 (VO + stamp visual) and reinforced in the beat 2 tagline and beat 13 end card.
- [ ] Fictional-data / illustrative-values disclaimer visible — banner in-app wherever shown (beats 1, 4, 6, 10) and explicit small print on the end card (beat 13), per the script's own rule that the end card carries both disclaimers regardless of what's trimmed.
- [ ] Clause citation ("§" references) visible at least once with the matching finding — beats 1, 4, 6, 7.

---

## Audio rules

- **Voiceover:** `vo.wav`, Mehul, single take per beat preferred so re-syncs are localized; no processing beyond basic noise reduction and normalization before mixing.
- **In-clip audio:** beat 8's spoken question ("What if racks go to 200 kilowatts?") is captured live on `v08-what-if-voice.mp4`'s own audio track — keep it as sync audio, do not replace with a VO re-read.
- **Music bed:** per the script's own rule ("keep the music bed low and duck it under the voiceover"), one royalty-free bed is permitted. **No licensed music** — this is a hard submission rule (checklist.md: T&C *Rules of Conduct* item 2 bans third-party-protected content). If a music bed is used:
  - Source it from a royalty-free library that grants a clear usage licence for competition/commercial use (e.g. YouTube Audio Library, Pixabay Music, or a CC0 track).
  - Note the exact track name, source URL and licence type in this file before final export (**open item** below — not yet chosen).
  - Duck it to roughly −18 to −20 dB under the VO (sidechain compress keyed off `vo.wav`), and silence it entirely during the beat 8 in-clip question.
  - If no suitable royalty-free track is found in time, ship with **VO only** — silence is always compliant; a wrong music choice is a disqualification risk.
- **Mix target:** final mix at **−14 LUFS integrated** (see export settings).

## Export settings

- **Resolution:** 1920×1080 (1080p), 16:9.
- **Codec:** H.264 (`libx264`), `yuv420p` pixel format for broad compatibility.
- **Frame rate:** match the capture rate (issue #25 asks for 60 fps where possible); 30 fps is also fine if that's what was captured — don't mix rates within one timeline, conform everything to one rate before concat.
- **Loudness:** **−14 LUFS integrated** (YouTube's own target; avoids YouTube's automatic turn-down and keeps the VO consistent against judges' other submissions).
- **Captions:** burn in per the script's rule ("burn the voiceover in as captions"); use the re-synced `captions.srt`. They go in a **caption band under the picture** (the picture at 90 %, 1728 x 972, inside the 1920 x 1080 frame, so a caption never covers the app's own text): `assemble.sh` does it through `caption_band.sh` and then runs the export gate `check_export.py` (16:9, picture untouched, every caption inside the band). Issue #25.
- **Container:** `.mp4`.
- **Bitrate:** target ~12–16 Mbps video for 1080p30, or ~16–20 Mbps for 1080p60; use a quality-based encode (`-crf 18` to `-crf 20`) instead of a hard bitrate cap if the export tool supports it.

## YouTube upload steps (public link required)

1. Sign in to the channel used for the submission (confirm with Mehul which account or channel to use).
2. Upload the final export (`final.mp4`).
3. **Visibility: Public.** Not Unlisted, not Private — the checklist's own FLAG #2 calls this out explicitly; Unlisted will not satisfy "public YouTube... link."
4. **Title:** `Kirchhoff — AI designs. Physics checks. An engineer signs. | AI Builder Cup 2026`
5. **Description** (include the live URL and a repo URL placeholder — fill the repo URL once the repo is made public, checklist FLAG #1):
   ```
   Kirchhoff is an AI MEP design platform for AI data-centre halls: AI designs,
   physics checks, and an engineer signs.

   Gemini agents draft power and liquid-cooling designs for AI data halls. A
   deterministic checker — no LLM in the verdict path — proves every number
   against cited tender clauses and IEC-based rules. ERP lead times shape the
   equipment choice. Nothing ships until an engineer signs.

   Live demo: https://kirchhoff.web.app
   Source code: [REPO URL — fill in once the GitHub repository is public]

   Built with Gemini, Google ADK, Cloud Run, Firestore and Firebase, for the
   AI Builder Cup 2026 (Future of Work & Enterprise Productivity).

   Team Ordinal: Mehul Arora, Jayadratha.

   Demo companies, people and data shown are fictional. Engineering values
   are IEC-based and illustrative, not for construction.
   ```
6. **Tags:** `AI Builder Cup`, `Kirchhoff`, `Gemini`, `Google ADK`, `Cloud Run`, `Firestore`, `Firebase`, `data center design`, `MEP`, `AI agents`, `electrical engineering`, `liquid cooling`.
7. Category: Science & Technology.
8. Thumbnail: use a frame from beat 1 (the red-to-green hall reveal) or beat 12 (architecture diagram) — whichever reads better at thumbnail size.
9. Copy the resulting `https://youtu.be/...` or `https://www.youtube.com/watch?v=...` link into the submission form and into deck slide 14 (per checklist.md's final sequence, step 3).
10. Double-check visibility is still **Public** after any post-upload edit (YouTube sometimes defaults re-edits to the last-saved visibility — verify, don't assume).

---

## Open items

1. **Every VO number must be re-verified against Friday's actual recorded clips, not against the 14-Oct numbers the script was written from.** The script's "Where each claim comes from" table sources these numbers to engine runs on 14 Oct, but checklist.md flags that the golden capture / UI freeze (#24) and the footage shoot (#25) both happen Fri 16 Oct, after the script was drafted. The VO wording is locked and cannot change, so if Friday's run produces different numbers, the fix must be on the visual/edit side (recapture the run so it matches, or tightly crop so an inexact-but-close value isn't legible) — never retype a value. Numbers to re-check, beat by beat: 48 racks / 132 kW / 2N / 9×1.2 MW CDUs (beat 5); 149/147/2 and FA-01's 2.16% vs 2% (beat 6); 98 wk vs 26 wk, 2.5 MVA vs 3.15 MVA, stock 0 vs 6, 60.45→65.42 kA (beat 7); ~8 ms, 18 chains, 113.6%, 60 findings (beat 8); 35/35 and 0 false positives (beat 12, likely stable since it's a separate benchmark run, not the live capture — confirm it wasn't invalidated by any rule-pack change before Friday).
2. **Beat 8's in-clip question length is unknown until recorded (TEAM SLOT B).** The script estimates ~3 s; captions and the VO-start marker for this beat must be re-timed once the real clip exists.
3. **TEAM SLOT A (beat 3, optional) and TEAM SLOT C (beat 13, team photo) are not yet supplied.** Beat 13 has a safe fallback (text-only end card); beat 3 has no required fallback since it's explicitly optional in the script.
4. **Music bed is not yet chosen.** A royalty-free track with a noted source and licence is optional per the script ("keep the music bed low..."); if none is picked in time, ship VO-only — do not use a licensed/unlicensed track under deadline pressure.
5. **Vertex AI's on-screen legibility in beat 12's architecture diagram is unverified** — the must-show checklist expects it readable at 1080p; crop/zoom if the deck slide's text is too small when held as full-frame video.
6. **No timing or claim problem was found that requires changing the script's wording** — all issues above are capture/sync risks, not script defects.
