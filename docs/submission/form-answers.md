# Hack2skill submission form: answers (AI Builder Cup 2026)

Source: the form as the Hack2skill dashboard shows it ("Prototype Submission"), captured on 16 Oct 2026 by Jayadratha (issue #32). Every field is required. **Do not submit until the FLAGS at the end are cleared.** Nothing personal goes in this file or in the repo.

**Closes:** Ending Date 18/10/2026 11:59:00 PM (IST), shown on the form. **We aim to submit by Sun 18 Oct 2026, 18:00 IST** (Mehul's handoff, 17 Oct), so there are hours left to fix a broken link before it closes.

## The fields

| Field (as the form labels it) | Limit | Our answer | Status |
|---|---|---|---|
| Challenges (drop-down) | one option | Future of Work & Enterprise Productivity | Check the option list; if this theme is missing, ask Mehul before choosing another. |
| Prototype Link Deployed on GCP or Cloud run | a URL | https://kirchhoff.web.app | Live (Firebase Hosting in front of Cloud Run). Must stay working through judging. |
| Final Prototype PPT/Deck converted into PDF | PDF, up to 5 MB | the PDF export of `docs/submission/deck/Kirchhoff-AI-Builder-Cup.pptx` | Export after the last deck build (screenshots #46, video link), then check the size: the screenshot PNGs alone are about 5.7 MB, so compress the images on export if the PDF is over 5 MB. |
| GitHub Repository Link (Public Access) | URL with https | https://github.com/mehular0ra/kirchhoff | **FLAG 2:** the repository is private today. |
| Demo Video Link (3-4 minutes) | a URL | the public YouTube link of the final video | **FLAG 1:** video not final. Length decided: 3:00 to 4:00 (Flag 1 below). |
| Brief Description of Your Solution | 1024 characters | the text below (1000 characters) | Ready. Check the numbers once more after any new run. |

## What the form's own instructions say (paraphrased)

- **Pitch deck:** it must use the prescribed template, and a different format may lead to disqualification. The built deck keeps the template's slide size, sections and order; it drops the template's instruction slide and fills the template's blank team slide.
- **Video:** a 3 to 4 minute demonstration that clearly shows the working solution. A video over the prescribed duration may be penalised or stop the submission progressing. A video that does not adequately show working functionality does not progress to the prototype evaluation.
- **Deployed prototype:** a valid, accessible link to a working prototype that stays functional through the whole evaluation. If the app, APIs or integrations are down during evaluation there are no retries or allowances.
- **GitHub repository:** accessible, with the relevant source and supporting material, and it must stay accessible through the evaluation.
- **Brief description:** what we built, including how we use Firebase, Firestore, Cloud Run and Gemini.
- **Links:** all submission links must work and be publicly accessible.

## Brief description (paste this)

<!-- BRIEF START -->
Kirchhoff by Ordinal turns a data-centre tender (PDF plus drawing) into a checked, engineer-signed power and liquid-cooling design. Gemini agents (Intake, Orchestrator, Layout, Power, Cooling, Procurement, Docs) propose the design; a deterministic engine and a clause-cited rule pack verify every number, so no figure on screen comes from the model's text. A human reviewer signs.

Google services: Gemini 3.8 Flash on Vertex AI, orchestrated with Google ADK (structured output, function calls); Gemini Live via Firebase AI Logic for the voice co-pilot; Cloud Run for the FastAPI API and a private ERP/CRM sandbox; Firestore for runs, revisions and events; Cloud Storage for tenders, calc reports and BOQs; Firebase Hosting and anonymous Auth for the React app.

Measured on live runs: a median of about 2.5 minutes from the start of a run to a checker-clean revision (gate waits excluded), about $0.07 per design. Demo companies and data are fictional; values are illustrative, not for construction.
<!-- BRIEF END -->

Numbers: the deck gives the same figures (slide numbers are the template's; in the PDF they are one page lower). Slide 12: median 149 s from the start of a run to a checker-clean revision over three live runs (143.8, 149.2 and 211.4 s), excluding the time spent waiting at gates. Slide 10: about $0.066 per design, measured on the golden-capture run of 16 Oct.

## Flags

1. **Video: length decided, file not final.** The form says 3 to 4 minutes; the terms and the organisers' pages we read on 15 Oct (see `checklist.md`) said under three. Mehul decided on 17 Oct to follow the form, because the form is what judges grade against: **3:00 to 4:00, target 3:30 to 3:50, hard ceiling 3:59**, spending the extra minute on the real working product (the form says that decides whether the entry progresses). If Hack2skill support (`support+aibuildercup@hack2skill.com`) answers differently before the upload, follow support. The export gate (`check_export.py`) rejects 180 s or more by default: run it alone with `--max-seconds 239`, and build the cut with `MAX_SECONDS=239` (PR #47's `assemble.sh` takes that variable; its v2 default becomes 239 s in that PR).
2. **Repository visibility.** Private today; the form needs public access and the repository must stay accessible. Mehul flips it (one toggle, owner only), after the final README and the last secrets scan (#26).
3. **Deck PDF** only after the last deck build, with the video link filled in on the links slide.
4. **Challenges list** has not been seen: choose from what the drop-down offers.
5. **Edit after submit** is unknown, so submit only the final versions.
