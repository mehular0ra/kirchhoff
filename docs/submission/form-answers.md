# Hack2skill submission form: answers (AI Builder Cup 2026)

Source: the form as the Hack2skill dashboard shows it ("Prototype Submission"), captured on 16 Oct 2026 by Jayadratha (issue #32). Every field is required. **Do not submit until the FLAGS at the end are cleared.** Nothing personal goes in this file or in the repo.

**Closes:** Ending Date 18/10/2026 11:59:00 PM (IST), shown on the form. Our internal deadline stays Sat 17 Oct 2026, 20:00 IST.

## The fields

| Field (as the form labels it) | Limit | Our answer | Status |
|---|---|---|---|
| Challenges (drop-down) | one option | Future of Work & Enterprise Productivity | Check the option list; if this theme is missing, ask Mehul before choosing another. |
| Prototype Link Deployed on GCP or Cloud run | a URL | https://kirchhoff.web.app | Live (Firebase Hosting in front of Cloud Run). Must stay working through judging. |
| Final Prototype PPT/Deck converted into PDF | PDF, up to 5 MB | the PDF export of `docs/submission/deck/Kirchhoff-AI-Builder-Cup.pptx` | Export after the last deck build (screenshots #46, video link). The preview export is 1 MB, well under the limit. |
| GitHub Repository Link (Public Access) | URL with https | https://github.com/mehular0ra/kirchhoff | **FLAG 2:** the repository is private today. |
| Demo Video Link (3-4 minutes) | a URL | the public YouTube link of the final video | **FLAG 1:** video not final, and its length is unclear. |
| Brief Description of Your Solution | 1024 characters | the text below (939 characters) | Ready. Check the numbers once more after the last capture. |

## What the form's own instructions say (paraphrased)

- **Pitch deck:** it must use the prescribed template, and a different format may lead to disqualification. The built deck keeps the template's slide size, sections and order; it drops the template's instruction slide and adds a team slide before the thank-you slide.
- **Video:** a 3 to 4 minute demonstration that clearly shows the working solution. A video over the prescribed duration may be penalised or stop the submission progressing. A video that does not adequately show working functionality does not progress to the prototype evaluation.
- **Deployed prototype:** a valid, accessible link to a working prototype that stays functional through the whole evaluation. If the app, APIs or integrations are down during evaluation there are no retries or allowances.
- **GitHub repository:** accessible, with the relevant source and supporting material, and it must stay accessible through the evaluation.
- **Brief description:** what we built, including how we use Firebase, Firestore, Cloud Run and Gemini.
- **Links:** all submission links must work and be publicly accessible.

## Brief description (paste this)

<!-- BRIEF START -->
Kirchhoff by Ordinal turns a data-centre tender (PDF plus drawing) into a checked, engineer-signed power and liquid-cooling design. Gemini agents (Intake, Orchestrator, Layout, Power, Cooling, Procurement, Docs) propose the design; a deterministic engine and a clause-cited rule pack verify every number, so no figure comes from the model. A human reviewer signs.

Google services: Gemini 3.8 Flash on Vertex AI, orchestrated with Google ADK (structured output, function calls); Gemini Live via Firebase AI Logic for the voice co-pilot; Cloud Run for the FastAPI API and a private ERP/CRM sandbox; Firestore for runs, revisions and events; Cloud Storage for tenders, calc reports and BOQs; Firebase Hosting and anonymous Auth for the React app.

Measured on live runs: about 2.5 minutes from upload to a checker-clean revision, roughly $0.07 per design. Demo companies and data are fictional; values are illustrative, not for construction.
<!-- BRIEF END -->

Numbers: the deck's slides 10 and 11 give the same figures (median 149 s over three live runs, about $0.066 per design, from the golden capture and the live runs of 15 and 16 Oct).

## Flags

1. **Video length.** The form says 3 to 4 minutes. The terms and the organisers' pages we read on 15 Oct (see `checklist.md`) say strictly under three minutes. Both cannot be met. Exceeding the duration is the penalised case, so a cut just under 3:00 (2:55 to 2:59) is the safe middle until support answers; it is also a little more room to show the working product, which the form says decides whether the entry progresses. Mehul decides; support is `support+aibuildercup@hack2skill.com`. `assemble.sh` stops at 175 s unless `MAX_SECONDS` is set higher.
2. **Repository visibility.** Private today; the form needs public access and the repository must stay accessible. Mehul changes this, after the final README and the last secrets scan (#26).
3. **Deck PDF** only after the last deck build, with the video link filled in on the links slide.
4. **Challenges list** has not been seen: choose from what the drop-down offers.
5. **Edit after submit** is unknown, so submit only the final versions.
