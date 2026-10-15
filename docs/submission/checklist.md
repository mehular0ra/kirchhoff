# Submission checklist (AI Builder Cup 2026)

Built from the organisers' own pages, read on Thu 15 Oct 2026 (issue #32). Every row gives the **owner**, the **status** and the **source**. A **FLAG** marks something we do not have yet or that needs a decision. **Jayadratha fills in and submits the form** (decided by Mehul, 16 Oct).

**Deadline.** The official deadline is **Sun 18 Oct 2026**. The organisers publish **no time and no timezone** ([home page](https://aibuildercup.com/): "submit it before October 18"; the terms give none either). Our internal deadline is **Sat 17 Oct 2026, 20:00 IST**, so a wrong guess about the official cut-off costs nothing. Judging runs 19 Oct to 6 Nov; finalists are announced 7 Nov; the finale is 4 Dec in Singapore.

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
| 1 | The repo is **private**. It must be public, with the final README, a licence decision and the final gitleaks run (#26). | Mehul (visibility), Jayadratha (#26) | Sat 17 Oct, before submitting |
| 2 | The **video** is not recorded (script drafted, footage #25 after the Fri 12:00 IST freeze), and needs a public link. | Mehul (edit), Jayadratha (footage) | Sat 17 Oct |
| 3 | The **deck** still has `[TBD]` slots (slides 10, 12, 14, 15), no screenshots yet (#17) and no PDF. | Mehul (content), Jayadratha (shots, PDF) | Sat 17 Oct |
| 4 | The **submission form is behind the Hack2skill login**. We have not seen its fields, so every field in this list is inferred from the organisers' pages. | Mehul | Fri 16 Oct |
| 5 | The **cut-off time and timezone** for 18 Oct are unpublished, and the FAQ does not say whether a submission can be edited or resubmitted. | Mehul (ask support) | Fri 16 Oct |
| 6 | **Each member's eligibility** (age, not a student, based in JAPAC) is for the member to confirm; the organisers may check IDs at any time. | Each member | Now |
| 7 | **Third-party licences** (npm and Python libraries, two fonts, an icon set) have no notice file in the repo. | Jayadratha | Sat 17 Oct |
| 8 | A **successful live run** on the deployed site has not been captured yet (golden capture #24); a judge's first click depends on it. | Jayadratha (capture), Mehul | Fri 16 Oct, 12:00 IST |

## Deliverables the organisers require

The T&C list four items ("Technical Stack, Authenticity, and Freshness Standards", item 3): a live URL, a video, a public repository and a deck. The FAQ repeats the same four.

| Item | The organisers' words | Owner | Status | Source |
|---|---|---|---|---|
| **Live URL** | "A working deployed live URL (on Cloud Run/GCP/Firebase)." | Mehul (releases), Jayadratha (deploys, #6) | `https://kirchhoff.web.app` is live on Firebase Hosting plus Cloud Run. Redeploy before the capture is in progress. Must stay up through judging (19 Oct to 6 Nov); the `min-instances` decision is #26 and #31. | T&C item 3a; FAQ "What to submit" |
| **Demo video** | "strictly under three (3) minutes"; "a public YouTube or Vimeo video or public Google drive link (3 minutes)" | Mehul (edit and upload), Jayadratha (footage #25) | Script drafted, runtime 2:45 (15 s headroom). No recording yet. **FLAG:** the link must be **public**, not unlisted or private. No music rules in the T&C, but "content protected under third party rights" is banned (*Rules of Conduct*, item 2), so use no licensed music. | T&C item 3b; themes (Mandatory Submission Items) |
| **Public GitHub repository** | "A public GitHub repository containing the source code." | Mehul | **FLAG:** private today (`mehular0ra/kirchhoff`). To make public before submitting. README is a draft (`docs/submission/README-draft.md`, #26). History audit (#16) is done: no secrets or personal data in file content; Mehul decided to leave the three metadata items (see #16). No `LICENSE` file yet. | T&C item 3c; FAQ |
| **Proposal deck** | "a comprehensive presentation deck explaining the solution architecture and business case"; "a deck/PPT converted into a PDF" | Mehul (content), Jayadratha (screenshots #17, PDF export) | 16-slide template filled (`docs/submission/deck/Kirchhoff-AI-Builder-Cup.pptx`). **FLAG:** open `[TBD]` slots on slides 10 (cost), 12 (performance), 14 (links), 15 (team bios and photos); screenshots after the freeze; no PDF yet. The built deck already drops the template's instructions slide (15 slides). A PowerPoint export of the current build (preview only, not attached) renders slide 1 (the a, b, c list) and the wireframes slide (bullets and the 1 to 6 markers) correctly; the orange boxes are the screenshot placeholders. **No slide, page or file-size limit is published.** | T&C item 3d; themes |

## Other things the form or the rules ask for

| Item | What the organisers say | Owner | Status | Source |
|---|---|---|---|---|
| **Problem statement** | "Clearly identify the problem statement you are submitting for." One team, one statement. | Mehul | We use **Future of Work & Enterprise Productivity** (one of the six listed: BFSI, Retail & Commerce, Manufacturing, Media/Content/Digital Experiences, Future of Work & Enterprise Productivity, Sustainability & Social Impact). **FLAG:** the themes page also lists a different set of categories (Healthcare, Education, Sustainability, Accessibility, Social Good); choose from whatever the form offers and tell us if "Future of Work" is missing. | themes; FAQ ("one solution under one problem statement") |
| **Google Cloud stack** | "must leverage Google AI models (like Gemini or Gemma)"; "built primarily using the Google Cloud tech stack"; competing clouds are ineligible. | Mehul | Met: Gemini on Vertex AI through ADK, Cloud Run, Firebase Hosting, Firestore, Cloud Storage, Firebase AI Logic. `docs/submission/gcp-brief.md` explains it. **The brief is our own artefact; none of the organiser pages we read asks for one.** Submit it only if the form has a field. | T&C item 1; themes (Google Cloud Requirements) |
| **Fresh code and original assets** | "exclusively fresh code and original assets created during the official hackathon timeline"; "Pre-existing products ... will be disqualified." | Mehul | Met by repo rule (AGENTS.md: fresh code only, open-source libraries fine) and by the audited history. The demo world is authored and fictional. | T&C item 2; FAQ ("Only fresh projects ... are eligible") |
| **Third-party content** | No content "protected under third party rights"; no copyrighted content. The T&C have no open-source clause. | Jayadratha | **FLAG:** we use open-source libraries, `lucide-react` icons and the Inter and JetBrains Mono fonts. Add a short third-party notice (names, licences) to the README or a `NOTICE` file in #26. The deck template is the organisers' own. | T&C *Rules of Conduct* item 2; *Intellectual Property Rights* item 3 |
| **Licence grant (decision for Mehul)** | Entrants grant the organiser "a worldwide, perpetual, irrevocable, non-exclusive license" to use the entry as marketing content, and the organiser has "a six-month right of first refusal on exclusive licenses". | Mehul | Not a blocker. Read it and decide before submitting; this is a business question, not a technical one. | T&C *Protection of Intellectual Property* item 7; *Intellectual Property Rights* item 1 |
| **Language** | All code, documentation and presentations in English. | Both | Met. | themes |
| **Team** | 2 to 4 members; no roster change after 14 Oct; only 2 members travel to the finale; members must stay on the Hackathon Dashboard and communication channels (leaving "may result in disqualification"). | Mehul | Two members (Mehul Arora, Jayadratha). The roster closed on 14 Oct, so no change is possible now. **FLAG:** both of us stay on the dashboard and Discord until results. | T&C *Hackathon Mechanism* items 1 to 5, *Rules of Conduct* item 5; FAQ |
| **Eligibility** | At least 21 years old at registration; working professionals, entrepreneurs or startups; "Students are not eligible" (one student disqualifies the team); physically based in, and legal residents of, JAPAC countries. The organiser may check government IDs, employment credentials and age at any point. | Each member | **FLAG:** each member confirms for themselves; nothing personal goes in this repo. | T&C *General Eligibility* items 4 to 8; home page; FAQ |
| **Registration / dashboard** | Submission goes through the Hack2skill dashboard (registration shows "Closed", the application status is still available). | Mehul | Not previewable without logging in; **we have not seen the form**. | home page |

## Form dry run (step 2 of #32)

Not done: the Hack2skill dashboard needs a team login and shows nothing without it, so I did not log in with anyone's account. **Do not submit.** To finish this step, the person with the dashboard access can either (a) paste the field names and limits from the form here, or (b) tell me to look at it in their browser session. Questions to settle at the same time:

1. Is there a **cut-off time and timezone** on 18 Oct? (Not published; we plan for Sat 17 Oct, 20:00 IST.)
2. Can the entry be **edited or resubmitted** after the first save? (The FAQ is silent.) This decides whether a tagged release after submission can still be reflected in the deck or video.
3. Does the form take the **GitHub URL** only, or also a licence statement or a link to the brief?
4. Is a **Google Drive link** accepted for the video as "public" with "anyone with the link"? We plan on a public YouTube link.

Ask support at support+aibuildercup@hack2skill.com (Mehul, as team lead).

## Judging criteria, for a last self-check

From themes. Weights add up to 100.

| Criterion | Weight | Where we show it |
|---|---|---|
| Technical merit and Gen AI implementation | 40% | Deck slides 8 and 9 (architecture, technologies) and 12 (benchmarks), the GCP brief, the trust rules in the README, the engine and replay tests |
| Problem alignment and impact | 25% | Deck slides 3 and 4 (idea, opportunities) and 13 (future development), the video's problem beat |
| Innovation and creativity | 25% | Deck slides 3 and 5 (idea, features), the voice co-pilot, the bids inbox |
| User experience and solution design | 10% | Deck slides 7 and 11 (wireframes, snapshots), the live site, accessibility work (icon plus text, keyboard) |

## Final sequence (suggested, Sat 17 Oct)

1. Freeze check: `build` at the release candidate, deployed, smoke OK, no run holding a lease.
2. Repo public, README final, notice file in, gitleaks clean, tag `v1.0-submission` (Mehul pushes the tag).
3. Deck PDF exported (slides 1 and 7 checked for bullet and numbering glitches), video public, both links in slide 14.
4. Fill the form from this list. **Jayadratha submits** before **Sat 17 Oct, 20:00 IST**.
5. Keep the site up and `min-instances` decided through 6 Nov; post-submission changes only as tagged releases, deployed with no runs active.
