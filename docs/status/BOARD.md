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

| Issue / PR | Task | State | Target (IST) |
|---|---|---|---|
| #6 | Cloud ops | `da2ad9f` deployed; the runtime SA needs `serviceUsageConsumer` (PR #29 merged; grant pending) | now |
| #24 | Golden capture operator | dry run blocked in p3 by the 403 above; Resume once granted | Thu eve / Fri 08:00–12:00 |
| #30 | Voice co-pilot on the deployed site (Live + push-to-talk), real mic | new | Fri 11:00 |
| #31 | Lighthouse + cold-start numbers | new | Fri 11:00 |
| #7 | QA pass 2 on the redeployed UX-2 build | after the next redeploy | Fri before 12:00 |
| #13 → PR #19 | Asset agent: passing-only pick + 2 tests | changes requested | Fri 10:00 |
| #15 → PR #22 | App Check script: executable stubs + call-log asserts | changes requested | Fri |
| #17 | Deck screenshots (script merged in #23) | after the freeze + capture | Fri afternoon |
| #32 | Submission checklist + form dry run + deck PDF | new | Fri 14:00 |
| #25 | Video screen footage per storyboard | after the freeze | Fri afternoon |
| #26 | README, final gitleaks, judging-window runbook, release | open | Sat 17 Oct |
| (none) | Team assets: photos, bios, TEAM SLOT clips | open | Fri 16 Oct |

Done today: #8, #9, #12, #18, #21, #23, #27, #28 and #29 merged; the history audit (#16) is complete.

## Not claimable (controller-owned, sequential)

- All remaining tasks in P2, P3 and P4.
- Contracts.
- Deciding when to deploy (Jayadratha runs the deploy, issue #6).
- The golden-run capture.
- App Check enforcement.
