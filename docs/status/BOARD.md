# Kirchhoff build board

Updated by Mehul's controller session on each push. Detailed per-task history, review findings and every ruling are in the exported ledgers next to this file (`2026-10-13-p*.md`). Internal deadline: **Sat 17 Oct 20:00 IST**.

## Progress (15 Oct)

| Workstream | Branch | Done | In flight |
|---|---|---|---|
| WS1 Engine (P1) | `ws1-engine` | 15 / 15 + hardening, merged | done |
| WS2 Agents + API (P2) | `ws2-agents` | 15 / 18 merged to build (full P1→P4 pipeline + co-pilot) | Task 16 voice; then 17 asset agent, 18 docs exports, final review |
| WS3 Web UI (P3) | `ws3-web` | 19 / 19, merged | final whole-branch review → one fix wave |
| WS4 Infra + enterprise + demo world (P4) | `ws4-infra` | 12 / 16, merged | Tasks 13–16 need the deploy + golden capture |
| Bids inbox (§20) | `jd/inbox-*` | I-1 (#4) and I-3 (#5) merged | I-2 (#2) |
| Submission | `docs/submission/` | drafts reviewed | team bios/photos, video, measured run metrics |

`build` has every workstream merged. Its suites pass: 515 pytest, 164 vitest and `tsc -b`. A live P1→P4 run on Vertex passed in 177 s (about $0.06 of Gemini per design).

**Live:** https://kirchhoff.web.app still shows the P0 shell until Jayadratha's first deploy of `bd9311e` (issue #6).

## UI/UX track (P3)

| # | Task | When |
|---|---|---|
| UX-0 | Final fix wave: tour step 3, 3D hall readability, lane text, fix costs, App Check hang, contrast, bundle size | running |
| UX-1 | Design review of the fixed UI at desktop and phone size: ranked defects plus ranked improvements | after UX-0 |
| UX-2 | One improvement round on the top UX-1 items | Thu 15 |
| UX-3 | Human pass: #7 exploratory QA on the deployed site, plus Mehul's click-through | Thu 15 evening |

**UI freeze: Fri 16 Oct 12:00 IST** (the video records this UI).

## Jayadratha's work (GitHub issues)

| Issue | Task | Target (IST) |
|---|---|---|
| #6 | Cloud ops: seed, CORS, deploy `bd9311e` (GCP access granted 15 Oct) | now |
| #2 → PR #8 | Bids inbox I-2: changes requested (unit-aware verification, sanitize source/unit, precompute backend) | Fri 16 Oct 12:00 cut line (the date governs) |
| #3 → PR #9 | Live Triage button: icon fix, then rebase after the ws3-web fix wave lands | after the fix wave |
| #7 | E2E suite (PR #12 merged) + exploratory QA; QA issues #10, #11 | ongoing |
| #13 | P2 Task 17: asset agent `/api/asset/{pack}` | Fri 16 Oct 10:00 |
| #14 | Fill citation bboxes in the engine-built demo bundles | Thu 15 Oct 20:00 |
| #15 | P4 Task 15: App Check (staged; full enforcement only on Mehul's "go") | code Fri 16 Oct 12:00 |
| #16 | Secrets and PII audit of the full history before going public | Fri 16 Oct 18:00 |
| #17 | Deck screenshots via Playwright after the UI freeze | Fri 16 Oct afternoon |
| (none) | Team assets: photos, bios, TEAM SLOT clips | Fri 16 Oct |

## Not claimable (controller-owned, sequential)

- All remaining tasks in P2, P3 and P4.
- Contracts.
- Deciding when to deploy (Jayadratha runs the deploy, issue #6).
- The golden-run capture.
- App Check enforcement.
