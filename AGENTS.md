# Kirchhoff — guide for contributors and coding agents

Kirchhoff by Ordinal: Gemini agents design power and liquid cooling for an AI data-centre hall, a deterministic checker verifies every number against a clause-cited rule pack, and an engineer signs. Built for the Google Cloud × Hack2skill AI Builder Cup 2026. **Submission is due Sat 17 Oct 2026, 20:00 IST.**

Team Ordinal: Mehul Arora (lead) and Jayadratha.

## Read these first

| What | Where |
|---|---|
| Product spec (binding authority) | `docs/superpowers/specs/2026-10-13-kirchhoff-design.md` |
| Cross-workstream interfaces, ownership, HTTP API, events, rulings | `docs/superpowers/plans/2026-10-13-interfaces.md` |
| Implementation plans (one per workstream) | `docs/superpowers/plans/2026-10-13-p1-engine.md`, `…-p2-agents-api.md`, `…-p3-web.md`, `…-p4-enterprise-demo-infra.md` |
| Live progress, rulings and claimable work | `docs/status/` (exported from the build ledgers; `BOARD.md` first) |
| Submission drafts (deck, GCP brief, video script, README) | `docs/submission/` |

## Branches and who works where

- `build`: the integration branch and the GitHub default. Only Mehul's controller session merges into it.
- `ws1-engine`, `ws2-agents`, `ws3-web`, `ws4-infra`: workstream branches driven by Mehul's controller session through task-by-task subagents. **Do not commit to them.** They are pushed for visibility.
- `main`: frozen pre-build state. It is fast-forwarded at release.
- **Jayadratha and his agents:** branch from `build` as `jd/<topic>`, and open a pull request into `build`. Keep each PR to one task from `docs/status/BOARD.md` or one GitHub issue. Rebase on `build` before asking for review.

## Rules (everyone, every commit)

- **Fresh code only.** Everything in this repo is written during the hackathon. Do not paste code from other repos; open-source libraries are fine.
- **TDD.** Write the failing test first. `make test` (pytest plus vitest) must be green before you open a PR. `make check-types` must exit 0 if you touched contracts.
- **Contracts are frozen.** `services/api/kirchhoff/contracts/**` and `apps/web/src/contracts/generated.ts` change only with Mehul's approval, because every workstream depends on them.
- **Ownership.** Each path belongs to one workstream (see `interfaces.md`). If your task needs a change in another workstream's files, say so in the PR description instead of editing them quietly.
- **Trust rules (spec §6.3).**
  - Every number shown to a user comes from the engine.
  - LLM text may contain digits only through `{value}`/`{limit}` placeholders or allowlisted ids (`kirchhoff/agents/trust.py`).
  - Requirement quotes are verified with pdfplumber.
- **No secrets or personal data in commits.** No emails, keys or service-account files. Alert recipients and similar values are passed at run time. The Firebase web config in `apps/web/.env.*` is public by design.
- **Labels.** Engineering values are "IEC-based, illustrative values, not for construction". Demo-world data is "all companies, people and data are fictional".
- **UI.**
  - Status is always shown as icon plus text, never colour alone.
  - Every control is keyboard-reachable.
  - Motion is used only for progress, and `prefers-reduced-motion` is respected.
- **Do not deploy** unless an issue assigns it to you (issue #6 assigns the runbook to Jayadratha). Mehul's session owns `infra/deploy_*.sh`, Firebase Hosting and Cloud Run. The live demo at https://kirchhoff.web.app must stay up through judging (19 Oct – 6 Nov).

## Local setup

- **Python 3.12 with `uv`:** run `cd services/api && uv sync && uv run pytest -q`.
- **Node 20+:** run `cd apps/web && npm ci && npx vitest run && npx tsc -b`.
- **Everything:** `make test`. Dev servers: `make dev-api` and `make dev-web`.
- **No cloud access is needed for tests.** Agent calls run against replay fixtures (`kirchhoff/runs/fakes.py`, `FAKE_REPLIES`), and the engine is pure Python. Live Vertex AI calls are opt-in with `KIRCHHOFF_LIVE=1` and need GCP access; ask Mehul.

## Repo map

- `services/api/kirchhoff/engine/`: deterministic engine. It covers layout, power, short circuit, cooling, the rule pack R01–R15 plus R04b, fixes, what-if, and the grid and solar packs. The public facade is `engine/api.py`.
- `services/api/kirchhoff/agents/`: the agent runner layer (ADK and google-genai), agent specs, and the trust sanitizer.
- `services/api/kirchhoff/runs/`: leases, step machinery, phase orchestration, fakes.
- `services/api/kirchhoff/store/`: the Store protocol (memory and Firestore) and the EventWriter.
- `services/api/kirchhoff/enterprise/`: the ERP/CRM sandbox service, the client, and the demo-world generators.
- `apps/web/`: React 19 + Vite UI. It has the workspace, SLD (React Flow and ELK), 3D hall (react-three-fiber), matrix, finding drawer and onboarding.
- `scenarios/`: Hall A, the grid, solar and the demo world, all authored and all fictional.
- `infra/`: deploy, IAM, monitoring and budget scripts, plus `firebase.json`.
