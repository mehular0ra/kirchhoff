# Submission checklist (AI Builder Cup 2026)

Built from the organisers' own pages, read on Thu 15 Oct 2026 (issue #32). Every row gives the **owner**, the **status** and the **source**. A **FLAG** marks something we do not have yet or that needs a decision. **Jayadratha fills in and submits the form** (decided by Mehul, 16 Oct). Since the 17 Oct handoff (`docs/HANDOFF.md`) Jayadratha owns the submission itself (video, deck, form, tag, deploys); Mehul only flips the repo to public, records a fresh intro if needed, and changes IAM and billing. The rows below that still name Mehul are his decisions as team lead.

**Deadline.** The official deadline is **Sun 18 Oct 2026, 11:59 PM IST**: the Hack2skill submission form shows "Ending Date 18/10/2026 11:59:00 PM (IST)" (seen 16 Oct; the home page and the terms give no time). Our target is to submit by **Sun 18 Oct 2026, 18:00 IST** (Mehul's decision, 17 Oct), six hours before the form closes. Judging runs 19 Oct to 6 Nov; finalists are announced 7 Nov; the finale is 4 Dec in Singapore.

**Sources.**
- **Home:** <https://aibuildercup.com/>
- **Challenges and requirements:** <https://aibuildercup.com/themes.html> (called *themes* below)
- **FAQ:** <https://aibuildercup.com/Faqs.html>
- **Terms and conditions:** <https://docs.google.com/document/d/e/2PACX-1vRm7ChZ6Ij9fG7uFDkxzUMpwgVeBmnQ6cMDnAIEEX84AiLBOOQ9cYbl3S5OzFBbcVb8TF55s-eVpiXb/pub> (called *T&C* below, cited by heading and item)
- **Registration and dashboard:** <https://hack2skill.com/event/aibuildercup2026/registration?isExternalLinkRedirection=true>
- **Organiser support:** support+aibuildercup@hack2skill.com

## What is still missing (read this first)

| # | FLAG | Owner | Needed by |
|---|---|---|---|
| 1 | The repo is **private**. It must be public, with the final README and the final gitleaks run (#26). | Mehul (visibility), Jayadratha (#26) | Sun 18 Oct, before the 18:00 submit |
| 2 | The **video** is not final (footage is recorded on the freeze build, the assembler is #47, the voiceover and captions are still to do) and needs a public link. **Its length is decided: 3:00 to 4:00, see row 9.** | Jayadratha | Sat night to Sun morning |
| 3 | With #46 merged, the **deck** builds with every screenshot (#17) and has one open slot, the video link on slide 14 (`links.demo_video`); the PDF is exported after the last build. The slide-14 text "(runs 2:45)" comes from `deck-content.md` and must say the final runtime before that build. | Jayadratha | Sun 18 Oct, after the video link |
| 4 | The **submission form** was seen on 16 Oct (a capture of the dashboard page): six required fields, answered in `docs/submission/form-answers.md`. Not yet seen: the option list of the Challenges drop-down. | Jayadratha | Sun 18 Oct, before the 18:00 submit |
| 5 | The form gives the cut-off (18 Oct, 11:59 PM IST), but nothing says whether a submission can be **edited or resubmitted** after saving, so submit only final versions. | Jayadratha (ask support) | Before the Sun 18:00 submit |
| 6 | **Each member's eligibility** (age, not a student, based in JAPAC) is for the member to confirm; the organisers may check IDs at any time. | Each member | Now |
| 7 | **Third-party licences** (npm and Python libraries, two fonts, an icon set): done, the root `NOTICE` lists them (#45, merged) and a test fails when a dependency has no entry. | Jayadratha | Done |
| 8 | **Done:** the golden capture of a successful live run is merged (#43, #24), so a judge's first click lands on a recorded run. | Jayadratha | Done |
| 9 | **Video length: decided (Mehul, 17 Oct): 3:00 to 4:00, following the form.** The form says 3 to 4 minutes and that a video that does not adequately show the working product does not progress to evaluation; the terms page said strictly under 3. Target 3:30 to 3:50, hard ceiling 3:59; spend the extra minute on the real product, not on motion graphics. If Hack2skill support answers differently before the upload, follow support. | Jayadratha | Before the upload, Sun 18 Oct |

## Deliverables the organisers require

The T&C list four items ("Technical Stack, Authenticity, and Freshness Standards", item 3): a live URL, a video, a public repository and a deck. The FAQ repeats the same four.

| Item | The organisers' words | Owner | Status | Source |
|---|---|---|---|---|
| **Live URL** | "A working deployed live URL (on Cloud Run/GCP/Firebase)." | Jayadratha (releases, deploys, #6) | `https://kirchhoff.web.app` is live on Firebase Hosting plus Cloud Run. Live on the freeze build `e2aa0f9`; redeploy only if app code changes. Must stay up through judging (19 Oct to 6 Nov); the `min-instances` decision is #26 and #31. | T&C item 3a; FAQ "What to submit" |
| **Demo video** | "strictly under three (3) minutes"; "a public YouTube or Vimeo video or public Google drive link (3 minutes)" | Jayadratha (cut, upload, footage #25) | Edit plan v2 runs 2:39 with Mehul's intro (2:46 with Jayadratha's optional intro); the handoff adds 60 to 70 s of real product, so trim to land in 3:30 to 3:50 (ceiling 3:59). Footage is recorded on the freeze build. **We follow the form's wording:** "a 3 to 4 minute video demonstration", field "Demo Video Link (3-4 minutes)", and the demonstration must clearly show the working solution (row 9). **FLAG:** the link must be **public**, not unlisted or private (Unlisted only as the fallback if Public is blocked). No music rules in the T&C, but "content protected under third party rights" is banned (*Rules of Conduct*, item 2), so use no licensed music. | T&C item 3b; themes (Mandatory Submission Items) |
| **Public GitHub repository** | "A public GitHub repository containing the source code." | Jayadratha (README, scan); Mehul flips the visibility | **FLAG:** private today (`mehular0ra/kirchhoff`). To make public before submitting. README is a draft (`docs/submission/README-draft.md`, #26). History audit (#16) is done: no secrets or personal data in file content; Mehul decided to leave the three metadata items (see #16). The root `LICENSE` is Apache-2.0 and `NOTICE` lists the third-party licences (#45). | T&C item 3c; FAQ |
| **Proposal deck** | "a comprehensive presentation deck explaining the solution architecture and business case"; "a deck/PPT converted into a PDF" | Jayadratha (content, screenshots #17, PDF export) | 16-slide template filled (`docs/submission/deck/Kirchhoff-AI-Builder-Cup.pptx`). **FLAG:** one open slot, the video link on slide 14 (`links.demo_video`); the screenshots are in #46; no PDF yet. The built deck already drops the template's instructions slide (15 slides). A PowerPoint export of the current build (preview only, not attached) renders slide 1 (the a, b, c list) and the wireframes slide (bullets and the 1 to 6 markers) correctly. The form takes the deck as a **PDF of up to 5 MB** and says it must use the prescribed template (a different format may be disqualified): the built deck keeps the template's slide size, sections and order, drops its instruction slide and fills its blank team slide. | T&C item 3d; themes |

## Other things the form or the rules ask for

| Item | What the organisers say | Owner | Status | Source |
|---|---|---|---|---|
| **Problem statement** | "Clearly identify the problem statement you are submitting for." One team, one statement. | Jayadratha | We use **Future of Work & Enterprise Productivity** (one of the six listed: BFSI, Retail & Commerce, Manufacturing, Media/Content/Digital Experiences, Future of Work & Enterprise Productivity, Sustainability & Social Impact). **FLAG:** the themes page also lists a different set of categories (Healthcare, Education, Sustainability, Accessibility, Social Good); choose from whatever the form offers and tell us if "Future of Work" is missing. | themes; FAQ ("one solution under one problem statement") |
| **Google Cloud stack** | "must leverage Google AI models (like Gemini or Gemma)"; "built primarily using the Google Cloud tech stack"; competing clouds are ineligible. | Mehul | Met: Gemini on Vertex AI through ADK, Cloud Run, Firebase Hosting, Firestore, Cloud Storage, Firebase AI Logic. `docs/submission/gcp-brief.md` explains it. **The brief is our own artefact; none of the organiser pages we read asks for one.** Submit it only if the form has a field. | T&C item 1; themes (Google Cloud Requirements) |
| **Fresh code and original assets** | "exclusively fresh code and original assets created during the official hackathon timeline"; "Pre-existing products ... will be disqualified." | Mehul | Met by repo rule (AGENTS.md: fresh code only, open-source libraries fine) and by the audited history. The demo world is authored and fictional. | T&C item 2; FAQ ("Only fresh projects ... are eligible") |
| **Third-party content** | No content "protected under third party rights"; no copyrighted content. The T&C have no open-source clause. | Jayadratha | **Met:** we use open-source libraries, `lucide-react` icons and the Inter and JetBrains Mono fonts; the root `NOTICE` and `LICENSE` (Apache-2.0) list them (#45, merged). The deck template is the organisers' own. | T&C *Rules of Conduct* item 2; *Intellectual Property Rights* item 3 |
| **Licence grant (decision for Mehul)** | Entrants grant the organiser "a worldwide, perpetual, irrevocable, non-exclusive license" to use the entry as marketing content, and the organiser has "a six-month right of first refusal on exclusive licenses". | Mehul | Not a blocker. Read it and decide before submitting; this is a business question, not a technical one. | T&C *Protection of Intellectual Property* item 7; *Intellectual Property Rights* item 1 |
| **Language** | All code, documentation and presentations in English. | Both | Met. | themes |
| **Team** | 2 to 4 members; no roster change after 14 Oct; only 2 members travel to the finale; members must stay on the Hackathon Dashboard and communication channels (leaving "may result in disqualification"). | Mehul | Two members (Mehul Arora, Jayadratha). The roster closed on 14 Oct, so no change is possible now. **FLAG:** both of us stay on the dashboard and Discord until results. | T&C *Hackathon Mechanism* items 1 to 5, *Rules of Conduct* item 5; FAQ |
| **Eligibility** | At least 21 years old at registration; working professionals, entrepreneurs or startups; "Students are not eligible" (one student disqualifies the team); physically based in, and legal residents of, JAPAC countries. The organiser may check government IDs, employment credentials and age at any point. | Each member | **FLAG:** each member confirms for themselves; nothing personal goes in this repo. | T&C *General Eligibility* items 4 to 8; home page; FAQ |
| **Registration / dashboard** | Submission goes through the Hack2skill dashboard (registration shows "Closed", the application status is still available). | Jayadratha | Not previewable without logging in; the form itself was seen on 16 Oct (row 4, and below). | home page |

## The form (seen on 16 Oct)

A capture of the Hack2skill dashboard page ("Prototype Submission") shows six required fields: Challenges (drop-down), Prototype Link Deployed on GCP or Cloud run, Final Prototype PPT/Deck converted into PDF (up to 5 MB), GitHub Repository Link (Public Access), Demo Video Link (3-4 minutes), and Brief Description of Your Solution (1024 characters, must say how we use Firebase, Firestore, Cloud Run and Gemini). The ready answers are in `docs/submission/form-answers.md`, with a test that checks the description length and the services it names. **Do not submit** until the video is final and public (row 2) and the repository is public (row 1).

Still to settle:

1. The **Challenges** drop-down options (we choose Future of Work & Enterprise Productivity if it is offered).
2. Can the entry be **edited or resubmitted** after the first save? (The FAQ is silent.) This decides whether a tagged release after submission can still be reflected in the deck or video.
3. Is a **Google Drive link** accepted for the video as "public" with "anyone with the link"? We plan on a public YouTube link.

Ask support at support+aibuildercup@hack2skill.com (Jayadratha asks, since he submits the form); the same email can ask about the video length.

## Judging criteria, for a last self-check

From themes. Weights add up to 100.

| Criterion | Weight | Where we show it |
|---|---|---|
| Technical merit and Gen AI implementation | 40% | Deck slides 8 and 9 (architecture, technologies) and 12 (benchmarks), the GCP brief, the trust rules in the README, the engine and replay tests |
| Problem alignment and impact | 25% | Deck slides 3 and 4 (idea, opportunities) and 13 (future development), the video's problem beat |
| Innovation and creativity | 25% | Deck slides 3 and 5 (idea, features), the voice co-pilot, the bids inbox |
| User experience and solution design | 10% | Deck slides 7 and 11 (wireframes, snapshots), the live site, accessibility work (icon plus text, keyboard) |

## Final sequence (suggested, Sat 17 to Sun 18 Oct)

1. Freeze check: `build` at the release candidate, deployed, smoke OK, no run holding a lease.
2. Repo public, README final, notice file in, gitleaks clean, tag `v1.0-submission` (Jayadratha tags and pushes it).
3. Deck PDF exported (slides 1 and 7 checked for bullet and numbering glitches), video public, both links in slide 14.
4. Fill the form from `docs/submission/form-answers.md`. **Jayadratha submits** by **Sun 18 Oct, 18:00 IST** (the form itself closes Sun 18 Oct, 11:59 PM IST).
5. Keep the site up and `min-instances` decided through 6 Nov; post-submission changes only as tagged releases, deployed with no runs active.
