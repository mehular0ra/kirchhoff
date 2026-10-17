# Handoff to Jayadratha: everything until submission

Written Sat 17 Oct 2026, 15:45 IST, by Mehul's Claude Code session. **From now on, Jayadratha owns all of it: reviews, merges, deploys, the video, the deck, the form and making the repo public.** Mehul may have poor internet until Sun 18 Oct evening. Reach him on WhatsApp only for the three things that need him (§7).

> **Read §1 and §2 first, then work through §4 in order.** §5 has ideas for making the submission stand out, and §6 has the safety rules that still apply.

---

## 1. Deadlines and decisions already made

| What | Decision |
|---|---|
| **Submission closes** | **Sun 18 Oct 2026, 23:59 IST**, as shown on the form. **Aim to submit by Sun 18 Oct, 18:00 IST.** Nothing can be fixed once it's late. |
| **Video length** | **3:00 to 4:00** (Mehul's decision, 17 Oct, following the form's "Demo Video Link (3-4 minutes)"). Target **3:30–3:50**; the hard ceiling is **3:59**. The terms page said "under 3:00", but the form is what judges grade against. If Hack2skill support says otherwise before you upload, follow support. |
| **The gate** | The form says a video that "does not adequately show working functionality" doesn't progress. **Spend the extra minute on the real product**, not on more motion graphics. |
| **UI freeze** | Still in force. The live site stays on `e2aa0f9` unless you find a judge-path bug. See §4.1 for PR #50. |
| **Names and titles** | "Mehul Arora · AI engineer · Team Ordinal" and "Jayadratha Gayen · AI research engineer · Team Ordinal". **No "founder" or "CEO" anywhere.** |
| **Labels** | Keep "all companies, people and data are fictional" and "IEC-based, illustrative values, not for construction" wherever product data is shown. |
| **Licence** | Apache-2.0. `LICENSE` and `NOTICE` are done. |
| **Voice of the video** | Mehul can't record more. **You narrate the walkthrough in your own natural voice.** Mehul's intro uses his recorded take (§4.2). |

## 2. How you work now (new rules, approved by Mehul on 17 Oct)

- **You may push and merge to `build` directly.** You no longer need Mehul's session to merge, and `AGENTS.md` says so.
- **Every PR goes through a review loop before merge.** A fresh reviewer agent reviews, you fix, and you repeat. **Stop after 4–5 rounds, or as soon as a round finds no real issues, whichever comes first.**
- **Then request a review from `@mehular0ra` on the PR** (Reviewers → mehular0ra) and leave a one-line summary of the rounds. Mehul reviews when he's online. Don't block submission-critical work on him: merge, and he follows up.
- **Keep what already worked:**
  - TDD and `make test` green;
  - `make check-types` if contracts are touched;
  - the trust rules (spec §6.3);
  - PRs small and single-purpose.
- **`ws1-engine` … `ws4-infra` are stale.** Branch from `build` only.
- **GitHub access:** you have **write**, which is the maximum a personal-account repo allows. You can push, merge, create releases and manage issues and PRs. **You can't change repository settings or visibility.** Making the repo public needs Mehul (§7).
- **GCP:** you have 12 curated roles (Cloud Run admin, Hosting, rules, App Check, Storage, Secret Manager, monitoring, Cloud Build, Artifact Registry, Datastore user, viewer, Service Usage). **Plus Editor (granted 17 Oct, 16:00 IST)**, so you can decide things yourself. Only IAM changes and billing still need Mehul (Owner).

## 3. Where things stand (17 Oct, 15:45 IST)

**Live site and checks**
- **Live:** https://kirchhoff.web.app on **`e2aa0f9`**, the light theme, which you deployed on 16 Oct. `build` is at the commit that adds this file.
- **Nothing to redeploy:** nothing under `apps/`, `services/`, `scenarios/` or `infra/` has changed since `e2aa0f9`. Redeploy only if you merge app code.
- **Checks at `e2aa0f9`:** 800 pytest, 320 vitest, tsc, lint (0 errors, 20 existing warnings), build, demo-world drift check; local e2e 28/28 (static 18, phone 10).

**Voice and inbox**
- **Gemini Live:** connects (your #35 test with synthesised audio). **A real human voice through a real mic is still untested.** Do it once while filming §4.3.
- **Vindhya email:** Decline is correct (the verified email body names a 33 kV switchyard, which is a substation). The e2e test now reads the verdict from the bundle (#7).

**Deck**
- `uv run --script docs/submission/deck/build_deck.py` builds 15 slides.
- The only open slots are the screenshots (your PR #46) and `links.demo_video` in `fill.yaml`.
- The uncited "4–8 weeks" baseline was removed from slide 12's notes. **Don't quote any number we didn't measure or can't cite.**

**Video**
- **Plan:** `docs/submission/video/edit-plan-v2.md` (17 beats, 2:39 as planned) and the talking points in `docs/submission/video-script-v2.md`.
- **Motion scenes:** HTML in `docs/submission/video/scenes/`, rendered by `render.py`.
- **Your seven footage clips:** they're on your machine.

**Captions** (`docs/submission/video/transcribe.py`)
- It now uses **Cloud Speech-to-Text Chirp 2** (us-central1, en-IN, with phrase hints for our names). Gemini was blocked by Vertex's safety filter on most calls, and flash-lite invented timings.
- `--engine gemini` still exists, but don't rely on it.

**Intro audio**
- `render.py` now trims, denoises and normalises the intro voices itself (-16 LUFS).

**Open PRs, all yours and none reviewed yet**

| PR | What it is |
|---|---|
| #46 | Deck screenshots |
| #47 | `assemble.sh` v2 |
| #48 | Footage tool fixes |
| #49 | Form answers |
| #50 | UI proposal |

## 4. Tasks, in order

### 4.1 Review and merge the open PRs (Sat evening)

Use the §2 loop. Suggested order: **#48 → #46 → #49 → #47**, small ones first.

- **#46 (deck shots)**
  - Open every PNG. Check for no dark leftovers, no error banners, no empty states, and no personal data. Fictional `.example` emails are fine.
  - Run `uv run --script docs/submission/deck/build_deck.py` and confirm there are no `[SHOT ]` lines left.
- **#48 (footage tool):** test-only changes; typecheck `e2e/` with `npm run typecheck`.
- **#49 (form answers)**
  - Update the video flag to the 3–4 minute decision.
  - Recount the brief description's characters (≤ 1024).
  - Check every claim against `docs/submission/gcp-brief.md`.
  - If you add Speech-to-Text to the services list, only do so if the final captions use it. They will, but it's a tooling detail, so keeping it out of the brief is fine.
- **#47 (assemble v2): rebase on `build` first.** Three things changed under it:
  - `render.py` already cleans and normalises the intro voices, so **don't normalise them a second time** in `assemble.sh`.
  - `transcribe.py` defaults to Chirp; check that the SRT it writes is the one `assemble.sh` burns in, on the final timeline.
  - The length cap moves to the new ceiling: set the default `MAX_SECONDS` to **239** and keep the export gate.
  - Exercise it end to end on synthetic inputs before trusting it on the real cut: ffmpeg `testsrc2` clips and `sine` WAVs with the right names.
- **#50 (UI proposal, glass theme and YC-style landing): your call, but my recommendation is don't merge before submitting.**
  - The screenshots, footage and QA are all on `e2aa0f9`. A theme change now risks regressions and a video that doesn't match the live site.
  - **Don't change the live site after the deadline either.** Judges should see what was submitted, and only hackathon-period code counts.
  - If you still want the landing page alone, merge just that piece before Sun 12:00 IST. Then rerun the full checks (`make test`, `cd e2e && E2E_LOCAL=1 npx playwright test --project=static --project=phone`), redeploy web, and reshoot any affected deck screenshots and footage.

### 4.2 Voices (Sat evening)

**Mehul's intro**
- His 20 s recording (take 3) is in a **draft release** that only collaborators can see: https://github.com/mehular0ra/kirchhoff/releases (look for "Handoff: Mehul's intro voice").
- Download `mehul-intro-take3-raw.wav`, then **delete the draft release**.
- It reads well, but has two slips to cut. Times are in the raw file; listen in Audacity and adjust by ±0.1 s:
  1. **About 4.5–5.0 s:** an "uh" between "Hi, I'm Mehul." and "Jayadratha". Leave about 0.3 s of pause.
  2. **About 10.25–10.95 s:** "pop– uh" between "a checked" and "power". Cut so it reads "a checked power and cooling design".

  ```
  ffmpeg -i mehul-intro-take3-raw.wav -af "aselect='not(between(t,4.5,5.0)+between(t,10.25,10.95))',asetpts=N/SR/TB" mehul-intro.wav
  ```
- Check the result with `transcribe.py` (below). It should read: "Hi, I'm Mehul. Jayadratha and I built Kirchhoff, so AI data-centre teams can go from a tender to a checked power and cooling design in minutes, and an engineer still signs it." Chirp may hear "built" as "build"; his "built" is soft.
- If the cut sounds unnatural, ask Mehul on WhatsApp for a fresh take. He records it offline (`ffmpeg -y -f avfoundation -i ":1" -ac 1 -ar 48000 -t 20 ~/Downloads/intro_mehul.wav`; device `:1` is his MacBook mic, `:0` is Loom) and sends the WAV when he has signal.

**Your intro:** the WAV you shared on Drive (about 14 s).

**Render both intro scenes** from the repo root:
```
uv run --with playwright==1.64.0 python docs/submission/video/scenes/render.py docs/submission/video/scenes/out/ \
  --scenes s1b-intro-mehul,s1c-intro-jayadratha --intro-mehul mehul-intro.wav --intro-jayadratha jay-intro.wav
```
Each intro scene is its speech plus 1 s. Look at three stills; the photo, lower third and waveform should be in sync.

**Your narration (the walkthrough voice-over)**
- One WAV per beat, recorded in a quiet room with your mouth about 20 cm from the mic. Speak naturally, in your own Indian English; don't put on an accent.
- The talking points are in `video-script-v2.md`; where it says "Mehul reads", you read. Rephrase freely, but **every number you say must come from the product or the deck's measured figures.**
- Find your mic's index with `ffmpeg -f avfoundation -list_devices true -i ""`, then record:
  ```
  ffmpeg -y -f avfoundation -i ":<mic index>" -ac 1 -ar 48000 -t 30 vo/b04-problem.wav
  ```
- Run each WAV through the same clean-up: high-pass at 80 Hz, `afftdn=nr=12:nf=-48`, short fades, `loudnorm=I=-16:TP=-1.5:LRA=11`. It's the filter chain in `render.py`'s `trim_silence`. Trim first, then clean: normalising first lifts the room noise, and the trim can't find the speech.

**Captions** (word-timed, on the final timeline):
```
GOOGLE_CLOUD_QUOTA_PROJECT=ordinal-mep uv run --python 3.12 --with google-cloud-speech \
  python docs/submission/video/transcribe.py --beats vo/beats.json --out docs/submission/video/captions-v2.srt
```
`beats.json` is `[{"wav": "vo/b04-problem.wav", "start": 31.2}, …]`, with each start being where that voice begins in the final cut. Read every cue once: the wording is what you said, and only the glossary changes spellings.

### 4.3 The 3:30–3:50 cut (Sat night → Sun morning)

Start from `edit-plan-v2.md`'s 17 beats (2:39) and **add about 60–70 s of real product**. My suggested additions, best first:

1. **A real voice question, in a human voice** (+12 s). Your voice, a real mic, the live site: "Why did FA-01 fail?" The drawer opens on FA-01 and the answer reads "… 2.16% against 2.0% … Cost Δ +$15,580 · ΔV 0.84%". This closes the last #35 item too.
2. **The bids inbox triage** (+12 s). Six emails get Pursue, Clarify or Decline with reasons. The scanned BOQ is marked "Not verified (scan)", and the Vindhya email shows a deterministic Decline. Then "Pursue" opens Hall B.
3. **Trust, shown not told** (+10 s). Click a requirement chip and the PDF opens on the cited page with a box around "shall not exceed 2.0%" and "✓ Verified quote". Say: "No number on screen comes from the language model. Every number is the engine's, and every requirement is a verified quote."
4. **The what-if at 200 kW per rack** (+8 s, if it's not already in v08). It's the strongest frame in the product: 60 findings in 18 impact chains, lit in 3D, in about 8 ms after warm-up.
5. **Grid and solar asset packs** (+8 s). The same engine on a 132 kV line and a 5 MWp solar field, which shows it's a platform, not a demo.
6. **Measured numbers on one card** (+6 s), only as measured:
   - 35 of 35 seeded faults caught, with 0 false positives;
   - a median 149 s from upload to a checker-clean revision, over 3 live runs, excluding human gates;
   - about $0.066 per design run;
   - intake recall 0.78–0.84, with 25 of 26 quotes verified.
7. **Close on "try it"** (+4 s). kirchhoff.web.app with a QR code, no login needed (anonymous sign-in), and fictional data labelled.

**Build it**
- With #47 merged: `PLAN=v2 MAX_SECONDS=239 ./docs/submission/video/assemble.sh <work_dir>`. Add your new beats to its beat list in the same format.
- Then run the export gate (`check_export.py`). **Watch the whole video once, start to finish, with sound,** before uploading.
- **Pacing:** no shot runs longer than about 12 s without something changing on screen. Burn in "time-compressed ×N" wherever footage is sped up.
- **Music:** optional, and only if it's clearly licensed (YouTube Audio Library, "attribution not required"), about 20 dB under the voice. Silence is better than a licence risk.

**Upload**
- YouTube, **Public** (the form needs links "publicly accessible"; *Unlisted* is the fallback only if Public is blocked).
- Title: "Kirchhoff by Ordinal: AI designs, physics checks, an engineer signs (AI Builder Cup 2026)". The description has the live URL and the repo link.
- Test the link in an incognito window.

### 4.4 Deck PDF (Sun morning)

1. Put the YouTube URL in `docs/submission/deck/fill.yaml` → `links.demo_video`.
2. Run `uv run --script docs/submission/deck/build_deck.py --strict`, which must report no open slots.
3. Open the `.pptx` and look at every slide: no overflow, and the photos are right.
4. Export to **PDF (≤ 5 MB)** in PowerPoint, Keynote or LibreOffice.
5. Check that the PDF's QR codes and links work.

### 4.5 README, secrets scan, public repo (Sun morning; needs Mehul for one click)

This is issue #26.

1. Promote `docs/submission/README-draft.md` to the root `README.md`. Add a hero GIF or screenshot, the "try it in 60 seconds" path, the Google Cloud services, how to run it locally, and the licence.
2. **Secrets and personal-data scan across all history and branches:**
   - `gitleaks git --log-opts="--all" -v` (`brew install gitleaks`);
   - `git log --all -p | grep -nE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}' | grep -viE 'example|noreply'`.
   - The Firebase web API key in `apps/web/.env.*` is public by design.
   - Anything else (a key, a token, a real email) must be fixed before the repo goes public. Ask Mehul if it needs a history rewrite.
3. Delete the stale branches you don't need.
4. **WhatsApp Mehul to flip the visibility:** GitHub → kirchhoff → Settings → General → Danger Zone → Change visibility → Public. It takes 30 seconds on his phone.
5. Check the repo URL in an incognito window.
6. Tag the release: `git tag -a v1.0-submission -m "AI Builder Cup 2026 submission" && git push origin v1.0-submission`. Fast-forward `main` to `build` (`git push origin build:main`).

### 4.6 Submit the form (Sun, by 18:00 IST)

- Use `docs/submission/form-answers.md` (PR #49): theme "Future of Work & Enterprise Productivity", the live URL, the deck PDF, the public repo URL, the public YouTube URL, and the brief description (≤ 1024 characters).
- **Before you press submit**, open each link in incognito. Clear the form's flags: video length (now decided), the repo being public, and the final deck.
- Screenshot the confirmation and post it on #32.

### 4.7 Judging window, 19 Oct – 6 Nov (`docs/runbooks/judging-window.md`)

- **The site must stay up with no retries.** Check https://kirchhoff.web.app daily: the landing loads, Hall A opens, the co-pilot answers "why FA-01", and the inbox loads.
- Uptime and budget alerts are configured (`kirchhoff-usd200`, alerts at 50% and 90%). Keep a warm Cloud Run instance if cold starts show.
- **App Check enforcement (#15) is optional.** Turn it on only after a real-Chrome token check passes on the live site, and with a rollback ready. If you're unsure, leave it unenforced; a broken demo costs far more than the hardening gains.
- **Don't change the live site's code** during judging unless something is broken.

## 5. Ideas to make it stand out

**Video**
- **The first 7 seconds decide attention.** Open on the 3D hall turning green when the R11 clash resolves (already planned), with the voice already speaking. No logo intro.
- **One story, end to end:** a tender email arrives → triage → the agents design → the checker catches 2 real failures → fixes chosen by cost → the ERP swaps a 98-week transformer for stock → an engineer signs. Each beat answers "what changed for the engineer?"
- **Say the tagline once, clearly:** "AI designs. Physics checks. An engineer signs." It's the whole pitch.
- **Show the humans:** a 1–2 s shot of your hands, or the screen with you at the mic during the voice question, makes it feel real.
- **Captions on for the whole video.** Judges often watch muted.
- **Google Cloud depth is 40% of the score.** Name the services as they act on screen, not in a list:
  - "Gemini 3.8 Flash on Vertex AI, orchestrated by Google ADK";
  - "Gemini Live through Firebase AI Logic";
  - "Cloud Run";
  - "Firestore streams every agent event";
  - "Firebase Auth gives every judge a private workspace".

**Live site** (judges will click)
- Try the judge path cold, in incognito, on a phone and on a laptop: landing → tour → Hall A → why FA-01 → what-if → review → inbox → integrations → asset packs. Fix only what's broken.

**Deck**
- One slide on **how trust works**: quotes verified with pdfplumber, numbers only from the engine, deterministic checks with clause citations, a human signature.
- Use only the measured metrics, and name where each comes from (the golden capture, live runs of 15–16 Oct).

**README:** a 20-second GIF at the top, "Try it: https://kirchhoff.web.app (no login)", the architecture diagram (the mermaid one is already in the draft), and one paragraph per Google Cloud service saying what it does for us.

## 6. Safety rules that still apply

- **No emails, keys or personal data in commits.** Gate every commit on a scan that aborts:
  ```
  ! git diff --cached | grep -E '^\+' | grep -nE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}' | grep -viE 'example|noreply' && git commit …
  ```
- **Never run `services/api/tests/enterprise/test_infra_appcheck.py` or `infra/*.sh` from an agent unless `PATH` is sanitised.** The fakes once fell through to real gcloud and switched App Check to ENFORCED (15 Oct).
- **Pass `--project=ordinal-mep` on every gcloud command.** Never change the gcloud default project.
- **Never `rm -rf` shared folders, and never bare `git stash`.** Agents remove only their own worktrees.
- **Voice recordings and photos stay out of git** (`scenes/.gitignore` covers `audio/*.wav`). Share them over Drive or as draft-release assets.

## 7. What only Mehul can do (WhatsApp him)

1. **Make the repo public** (§4.5). It's one toggle and only the owner can do it.
2. **A fresh intro take**, if the edited take 3 sounds wrong (§4.2).
3. **Anything that needs the GCP Owner role:** IAM changes and billing.
