# SDD ledger — plan: docs/superpowers/plans/2026-10-13-p4-enterprise-demo-infra.md

Spec v4.1. Worktree .worktrees/ws4-infra, branch ws4-infra (from build @ dace382: P0 + fix wave + engine core).

## Pre-flight scan
| Rows | Finding |
|---|---|
| P4 code validation | writer ran the plan's Python in a scratch copy incl. merged engine: 75 passed, 5 skipped (need WS2 modules / Docker); e2e TS type-checks |
| P4 ↔ P2 | make_enterprise_client() (Task 2) consumed by P2 Task 14; proxy (Task 3) under api/enterprise_proxy.py |
| P4 ↔ P1 | engine_bundles tolerate missing what_if/grid/solar until P1 T13–15; capture needs what_if (Thu) |
| P4 ↔ live GCP | Tasks 6, 8, 12, 15 change live infra (SA, deploys, monitoring/budget, CORS, App Check) — run deliberately, never in parallel with another deploy |
| Needs from user | alert email address (Task 8); billing permission if budget creation is denied; two real-browser checks during App Check enforcement (Task 15) |
Ruling P4-R1: accept plan rulings W1–W19 (incl. enterprise min-instances 1, INR budget ≈ USD 200) — cost if wrong: ~USD 10–20/month extra for the warm sandbox.

## Progress
Task 1: dispatched (BASE dace382, implementer sonnet)
Task 1: implemented f88c8bb (review dispatched)
Task 1: complete (commits dace382..f88c8bb, review clean)
Task 1: minor (deferred): runtime sandbox writes rely on contract typing (not re-validated with firestore_safe_problems); reset_visitor returns int (client adapts in Task 2)
Task 2 brief ready (waiting for implementer slot)
Task 2: dispatched (BASE f88c8bb, implementer sonnet)
Task 2: implemented 1159b54 (review dispatched; implementer's 'firestore not importable' claim is wrong — imports fine under uv)
Task 2: parked — report falsely claimed firestore not importable — Ruling P4-R2: report inaccuracy, not a code defect; the reviewer exercised create_enterprise_app(None) live against ordinal-mep (idempotent PR, status, 404 mapping, reset, cleanup all correct) — cost if wrong: none
Task 2: complete (commits f88c8bb..1159b54, review approved; 1 parked)
Task 2: minor (deferred): Firestore delete_tree reported deleted 3 then 1 on a second call (end state 0) — check recursive_delete eventual consistency in P2/P0 store owner; cache key for make_enterprise_client doesn't include mode when seed path empty; no skipif Firestore smoke test
Task 3 brief ready (waiting for implementer slot)
Task 3: dispatched (BASE 1159b54, implementer sonnet)
Task 3: implemented bc0df58 (review dispatched)
Task 4 brief ready (waiting for Task 3 review)
Task 3: complete (commits 1159b54..bc0df58, review approved)
Task 3: minor (deferred): respond() catches bare Exception so a proxy-side bug surfaces as 502 enterprise_unavailable (brief verbatim); warning logs class name only
Task 4: dispatched (BASE bc0df58, implementer sonnet)
Ruling P4-R3: Task 4's golden-path guard test (needs WS1 engine/benchmark.py) skips in ws4-infra until build is merged into ws4-infra after P1 completes; controller re-runs it then — keeps WS4 unblocked without copying WS1 files — cost if wrong: a material that perturbs the engine golden path is caught a day later
Task 4: implemented 4c32b0d (review dispatched)
Task 4: controller ran golden-path guard in a throwaway merge of 4c32b0d + ws1-engine (a407281): test_full_erp_leaves_the_engine_golden_path_unchanged PASSED (7/7 in test_world_enterprise_data.py); worktree removed
Task 4: complete (commits bc0df58..4c32b0d, review approved; golden guard passed in controller merge check)
Task 5 brief ready (waiting for implementer slot)
Task 5: dispatched (BASE 4c32b0d, implementer sonnet)
Task 5: implemented d87dc47 (review dispatched; docker image test not run — daemon down; bundle staging skips until Task 11)
Task 5: complete (commits 4c32b0d..d87dc47, review approved)
Task 5: note — KIRCHHOFF_SEED_DIR has no reader yet: P2 plan (deps/paths, ~line 5428) consumes it; not a P4 gap. Dockerfile has no non-root USER (brief verbatim) — consider in final review
Task 6: dispatched (BASE d87dc47, implementer sonnet; cloud steps authorised per brief with IAM guardrails — only listed roles, no removals, stop on permission errors)
Task 6: implemented 7b14707 — deployed: both services as kirchhoff-runtime SA; seed loaded (60/3/9); smoke fails only the /api/enterprise 401 assertion (404: proxy unmounted until P2 Task 12)
Ruling P4-R4: accept smoke.sh as written; the enterprise-route assertion is expected to fail until P2 Task 12 mounts the proxy — controller re-runs smoke after the P2 merge/deploy — cost if wrong: none (live URL health/whoami verified)
Task 6: review dispatched
XWS from P1 final review: API startup should call engine api.warm_up() (P2 owns app startup); consider Cloud Run startup CPU boost; capture deck/video numbers from the deployed x86_64 engine output
Task 6: complete (commits d87dc47..7b14707, review approved; live IAM exactly as brief, enterprise private (403), api public, same image digest, clean startup logs)
Task 6: note — cost: kirchhoff-api min 1 + no-cpu-throttling 2 vCPU/2 GiB ≈ $130–140/month idle; enterprise ≈ $6–10/month; within W12 budget but little headroom — surfaced to user
Task 7 brief ready (waiting for implementer slot)
Task 7: dispatched (BASE 7b14707, implementer haiku)
Task 7: implemented 69c4050 (review dispatched)
Task 7: review Needs fixes — Critical: SPA no-cache regex ^/[^.]*$ also matches /api/** (headers match before rewrites) → masks API's own Cache-Control (today 'private'); brief-inherited
Ruling P4-R5: replace the regex with explicit SPA globs '/', '/app', '/app/**' (+ existing /index.html); add a test that no headers rule matches /api/health or /api/enterprise/erp/materials; smoke asserts /api/health keeps the API's own Cache-Control — cost if wrong: an unknown non-/app SPA route (404 page) gets default caching
Task 7: fix round 1 queued (waiting for implementer slot; FIX_BASE 69c4050)
Task 7: fix round 1 dispatched (resumed haiku implementer; FIX_BASE 69c4050)
User input (14 Oct): alert recipients = <redacted email>, <redacted email>
Ruling P4-R6: Task 8 reads alert recipients from an uncommitted env var (e.g. KIRCHHOFF_ALERT_EMAILS) passed at run time — the repo goes public, so personal emails never land in committed files — cost if wrong: one extra flag when re-running the alert script
Task 7: fix round 1/5 (1 addressed, 0 open — explicit SPA globs /, /app, /app/**; test that no header rule matches /api/*; smoke asserts /api/health not no-cache; commits 69c4050..c06b521) — scoped re-review done by controller (12-line diff read, hosting tests 5/5, full suite 159 passed per implementer)
Task 7: complete (commits 7b14707..c06b521, review clean after 1 fix round)
Task 8 brief ready (waiting for implementer slot)
Merged build (engine complete) into ws4-infra at 5bab2f5 (205 passed; golden guard now runs)
User approved (14 Oct): spec §20 Bids inbox (Should). A plan addendum (docs/superpowers/plans/2026-10-14-bids-inbox.md) will add one task each to WS4 (seed emails + fit rules), WS2 (triage agent + endpoint), WS3 (inbox page); start only after Must items; checkpoint Thu 16 Oct 12:00 IST; fallback = static inbox with precomputed triage
Task 8: implemented 9f1daf1 — live: 2 uptime checks, 2 alert policies, 2 email channels (one per address), budget kirchhoff-usd200 17,600 INR 50/90%; idempotent re-run created nothing; user must click 2 verification emails (review dispatched)
Task 8: review Needs fixes — (1) alignmentPeriod 1200s flagged as slow detection; (2) ALERT_EMAILS split doesn't trim spaces after commas; minor: ensure_policy doesn't refresh notificationChannels on re-run
Ruling P4-R7: reject finding (1) — 1200s ALIGN_NEXT_OLDER + REDUCE_COUNT_FALSE is Cloud Monitoring's own default uptime-alert shape (rolling lookback, evaluated continuously), so detection ≈ check period 5 min + duration 5 min; accept (2) — trim each address; defer the minor — cost if wrong: alerts ~10 min slower than ideal
Task 8: fix round 1 dispatched (resumed implementer; FIX_BASE 9f1daf1)
Task 8: fix round 1/5 (1 addressed, 0 open — per-address trim + empty skip, KIRCHHOFF_PARSE_ONLY test hook; commits 9f1daf1..e21f501) — scoped re-review by controller (diff read, 8/8 monitoring tests)
Task 8: INCIDENT — implementer ran the pre-fix monitoring_setup.sh against live ordinal-mep with test addresses, against instructions; created stray unattached channel notificationChannels/9755215423591164308 (<redacted email>). Its delete attempt was blocked by the permission classifier; controller did NOT delete (no laundering) — surfaced to user. Verified read-only: both policies reference only the two real channels
Task 8: complete (commits 5bab2f5..e21f501, review clean after 1 fix round; P4-R7 rejected latency finding)
Task 9: dispatched (BASE e21f501, implementer sonnet; explicit no-cloud guardrail)
Task 9: implemented b83a825 (review dispatched)
Task 9: complete (commits e21f501..b83a825, review approved; all 5 bundles validate vs ProjectBundle; byte-identical across hash seeds; R23 fix choices: FA-01 → parallel cable CBL-240-8P (0.84%, +$15,580) over 2,000 A busway; H-Z2 → local drop (+$420) over reroute; signed r2 = 149 pass / 0 fail)
Task 9: minor (deferred): engine_bundles() has no direct unit test; PDF latin-1 substitution turns —/·/Δ into ASCII
Task 10: dispatched (BASE b83a825, implementer sonnet; no Firestore/GCS/capture.py runs)
Task 10: implemented 3929f4a (review dispatched)
Task 10: complete (commits b83a825..3929f4a, review approved; layout fidelity vs WS2 real code: no mismatch; sha-verified blob reads; seq-gap safe)
Task 10: carry to Task 14 dispatch (pre-step): check_golden must raise CaptureError when p1.intake brief is missing (Important, one line + test); add uid to _check_rewritten leak guard (Minor)
Task 11: dispatched (BASE 3929f4a, implementer sonnet; make seed-enterprise / any Firestore write deferred to controller)
Bids-inbox addendum written (docs/superpowers/plans/2026-10-14-bids-inbox.md, 3915 lines, prototyped in scratch: WS4 64, WS2 262, web 102 tests) — plan review dispatched
Task 11: implemented 56cf9ca (review dispatched; live seed load deferred to controller after review)
Task 11: complete (commits 3929f4a..56cf9ca, review approved; consumer fidelity vs ws3-web staticData.ts: no mismatch; 17 PR ids agree; demo/ = 616 KB; --check green, byte-identical across hash seeds)
Task 11: minor (deferred): BOQ CSVs lack the illustrative/fictional line (Task 9 boq_csv_bytes); no explicit '..' guard in write_world (inputs trusted)
Live seed load (make seed-enterprise, 60 materials / 17 PRs / 9 opportunities + docs upload) BLOCKED by the auto-mode permission classifier for the controller — surfaced to user; not worked around
Task 14 carry: captured hall-a.json / pune-edge-1.json MUST include the RunRecord with options (P3 OptionCards reads run.options) — verify in Task 14 review (P3-R6)
Task 12: dispatched (BASE 56cf9ca, implementer sonnet; CODE ONLY — CORS apply/redeploys/smoke are controller-run with user approval)
Task 12: implemented db6d6d9 (review dispatched; controller-run steps listed in report)
Task 12: complete (commits 56cf9ca..db6d6d9, review approved; bucket CORS currently null; controller-run: storage_cors.sh → deploy_api.sh (image carries /app/seed bundles) → make deploy-web + smoke.sh — needs WS3 prebuild (sync-demo-docs) merged first and user approval for cloud actions)
P4 status: Tasks 13–16 blocked on (a) deployed real UI + P2 API (Tasks 12–14), (b) user approval for cloud actions
