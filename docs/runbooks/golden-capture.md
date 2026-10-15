# Golden capture runbook (P4 Task 14)

Captures two live Hall B runs on the deployed stack (2N → Hall A, DR → Pune Edge), exports them from Firestore,
rewrites them deterministically into the static demo bundles, and redeploys. The static site, the deck screenshots
and the video all read this data, so it has to be right the first time.

- **Plan:** `docs/superpowers/plans/2026-10-13-p4-enterprise-demo-infra.md` Task 14 (and Task 10 for the capture
  module it drives) and its Global Constraints.
- **Ledger:** `.superpowers/sdd/2026-10-13-p4-enterprise-demo-infra/progress.md`.
- **Who runs what:** Jayadratha runs every command that touches GCP (issue #6). The controller verifies, commits
  and decides; it never runs a cloud write command.
- **Checked against `build` @ `54dff9d`** (this repo's current HEAD at the time this runbook was written).

---

## Readiness gaps (fix before or during capture)

| # | Gap | Status | Where | Smallest fix |
|---|---|---|---|---|
| 1 | `check_golden` does not raise `CaptureError` when the brief is missing | **MISSING** | `services/api/kirchhoff/enterprise/capture.py:112-135` (`check_golden`) | Add `if b.brief is None: problems.append("the brief is missing")` inside `check_golden`, plus a test in `services/api/tests/enterprise/test_capture.py` (e.g. clear `brief` on the fixture bundle and assert `CaptureError` with a "brief" match). This was flagged as a carry from Task 10 ("Important, one line + test") and was never applied — confirmed by reading the file: there is no brief check anywhere in `check_golden`, and no test in `test_capture.py` exercises a missing brief. |
| 2 | `_check_rewritten`'s leak guard does not check for the raw `uid` | **MISSING (minor)** | `services/api/kirchhoff/enterprise/capture.py:282-291` (`_check_rewritten`), called at `:274` | `export_run` already anonymises `uid` → `"visitor"` before `check_golden` runs (`capture.py:178`), so this is defense-in-depth, not a live leak. Smallest fix: thread `uid` through `to_static`/`_check_rewritten` and add it to the `leaks` tuple at `:285`, or skip it and accept the existing anonymisation as sufficient — note the decision either way. |
| 3 | `RunRecord.options` on the captured bundle | **DONE in code, untested** | `capture.py:254` (`run = r0.model_copy(update={...})` never touches `options`, so it survives from the live `RunRecord`) | No code change needed — `model_copy` only overwrites the keys you pass, and `_model(RunRecord, run_doc)` at `export_run` (`capture.py:147`) keeps whatever `options` Firestore has. Nothing in `test_capture.py` asserts `b.runs[0].options` is non-empty, so this is a **must-verify-by-hand** item (Step 4/6 below), not a demonstrated defect. P3-R6 (`OptionCards` reads `run.options`) depends on it. |
| 4 | Citation bboxes on captured findings | **DONE for the capture path** | `services/api/kirchhoff/runs/revisions.py:79-93` (`find_bbox`, fills `bbox` at live-run time, before Firestore is ever written); `capture.py`'s `_walk`/`to_static` never touches numeric fields, so a bbox already set at live-run time survives the rewrite untouched | Nothing to fix in `capture.py`. The separate issue #11/#14 problem (the *engine-built* `apps/web/public/demo/**` bundles showing bbox null) is a different code path (`scenarios/demo_world/build.py`) due tonight (BOARD.md issue #14, Thu 15 Oct 20:00) and is superseded for Hall A once the golden capture lands, since the capture is what will actually populate `apps/web/public/demo/projects/hall-a.json`. Verify post-capture (Step 6) that no citation has a null bbox where a quote and page exist. |
| 5 | 200 kW what-if: 60 findings / 18 chains | **ACTION ITEM, not a code gap** | `docs/submission/deck-content.md:513` already says: "Re-check every quoted number against the DEPLOYED Hall A bundle after the golden capture (P4 Task 14). The 200 kW what-if count changed from 62 to 60 once the signed revision used the R23 fix choice." | Re-measure against the captured, deployed Hall A bundle in Step 6/post-capture and update `docs/submission/deck-content.md`, `docs/submission/README-draft.md`, `docs/submission/video-script.md` and `docs/submission/deck/shots/README.md` if the number moved again. |
| 6 | Event visibility rule (`steps/{step}.attempt == event.attempt`) | **DONE** | `capture.py:148-152` (`done = {s.id: s.attempt for s in steps if s.status == "done"}`; `events = [... if done.get(e.step) == e.attempt]`) matches `docs/superpowers/plans/2026-10-13-interfaces.md:138` exactly | None. |
| 7 | Bids inbox precompute (I-2, `--backend adk`) at capture time | **CONDITIONAL — PR #8 is still OPEN** | `gh pr view 8 --repo mehular0ra/kirchhoff` → `state: OPEN`, `baseRefName: build`, not merged as of this writing | If PR #8 merges into `build` before the capture, add the Step 15 command from `docs/superpowers/plans/2026-10-14-bids-inbox.md:2512-2532` to the sequence below (it is listed there as a conditional step). If it has not merged, skip it — `scenarios/demo_world/build_inbox.py` already tolerates a missing `captures/inbox-triage.json` (`load_triage_capture` returns no triage, build_inbox.py:12 docstring: "folded in if present"), so `make demo-world` and the rest of the sequence are unaffected either way. |
| 8 | Deployed sha may be stale | **MUST CONFIRM** | GitHub issue #6 only shows comments through 15 Oct 04:49 IST instructing a deploy of `bd9311e`; `build` HEAD is 6 commits ahead (`54dff9d`), all of them e2e suite + submission docs, not the P3 UI fix wave (BOARD.md `UX-0`, "running") | Before starting, the controller must post a fresh "deploy `<sha>`" comment on issue #6 naming the `build` sha that includes the P2 final wave, the P3 fix wave (UX-0, App Check hang fix, tour step 3, 3D hall) and PR #8 if it has merged, and Jayadratha must confirm the redeploy before Step 2 below. Capturing against a stale UI makes the video/deck mismatch what ships. |

---

## Preconditions (checklist)

- [ ] **Deployed sha.** The controller has posted the target sha on issue #6 and Jayadratha has deployed it (`make deploy-api && make deploy-web`). It must include: the P2 final wave (Tasks 16–18 merged, or explicitly deferred by the controller), the P3 fix wave (UX-0: tour step 3, 3D hall readability, lane text, fix costs, App Check hang, contrast, bundle size), and PR #8 (bids inbox I-2) **if** it has merged by then (gap #7/#8 above).
- [ ] **Seed loaded.** `make seed-enterprise` has run against `ordinal-mep` (Jayadratha, issue #6 Part A step 3) — expect "60 materials, 9 opportunities" plus PRs and docs upload reported back on the issue.
- [ ] **CORS set.** `infra/storage_cors.sh` has run (issue #6 Part A step 2) — `gcloud storage buckets describe gs://ordinal-mep.firebasestorage.app --format='json(cors_config)'` returns a non-null `cors_config` (the plan's precondition check at P4 Task 12 described this as currently null before the fix).
- [ ] **Smoke green.** `./infra/smoke.sh` (or `make smoke`) prints `smoke OK: https://kirchhoff.web.app`.
- [ ] **App Check NOT yet enforced on Firestore.** Per BOARD.md, issue #15 (App Check, P4 Task 15) is staged but gated on Mehul's explicit "go" and targeted for Fri 16 Oct 12:00 — i.e. *after* this capture. Confirm with Jayadratha that enforcement has not been flipped on Firestore rules before Thu's capture, since `export_run`/`find_workspace_for_run` read Firestore directly with a service-account client, not through the App Check–gated client path, but a premature flip could still affect the live Hall B run itself (the browser client that drives P1–P4).
- [ ] **No live run holds a lease.** `cd services/api && GOOGLE_CLOUD_PROJECT=ordinal-mep GOOGLE_CLOUD_QUOTA_PROJECT=ordinal-mep uv run python ../../infra/live_runs.py` prints `live runs holding a lease: 0` (this is also enforced automatically by `infra/deploy_api.sh`, but check it before kicking off the capture run too, since a stray lease would also mean someone else is mid-run on Hall B).
- [ ] **`what_if`/`chip_what_ifs` present.** `cd services/api && uv run python -c "from kirchhoff.engine import api; assert hasattr(api, 'what_if') or hasattr(api, 'chip_what_ifs'); print('what-if OK')"` prints `what-if OK` (WS1 Task 15 — confirmed merged: WS1 is 15/15 per BOARD.md, so this should already pass).
- [ ] **Readiness gap #1 decided.** Either the `check_golden` brief-check fix (gap #1 above) has been applied and tested, or the controller has explicitly accepted the risk for this capture (the live Hall B run always has a brief from `p1.intake`, so the missing guard is a defense-in-depth gap, not a known live defect — but it should still be fixed before Thu if there's time, since it's a one-line change).

---

## Command sequence

Every step says who runs it. "Controller" never runs a command that writes to GCP; Jayadratha runs all cloud commands (per issue #6 and AGENTS.md "Do not deploy").

### 1. Confirm the deployed sha and preconditions

- **Controller:** Post the target sha on issue #6 if not already posted; read back Jayadratha's confirmation that `make deploy-api && make deploy-web && make smoke` succeeded against it.
- **Jayadratha:** Run the preconditions checklist above (seed, CORS, smoke, lease check, what-if check) and paste the output on issue #6.
- **Stop condition:** any checklist item fails → fix it and re-verify before continuing; do not start the live run against an unconfirmed deploy.

### 2. Check preconditions in code (plan Task 14, Step 2)

- **Jayadratha**, from `services/api`:
  ```bash
  cd services/api && uv run python -c "from kirchhoff.engine import api; assert hasattr(api, 'what_if') or hasattr(api, 'chip_what_ifs'); print('what-if OK')" && cd ../.. && ./infra/smoke.sh
  ```
- **Expected:** `what-if OK` then `smoke OK: https://kirchhoff.web.app`.
- **Stop condition:** if `what_if`/`chip_what_ifs` is missing, stop — the capture refuses to build Hall A without the five chips (`chip_what_ifs(..., required=True)`, `capture.py:268`). Ask the controller; this should not happen since WS1 is complete.

### 3. Record and export the Hall A golden run (2N)

- **Jayadratha**, from the repo root:
  ```bash
  E2E_OPTION=2N make e2e-live
  make capture-export RID=$(python3 -c "import json; print(json.load(open('e2e/out/live-run-2N.json'))['run_id'])") TARGET=hall-a
  ```
  `make e2e-live` drives the real browser through every gate automatically (`e2e/tests/live.spec.ts`): starts the run in Ask mode on `/app/p/hall-b`, approves the plan gate ("Compare all three topologies"), selects option `2N` at the option gate, opens the review screen, fills the review comment, clicks "Approve and sign as You (Demo Reviewer)", and verifies the PRs and CRM stage land before writing `e2e/out/live-run-2N.json`.
  `make capture-export` (added by this task to the Makefile — it does not exist on `build` yet) calls `scenarios/hall_a/capture.py export --rid <id> --target hall-a`, which is `kirchhoff.enterprise.capture.export_run` against live Firestore/GCS.
- **Expected:** `1 passed` from Playwright, then `…/scenarios/demo_world/captures/hall-a.json: revisions=['<rid>-r1', '<rid>-r2'] events=<n> prs=<6-7> option=2N`.
- **Stop condition:** `capture failed: …` names the missing piece (unsigned revision, blocked PRs, no CRM overlay, or — once gap #1 is fixed — a missing brief). **Fix the run, never the check** (re-run `E2E_OPTION=2N make e2e-live` after diagnosing why the live run didn't finish golden, e.g. a timed-out gate or a Vertex hiccup). Playwright's `test.setTimeout(15 * 60_000)` gives 15 minutes per attempt.

### 4. Verify it is the storyboard run

- **Jayadratha or controller** (read-only, no cloud write — this only reads the just-written local JSON file), from the repo root:
  ```bash
  python3 - <<'EOF'
  import json
  raw = json.load(open("scenarios/demo_world/captures/hall-a.json"))
  b = raw["bundle"]
  r1 = b["revisions"][0]["id"]
  fails = sorted(f["id"] for f in b["findings"][r1] if f["status"] == "fail")
  agents = sorted({e["agent"] for e in b["events"]})
  print("r1 fails", fails, "| option", b["runs"][0]["selected_option"], "| agents", agents)
  assert fails == ["R05:FA-01", "R11:H-Z2"], fails
  assert b["runs"][0]["selected_option"] == "2N"
  assert b["runs"][0]["options"], "RunRecord.options is empty — P3-R6 (OptionCards) will have nothing to show"
  EOF
  ```
  The `options` assertion is added here beyond the plan's own Step 4 script specifically to close readiness gap #3 before it reaches the static bundle.
- **Expected:** `r1 fails ['R05:FA-01', 'R11:H-Z2'] | option 2N | agents [...]` with at least intake, orchestrator, layout, power, cooling, procurement, checker and docs, and no assertion error.
- **Stop condition:** anything else is an engine or agent regression on the golden path (spec §3 relies on exactly these two findings) — report to the controller before continuing. An empty `options` list means stop and investigate P2's option-gate write before exporting again.

### 5. Record and export the Pune Edge run (DR)

- **Jayadratha:**
  ```bash
  E2E_OPTION=DR make e2e-live
  make capture-export RID=$(python3 -c "import json; print(json.load(open('e2e/out/live-run-DR.json'))['run_id'])") TARGET=pune-edge-1
  ```
- **Expected:** `1 passed` and `…/captures/pune-edge-1.json: … option=DR`.
- **Stop condition:** none that blocks the rest — if DR cannot reach all-pass in a live run, skip this step. The generator keeps the engine-built Pune Edge (ruling W17) and the obligation is reported as met by the fallback. Do not retry indefinitely; one or two attempts is enough before falling back.

### 6. (Conditional, gap #7) Freeze the bids-inbox triage — only if PR #8 has merged

- **Jayadratha**, from `services/api`, only if PR #8 (`feat(api): bids inbox I-2 ...`) has merged into `build` by now:
  ```bash
  cd services/api && GOOGLE_GENAI_USE_VERTEXAI=true GOOGLE_CLOUD_PROJECT=ordinal-mep GOOGLE_CLOUD_QUOTA_PROJECT=ordinal-mep \
    GOOGLE_CLOUD_LOCATION=global uv run python -m kirchhoff.inbox.precompute
  ```
- **Expected:** one line per seeded email (e.g. `em-hall-b: pursue (7/7 quotes verified)`), then `wrote …/scenarios/demo_world/captures/inbox-triage.json`.
- **Stop condition:** a verdict differs from `test_inbox_precompute.py`'s `VERDICTS` — usually a quote wasn't copied verbatim (shown "Not verified" → verdict becomes Clarify). Re-run once; never hand-edit the capture.
- **If PR #8 has not merged, skip this step entirely** — `make demo-world` below tolerates the missing `inbox-triage.json`.

### 7. Rebuild the demo world from the captures

- **Jayadratha**, from the repo root:
  ```bash
  make demo-world
  cd services/api && uv run python ../../scenarios/demo_world/build.py --check && uv run pytest tests/enterprise -q && cd ../.. && python3 - <<'EOF'
  import json
  b = json.load(open("apps/web/public/demo/projects/hall-a.json"))
  print("events", len(b["events"]), "revisions", [r["id"] for r in b["revisions"]], "what_ifs", len(b["what_ifs"]),
        "approval", b["approvals"][0]["approver_name"], b["approvals"][0]["role"], "prs", [p["id"] for p in b["prs"]],
        "options", bool(b["runs"][0].get("options")))
  EOF
  ```
  If step 6 ran, also run `cd services/api && uv run python ../../scenarios/demo_world/build_inbox.py --check`.
- **Expected:** `captured ['hall-a', 'pune-edge-1']` (or just `['hall-a']` if Pune Edge fell back), `demo world up to date`, all `tests/enterprise` pass (the committed-files test validates every bundle strictly against `ProjectBundle`), and `events <n> revisions ['r1', 'r2'] what_ifs 5 approval Priya Raman Lead Electrical Engineer (Reviewer) prs ['PR-2026-0142', …] options True`.
- **Stop condition:** `options False` → stop, this is readiness gap #3 showing up for real; do not proceed to deploy a bundle the OptionCards component can't render from. `--check` failing or any enterprise test failing → stop and diagnose before deploying.

### 8. Reseed, redeploy, re-test

- **Jayadratha:**
  ```bash
  make seed-enterprise && make deploy && make e2e-static
  ```
  (`make deploy` = `deploy-api` + `deploy-web` + `smoke`.)
- **Expected:** the seed reports Hall A's and Pune Edge's PRs; `smoke OK`; every static Playwright test passes, including "a recorded run replays from the static bundle", "a precomputed what-if chip works offline" and "the static Hall A bundle carries a recorded run and the five chips".
- **Stop condition:** any smoke or e2e-static failure → stop, do not proceed to commit/announce a broken deploy. Investigate with the controller before retrying `make deploy`.

### 9. Commit

- **Controller** (only the controller merges/commits to `build`):
  ```bash
  git add Makefile scenarios/demo_world/captures scenarios/demo_world/out apps/web/public/demo/world.json \
    apps/web/public/demo/integrations.json apps/web/public/demo/projects apps/web/public/demo/files
  git commit -m "feat(demo-world): golden capture — static Hall A (2N) and Pune Edge (DR) from recorded live runs

  Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
  ```
  If step 6 ran, also stage `scenarios/demo_world/captures/inbox-triage.json apps/web/public/demo/inbox.json scenarios/demo_world/out/inbox_seed.json` in a separate commit per the bids-inbox plan's own Step 15 commit message.
- **Expected:** a clean commit; `git status` shows nothing else from WS1–WS3's concurrent work staged (stage only the files listed, never `git add -A`/`git add .`, per the plan's Global Constraints).
- **Then:** open/update whatever PR tracks P4 Task 14 against `build` (or note in `docs/status/BOARD.md` that Task 14 is complete) — the plan calls for reporting the Hall A run id, the r1 findings, the event count and the PR ids to the controller, since the video and deck read values from this run (spec §3).

### 10. Post-capture verification list

Run against the now-deployed `https://kirchhoff.web.app`, by the **controller** (read-only HTTP checks) with **Jayadratha** available to re-pull anything that needs a cloud read:

- [ ] **Numbers.** Re-run the 200 kW what-if against the deployed, signed Hall A r2 bundle (via the UI or `GET` the relevant endpoint) and compare to "60 findings, 18 impact chains" in `docs/submission/deck-content.md:340,351,361,383,513`, `docs/submission/README-draft.md:43`, `docs/submission/video-script.md:25,65`, `docs/submission/deck/shots/README.md:27`. Update every file if the count moved (it already moved once, 62→60, per the note at `deck-content.md:513`).
- [ ] **bboxes.** `curl -fsS https://kirchhoff.web.app/demo/projects/hall-a.json | python3 -c '...'` — no finding's `tender_refs[].bbox` is null where `quote` and `page` are both set (closes gap #4's verification).
- [ ] **Options.** `b["runs"][0]["options"]` on the deployed bundle is non-empty (closes gap #3's verification; P3-R6).
- [ ] **Brief.** `b["brief"]` is present and non-null on the deployed bundle (the thing gap #1's missing check was supposed to guard).
- [ ] **No leaks.** `hall-b`, `Hall B`, `Demo Reviewer`, the raw live `rid`, and the raw `uid` do not appear anywhere in `curl -fsS https://kirchhoff.web.app/demo/projects/hall-a.json` or `.../pune-edge-1.json`.
- [ ] **Tour / replay.** Manually click through tour step 4 (the recorded-run replay) on the deployed site and confirm lanes and events render.
- [ ] **`make e2e-static`** was green in Step 8 — re-run if any of the above required a redeploy.

---

## Rollback

Everything the capture changes is committed to `build` as ordinary files (`scenarios/demo_world/captures/**`,
`scenarios/demo_world/out/**`, `apps/web/public/demo/**`), so rollback is a `git revert` plus a redeploy, not a
cloud-side undo:

1. **Controller:** identify the commit from Step 9 (and the bids-inbox commit if Step 6 ran) and `git revert <sha>
   [<sha2>]` on `build` (new commit, never `--amend`/force-push). This restores the pre-capture `apps/web/public/demo/**`
   files, `scenarios/demo_world/captures/**` and `scenarios/demo_world/out/**` to their prior committed state.
2. **Jayadratha:** redeploy from the reverted sha:
   ```bash
   git checkout <reverted sha>
   make seed-enterprise && make deploy
   ```
   `make deploy` is gated on a current (now-reverted) demo world by `infra/deploy_web.sh`'s own check (`uv run python
   ../../scenarios/demo_world/build.py --check`), so a half-reverted tree fails loudly instead of deploying a mixed
   bundle.
3. **Jayadratha:** `make smoke` to confirm `https://kirchhoff.web.app` is back to the pre-capture bundle.
4. **Both:** if the live Hall B runs themselves need cleaning up (stray `workspaces/{uid}/runs/{rid}` from a failed
   attempt), leave them — `export_run`/`find_workspace_for_run` only read a specific `rid` you pass in, so leftover
   workspaces are inert for the next capture attempt, not a hazard. Do not delete Firestore documents by hand.
5. **Stop condition for the rollback itself:** if `make deploy` refuses because the reverted demo world doesn't
   pass `--check` (e.g. a partial revert), stop and revert the remaining commit(s) rather than forcing the deploy.
