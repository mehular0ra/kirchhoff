# Judging-window runbook (19 Oct to 6 Nov 2026)

How we keep https://kirchhoff.web.app up and unchanged while the judges use it. Written for issue #26. It covers what runs, what to check, what we may change, and how to roll back. Facts below were read from the repo and the live project on Thu 15 Oct 2026 (build `94b741c`); anything marked **confirm** is not something the runner could verify.

**Dates.** Official submission deadline Sun 18 Oct 2026 (no time or timezone published); our internal deadline is Sat 17 Oct, 20:00 IST. Judging runs 19 Oct to 6 Nov, finalists are announced 7 Nov, the finale is 4 Dec in Singapore. The site should stay up through the finale decision, not only to 6 Nov.

## What has to stay up

| Piece | Where | Notes |
|---|---|---|
| The web app | Firebase Hosting, site `kirchhoff` (https://kirchhoff.web.app) | static bundles, the demo world and the PDFs; the first screen a judge sees |
| The API | Cloud Run `kirchhoff-api`, `asia-south1`, public behind Hosting `/api/*` | live runs, co-pilot, voice fallback, inbox triage |
| The ERP/CRM sandbox | Cloud Run `kirchhoff-enterprise`, `asia-south1`, **private** | reached only by the API with a service identity |
| Data | Firestore and Cloud Storage in `ordinal-mep` | runs, steps, events, exports; the seeded sandbox |
| Models | Vertex AI (Gemini) for agents; Firebase AI Logic for the browser's Live voice | live runs and voice call Gemini |

## State at the start of judging (fill in when the release is tagged)

- Release tag: `v1.0-submission` (Mehul pushes it) at commit: **[sha]**.
- Deployed revisions: `kirchhoff-api-`**[rev]**, `kirchhoff-enterprise-`**[rev]**; Hosting release time: **[time]**.
- Smoke result on that deploy: `smoke OK: https://kirchhoff.web.app`.
- App Check: **[unenforced / enforced on: …]** (see "App Check" below).
- Voice: **[Live works / push-to-talk only / off]**.

## Scaling and cost

Both services already run with a warm instance, so there is no cold start for a judge: `kirchhoff-api` min 1, max 3 (2 vCPU, 2 GiB, CPU always allocated); `kirchhoff-enterprise` min 1, max 2 (set in `infra/deploy_api.sh`, read back from the live services on 15 Oct). **No `min-instances` change is needed.**

An always-on instance bills around the clock, including 19 days of judging. Order of magnitude: a few US dollars per day for the API at list prices (check the Cloud Run pricing page for `asia-south1` and the billing report; do not rely on this figure). Live runs add Gemini usage, which depends on how many judges click Run live.

- The budget in `infra/budget_setup.sh` is USD 200 equivalent (INR 17,600) with alerts at 50% and 90%. **Confirm with Mehul that it exists and who receives the alerts**; the runner has no billing permission and cannot read it.
- Uptime checks exist for `/` and `/api/health` (5-minute period) with alert policies and two notification channels each (read from Monitoring on 15 Oct).
- If the 50% alert fires early, the first levers are `--max-instances` and the live-run guard, not turning the demo off. Decide with Mehul.

## Daily check (two minutes, from the repo root)

1. `./infra/smoke.sh` and expect `smoke OK: https://kirchhoff.web.app`. It checks `/api/health`, that `/api/whoami` and the sandbox proxy reject anonymous callers, the SPA shell, cache headers, the signed Hall A bundle and that PDFs are served as PDFs.
2. Open https://kirchhoff.web.app in a private window: the landing page loads, `/app` shows the dashboard, `/app/p/hall-a` shows the signed Hall A (r2 all pass) and the what-if chip lights the impact chain.
3. Look at the two uptime alerts and the budget alert mail; nothing new.
4. No run is stuck: `cd services/api && GOOGLE_CLOUD_PROJECT=ordinal-mep GOOGLE_CLOUD_QUOTA_PROJECT=ordinal-mep uv run python ../../infra/live_runs.py` prints `live runs holding a lease: <n>`; a lease is fresh only while a run is genuinely working (see `infra/live_runs.py`).
5. Post a one-line status on issue #6 only when something changed.

Every `gcloud` call in this repo names `--project=ordinal-mep`. Never run `gcloud config set project`.

## What we may change during judging

The golden path is frozen. Allowed changes, each as a **tagged release**:

- a defect that blocks a judge from reaching the signed design, the workspace or a live run;
- a secret or data-exposure problem;
- a static-bundle fix that makes a number wrong.

Rules for any release:

1. Build from a throwaway worktree of the tag with raw blobs, and check the seeded PDFs' hashes (a Windows checkout rewrites PDFs and CSVs with CRLF and corrupts them; see `golden-capture.md` and the deploy notes on #6).
2. **No run holds a lease.** `infra/deploy_api.sh` checks this itself and refuses otherwise. **Never `FORCE=1` during judging**: it can cut a judge's run in half.
3. `make seed-enterprise` only if the seeded sandbox or documents changed.
4. `./infra/deploy_api.sh`, then `./infra/deploy_web.sh`, then `./infra/smoke.sh`, then the voice smoke (a POST of a small `.webm` to `/api/voice` must answer anything but 411).
5. Post the revisions, the smoke result and the reason on issue #6.

Not allowed: schema or contract changes, new features, App Check enforcement toggles without Mehul's explicit go, IAM changes by the runner.

## Rolling back

**API or sandbox.** Cloud Run keeps every revision. Find the last good one and shift all traffic to it (no rebuild, takes seconds):

```bash
gcloud run revisions list --service=kirchhoff-api --region=asia-south1 --project=ordinal-mep
gcloud run services update-traffic kirchhoff-api --region=asia-south1 --project=ordinal-mep \
  --to-revisions=<last-good-revision>=100
```

Same for `kirchhoff-enterprise`. Check with `./infra/smoke.sh` afterwards. To move forward again, route 100% to the newest revision the same way, or deploy normally.

**Hosting.** Firebase console, Hosting, release history, Rollback on the previous release. Then `./infra/smoke.sh`.

**Rules (Firestore or Storage).** Redeploy the previous `firestore.rules` or `storage.rules` from the release tag with `./infra/deploy_web.sh` from a worktree of that tag.

## When something breaks

| Symptom | First checks | Likely action |
|---|---|---|
| The site does not load or `/api/health` is not 200 | Uptime alerts; `./infra/smoke.sh`; Hosting release time; Cloud Run service status | Roll back the last release (above) |
| Live runs fail early | `gcloud logging read` for `kirchhoff-api` errors; the failing step in the run; a 403 on Storage means the runtime service account lost a role (`infra/iam_setup.sh` lists them, including `serviceusage.serviceUsageConsumer`) | Fix the cause, never the check; ask Mehul before any IAM change |
| Live runs are slow or 429 | Vertex AI quota page for the project; recent bursts of runs | Wait; reduce `--max-instances` only with Mehul's go |
| The Checker or an engine number looks wrong | Reproduce on the signed Hall A first (static, no cloud) | Tagged release only after Mehul reviews |
| Voice does not answer | Browser console on the Hall A workspace; Live: is the Firebase AI Logic API enabled and configured (`firebasevertexai.googleapis.com`); push-to-talk: `/api/voice` status | Typed co-pilot still works; leave voice off the demo path until fixed |
| The budget alert fires | Billing report by service for the last 24 hours | Decide with Mehul before changing anything |

## App Check

App Check is a staged item (issue #15). Facts that matter for judging:

- A real, non-automated Chrome obtains a token; automated Chromium gets `403 App attestation failed` and is then throttled by the SDK for 24 hours. The web code does not show an error when the token fails (`appCheckToken()` returns `null`).
- Once enforced, anything automated (live-run tests, screenshot scripts) is rejected unless it uses the registered debug token. So run all automated captures and screenshots **before** enforcing, and re-test the whole golden path in a real browser right after.
- Enforcement is Mehul's decision. The script is `infra/appcheck.sh` (PR #22; **not on `build` yet when this was written**, so check it has landed): it needs an explicit confirmation to enforce and has an `unenforce` that restores the open state.

## Contacts and hand-over

Mehul owns releases, IAM and the budget; Jayadratha runs the cloud steps under issue #6. Anything that needs a human decision goes on issue #6; no personal contact details or secrets belong in the repo.
