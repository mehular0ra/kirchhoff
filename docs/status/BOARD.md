# Kirchhoff build board

Updated by Mehul's controller session on each push. Detailed per-task history, review findings and every ruling are in the exported ledgers next to this file (`2026-10-13-p*.md`). Internal deadline: **Sat 17 Oct 20:00 IST**.

## Progress (14 Oct)

| Workstream | Branch | Done | In flight |
|---|---|---|---|
| WS1 Engine (P1) | `ws1-engine` | 15 / 15, final review clean, merged | small hardening follow-up (forged-fix guards) |
| WS2 Agents + API (P2) | `ws2-agents` | 7 / 18 | Task 8: step machinery |
| WS3 Web UI (P3) | `ws3-web` | 7 / 19 | Task 8: 3D hall (fix round 3: tube animation) |
| WS4 Infra + enterprise + demo world (P4) | `ws4-infra` | 7 / 16 (8 in fix) | Task 8: monitoring, small fix queued |
| Submission | `docs/submission/` | drafts reviewed | team bios/photos, GitHub/video URLs, measured run metrics |

`build` now contains every workstream at its last clean task boundary. Its suites pass: 277 pytest, 73 vitest, `tsc -b` and `make check-types`.

**Live:** https://kirchhoff.web.app
- The API runs on Cloud Run as a dedicated least-privilege service account.
- The ERP/CRM sandbox is seeded.
- Uptime checks and the budget alert are on.
- The web UI there is still the P0 shell. The real UI deploys after the API wiring (P2 Task 12) and the demo bundles (P4 Task 11).

## Claimable work for Jayadratha (and his agents)

To claim a task, comment on its GitHub issue, branch `jd/<topic>` from `build`, and open a PR into `build`. The rules are in `AGENTS.md`.

1. **Bids inbox (spec §20, a Should item)**
   - The plan addendum `docs/superpowers/plans/2026-10-14-bids-inbox.md` is reviewed and ready.
   - Issues #1 (I-1), #2 (I-2) and #3 (I-3) are assigned to Jayadratha.
   - **I-1** can start now.
   - **I-2** Steps 1–9 can start now; its endpoints wait for P2 Task 12 (API wiring).
   - **I-3**'s static page can start once I-1's `inbox.json` exists.
   - Cut line: Thu 16 Oct 12:00 IST.
2. **Team assets for the deck and video**
   - Photos.
   - Two-sentence bios for Mehul and Jayadratha.
   - Any team clips for the three TEAM SLOTs in `docs/submission/video-script.md`.
3. **Exploratory QA on the deployed site.** This starts once the real UI is live, Thu 16 Oct. Follow the 7-step tour in spec §13.5 and file issues with screenshots.

## Not claimable (controller-owned, sequential)

- All remaining tasks in P2, P3 and P4.
- Contracts.
- Deploys.
- The golden-run capture.
- App Check enforcement.
