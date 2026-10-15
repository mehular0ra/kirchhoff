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
| #6 | Cloud ops: seed (done), CORS (done), deploy | **blocked**: needs actAs on the default Compute SA for Cloud Build | as soon as granted |
| #24 | Golden capture operator: dry run Thu evening, capture Fri | queued behind the deploy | Thu eve / Fri 08:00–12:00 |
| #2 → PR #8 | Bids inbox I-2 | fixes pushed, re-review running | Fri 16 Oct 12:00 cut line |
| #3 → PR #9 | Live Triage button | icon fix pushed, re-review running | after UX-2 lands |
| #13 → PR #19 | P2 Task 17: asset agent | review running | Fri 16 Oct 10:00 |
| #14 → PR #18 | Citation bboxes in demo bundles | review running | after the P2 fix wave (R13 regen) |
| #20 → PR #21 | E2E follow-ups; phone tour bug (UX-2 is fixing the cards) | review running | Fri |
| #15 → PR #22 | App Check `appcheck.sh` (code); enforcement on Mehul's "go" | to review | code done |
| #17 → PR #23 | Deck screenshot script (part 1) | to review | shots after the freeze |
| #25 | Video screen footage per storyboard | new | Fri afternoon |
| #26 | P4 Task 16: README, pre-public gitleaks, judging-window runbook, release | new | Sat 17 Oct |
| #16 | Secrets/PII audit | **done**: 3 decisions for Mehul | (none) |
| (none) | Team assets: photos, bios, TEAM SLOT clips | open | Fri 16 Oct |

## Not claimable (controller-owned, sequential)

- All remaining tasks in P2, P3 and P4.
- Contracts.
- Deciding when to deploy (Jayadratha runs the deploy, issue #6).
- The golden-run capture.
- App Check enforcement.
