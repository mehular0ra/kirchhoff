# SDD ledger — plan: docs/superpowers/plans/2026-10-13-p2-agents-api.md

Spec v4.1. Worktree .worktrees/ws2-agents, branch ws2-agents (from build @ 06f5494: P0 + fix wave + engine core P1 T1–11). Baseline: 114 passed, 1 warning.

## Pre-flight scan
| Rows | Finding |
|---|---|
| P2 code validation | blocks were parsed (syntax) by the writer but NEVER executed; reconciler edited 19 places → expect fix rounds; implementers on sonnet with "smallest faithful fix + report deviations" |
| P2 ↔ engine facade | real engine now on build (T1–11); what_if/grid/solar land later (P1 T13–15) — P2 Tasks 15/17 depend on them |
| P2 ↔ P0 fix wave | uses Store.transact/delete_tree/list_docs(order_by), EventWriter.emit(step=), fence(); Task 6 adds EventWriter hardening (R10) |
| P2 ↔ WS4 | enterprise client make_enterprise_client() (P4 Task 2) needed by P2 Task 14; P2 Task 7 provides fakes until then |
| P2 ↔ tender.yaml | Task 1 consumes WS1's tender.yaml (on build) |
Ruling P2-R1: execute P2 against the real engine already on build; where a P2 task references a facade function not yet landed (what_if, evaluate_grid/solar), implement against the fake port and mark an integration TODO in the ledger, not in code — cost if wrong: late integration fix Thu.

## Progress
Task 1: dispatched (BASE 06f5494, implementer sonnet)
Task 1: implemented 05092a3 (review dispatched)
Task 1: complete (commits 06f5494..05092a3, review clean; live PDF check 17/17 clauses on declared pages)
Task 2: dispatched (BASE 05092a3, implementer sonnet)
Task 2: implemented 19a3845 (review dispatched)
Task 2: fix round 1 dispatched (Important: DXF non-deterministic header timestamps/GUIDs; FIX_BASE 19a3845)
Task 2: fix round 1/5 (1 addressed + 1 extra root cause fixed — DXF metadata + hash-seed CLASSES order; commits 19a3845..ba9ea4b)
Task 2: complete (commits 05092a3..ba9ea4b, review clean after 1 fix round)
Task 2: minor (deferred): ezdxf write_fixed_meta_data_for_testing is process-global (set inside render fn; API never renders DXF)
Task 3 brief ready (waiting for implementer slot)
Task 3: dispatched (BASE ba9ea4b, implementer sonnet)
Task 3: implemented 7a4dc0f (review dispatched)
Task 3: complete (commits ba9ea4b..7a4dc0f, review clean)
Task 3: minor (deferred): score_intake doesn't check citation.doc_id (extraction agent must set tender-hall-a); NUMBER_WORDS only to twelve; greedy matcher order-dependence inert (no duplicate-valued gt rows) — add a uniqueness guard test if gt grows
Task 4 brief ready (waiting for implementer slot)
Task 4: dispatched (BASE 7a4dc0f, implementer sonnet)
Task 4: implemented 07b264a (review dispatched)
Task 4: fix round 1 dispatched (Important: superscript digits ² ³ ¹ (Unicode No) bypass \d in is_clean/sanitize; FIX_BASE 07b264a)
Task 4: minor (deferred): fill_finding unit-present check is textual heuristic (no failing case found)
Task 5 brief ready (waiting for Task 4 fix round)
Task 4: fix round 1/5 implemented 34c5228 (scoped re-review dispatched)
Task 4: fix round 1/5 (1 addressed, 0 open — Unicode No-category digits; commits 07b264a..34c5228)
Task 4: complete (commits 7a4dc0f..34c5228, review clean after 1 fix round)
Task 5: dispatched (BASE 34c5228, implementer sonnet)
Task 5: implemented 99cd3a5 (review dispatched; live suite 4/4 on Vertex)
Task 5: complete (commits 34c5228..99cd3a5, review approved; ADK node= deviation verified against installed source)
Task 5: minor (deferred): RecordingRunner writes tool args/results unredacted (note for first live recording); GenaiRunner multi-tool automatic_function_calling_history unverified (voice/co-pilot task must test multi-call turns)
Task 6 brief ready (waiting for implementer slot)
Task 6: dispatched (BASE 99cd3a5, implementer sonnet; carries R10 residuals)
Task 6: implemented f851621 (review dispatched, opus — concurrency)
XWS from P1 final review (carry into dispatches):
 - Ruling P2-R2: WS2 ruling R20 does NOT apply — WS1 option models already include cooling_nodes; never append size_cooling output (duplicate CDUs flip R08 to pass). validate_model() will now raise on duplicates.
 - fix_candidates returns [] for every rule except R05 and R11; WS2 fix-loop must handle 'no candidates' (park at review gate) — R12/R15/Power-owned R01–R07/R13 have no engine candidates.
 - Pass FixCandidates to apply_fix by id from the engine's own fix_candidates output only; never build a candidate or patch from LLM output.
 - allowed_ids_for(model) misses asset-pack ids (L-132, SS-132, SS-33, STR-28, INV, FIELD): pass them via extra.
 - Call engine api.warm_up() at API startup (cold pandapower import ~1.2 s).
Task 6: review Needs fixes (opus) — Important: close()/flush() return while another thread's batch is in flight → stranded events in closed writer + seq reuse at Task 10 phase handoff (reproduced 20/20); reviewer-verified fix: _io RLock taken before _lock around flush body + set_step. Minors folded in: log exc_info + per-case wording; backoff growth/cap test; cap-unchanged-on-CapReached test; docs: set_step single-threaded/holds lock across commit, never emit inside transact fn, run_patch is shallow
Task 6: fix round 1 dispatched (resumed implementer; FIX_BASE f851621)
Task 6: fix round 1/5 implemented 54298d5 (scoped re-review dispatched to original opus reviewer)
Task 6: fix round 1/5 (1 addressed, 0 open — _io RLock; stress 0 lost/0 seq reuse; close() raises on its own flush failure; commits f851621..54298d5)
Task 6: complete (commits 99cd3a5..54298d5, review clean after 1 fix round)
Task 6: minor (deferred → P2 final fix wave): closed-branch ERROR log now a false alarm (make WARNING 'close() will flush requeued events'); silent 'not has_pending' except branch; test_flush_blocks_until_a_concurrent_timer_batch_is_also_durable doesn't fail pre-fix (make first batch slow, later fast); test pokes w._arm/_timer_flush; flush/fence docstrings overclaim during set_step
Task 7: queued (brief ready; waiting for implementer slot)
Merged build (engine complete) into ws2-agents at 8e71a38 (217 passed)
Task 7: dispatched (BASE 8e71a38, implementer sonnet)
Task 7: implemented e78693f (review dispatched)
 - HARD REQUIREMENT (P1-R7): the fix loop applies a candidate only by looking up its id in a fresh engine fix_candidates() result for that finding; never construct/patch a FixCandidate from LLM output
User approved (14 Oct): spec §20 Bids inbox (Should). A plan addendum (docs/superpowers/plans/2026-10-14-bids-inbox.md) will add one task each to WS4 (seed emails + fit rules), WS2 (triage agent + endpoint), WS3 (inbox page); start only after Must items; checkpoint Thu 16 Oct 12:00 IST; fallback = static inbox with precomputed triage
Task 7: complete (commits 8e71a38..e78693f, review approved; golden behaviour verified side-by-side vs real engine)
Ruling P2-R3: fake/real parity gaps (fake route() not idempotent after apply_fix; fake fix_candidates trusts finding id; fake check() skips validate_model; AST drift guard misses multi-line imports) — fold into the dispatch of the first task that exercises the fix loop / re-route: align FakeEngine with real (route only fills empty cooling_nodes/pipes; fix_candidates returns [] if the finding isn't failing; check() calls validate_model) and harden the drift guard — cost if wrong: a WS2 test passes on the fake but fails on the real engine
Task 7: minor (deferred): FixCandidate.patch shapes differ fake vs real (opaque; never inspect .patch keys); FakeEnterprise.create_pr uses time.time()
Task 8: dispatched (BASE e78693f, implementer sonnet)
Task 8: implemented 6d0c4ff (review dispatched, opus — transactions/leases)
Task 8: review Needs fixes (opus) — I-1 stale worker's flushes overwrite current attempt's events (shared seq range; run_step flushes without lease check) — 32/300 iterations lost events; I-2 blob outputs not attempt-scoped + sha256 never verified; I-3 mutation testing: 5 core safety properties untested; minors M-1 event cap not whole-event, M-2 unsafe payload degrades agent silently, M-3 post-fn failures leave step running, M-4 >400-docs path unleased, M-5 agent_json drops tokens on failure, M-6 early lease_lost path doesn't fence
Ruling P2-R4: fix I-1 (new attempt's writer starts at next_seq + 10_000 when the latest event's attempt != current attempt; check ctx.lease_lost → fence + LeaseLost before the pre-commit flush), I-2 (sha-scoped blob path + ValueError on mismatch), I-3 (tests killing the 5 surviving mutants), M-1, M-3, M-4 (reject >400 docs per step with ValueError), M-6 in one round; defer M-2, M-5, M-7 and the Task-9 heartbeat self-fence note (carried to Task 10 dispatch) — cost if wrong: one more round
Task 8: fix round 1 dispatched (resumed implementer; FIX_BASE 6d0c4ff)
Task 8: fix round 1/5 implemented 6d0c4ff..541df85 (scoped re-review dispatched to original opus reviewer)
Task 8: fix round 1/5 (6 addressed, 1 residual Important — SEQ_GAP fixed offset from last flushed event collides when a stale attempt ≥2 flushed nothing (gate resumes make every P2/P3 attempt ≥2); commits 6d0c4ff..541df85)
Ruling P2-R5: round 2 = attempt-proportional gap (base + SEQ_GAP*max(0, cur-last); no events → 1 + SEQ_GAP*(cur-1)), pass attempt explicitly to next_seq; tests killing N1 (early-guard fence), N2 (pre-flush lease check), N6 (commit txn raises), N10 (no-events branch); failed-path txn leaves an already-done step alone (ambiguous commit error); TITLE_MAX → 1000; truncated payload re-checked against budget — cost if wrong: round 3
Task 8: fix round 2 dispatched (resumed implementer; FIX_BASE 541df85)
Task 8: fix round 2/5 implemented 541df85..6944260 (scoped re-review dispatched; check next_seq attempt param optional vs required)
Task 8: fix round 2/5 (all addressed, 0 open — proportional SEQ_GAP; 26/26 mutants killed; probes 0 losses; commits 541df85..6944260)
Task 8: complete (commits e78693f..6944260, review clean after 2 fix rounds)
Task 10 carry (P2-R6): make next_seq's attempt REQUIRED; Task 10 call sites (plan lines ~4450 _worker writer, ~4511 _record_failure) pass attempt; attempt < last_attempt → raise LeaseLost (stale caller)
Task 9: dispatched (BASE 6944260, implementer sonnet)
Task 9: implemented 191c4d4 (review dispatched)
Task 9: review Needs fixes — CRITICAL: unverified LLM quote reaches UI verbatim when digit-free (sanitize is not an always-template gate; brief code); Important: unit never checked against quote; minors: App-vs-App tie-break unpinned, U+2010/U+2212 dash folding
Ruling P2-R7: unverified → always UNVERIFIED_TEMPLATE + value None; unit must appear in normalised quote else unverified (real tender fixture must still verify); pin App-vs-App; fold extra dashes — cost if wrong: false rejects on unit spellings (tested against real PDF)
Task 9: fix round 1 dispatched (resumed implementer; FIX_BASE 191c4d4)
Task 9: fix round 1/5 implemented 53ecf17 (scoped re-review dispatched)
Task 9: fix round 1/5 (3 addressed, 1 new Important — unit_in_quote is unbounded substring: 'm' matches inside 'mm' (real §6.3.4 clause false-accepts unit m for 300 mm); commits 191c4d4..53ecf17)
Ruling P2-R8: token-bounded unit match (no ASCII letter on either side of each alias form), tests incl. m-vs-mm on the real tender clause, min-in-aluminum, week-in-midweek, kW-vs-kWh; real tender must still verify 7/8 — cost if wrong: round 3
Task 9: fix round 2 dispatched (resumed implementer; FIX_BASE 53ecf17)
Task 9: fix round 2/5 (1 addressed, 0 open — token-bounded unit match; commits 53ecf17..0a9e8bd) — scoped re-review by controller (diff read; 10 unit cases incl. m-vs-mm, min-in-aluminum, kW-vs-kWh all correct; intake 38/38; real tender still 7/8 per implementer)
Task 9: complete (commits 6944260..0a9e8bd, review clean after 2 fix rounds)
Task 10: dispatched (BASE 0a9e8bd, implementer sonnet; carries P2-R6 required attempt + LeaseLost on stale, heartbeat self-fence at lost/45 s, _record_failure holds_lease guard)
Task 10: implemented ff77795 (review dispatched, opus)
Ruling P2-R9: accept the Ask-mode test change (seq strictly increasing, not contiguous) — SEQ_GAP per new attempt applies on every gate resume by design (P2-R5); UI orders by seq field and WS4 capture renumbers — cost if wrong: none
Task 10: review Needs fixes (opus) — Important: 9/19 mutants survive (LeaseBusy race, gate_wait_s/active_s exact values, _patch_if_holder, stop.set, resume_run at_gate, expiry boundary); minors: expiry check-then-act (E1/E2), self-fence during flush drops committed step's events (S9), unguarded failure-path release, lazy expiry; all stress scenarios otherwise passed (1 winner/race, cap 3, clean takeovers, no thread leaks)
Ruling P2-R10: fix round = the mutant-killing tests + S9 lease re-check after flush + transactional gate claim (acquire_lease expect predicate) + resume_run expiry + guarded release + Task 8 test timer hygiene; defer Minors 5–7 — cost if wrong: one more round
Task 10: fix round 1 dispatched (resumed implementer; FIX_BASE ff77795)
Task 10: fix round 1/5 implemented ff77795..f1bba82 (mutants 20/20 killed; scoped re-review dispatched to original opus reviewer)
Task 10: fix round 1/5 (6 addressed, 0 open — S9 post-flush re-check, transactional gate claim, resume_run expiry, guarded release, timer hygiene, mutants killed; commits ff77795..f1bba82)
Task 10: complete (commits 0a9e8bd..f1bba82, review clean after 1 fix round)
Task 10: minor (deferred → P2 final fix wave): _expire should re-check gate identity + expiry inside fn (E3, needs a phase-long stall at 24 h); expiry event emitted without a step doc (invisible, breaks R4) — drop it or write the step doc; tests for expect's gate-identity/expiry clauses + _expire status; cosmetic: double-submit gives wrong_state, ensure_gate _retried kwarg, unused gate param
Task 11: dispatched (BASE f1bba82, implementer sonnet; P2-R2 cooling-node merge guard; real-engine P1+P2 integration test; one live P1 smoke for intake metrics)
Task 11: implemented 6f2725a (DONE_WITH_CONCERNS: ADK {value} injection bug fixed in adk_runner; ADK workflow-mode intermittent >90 s latency; live P1 attempt 3 still running as pid 36957) — review dispatched
Task 11: review Approved-but-needs (phases byte-identical to brief except verify arity drift fix; adk_runner fix verified against ADK source; real-engine test meaningful) — open: no offline test for adk_runner instruction fix; live P1 smoke not confirmed passing
Ruling P2-R11: fix round 1 = offline instruction-provider test + live ADK mode measurement (agent mode for P1 + one live P2 tool-calling smoke; default to agent mode if it passes, else raise INTAKE/ORCHESTRATOR timeout_s to 150 s) — live reliability for judging outweighs the Workflow-graph showcase; ADK still used either way — cost if wrong: architecture slide wording ('ADK Workflow') must say ADK agents
Task 11: fix round 1 dispatched (resumed implementer; FIX_BASE 6f2725a)
Task 11: fix round 1/5 implemented 3a7f31c — offline instruction-provider test (RED→GREEN, both modes) + test_runs_live_p2.py (live, unrun); live: test_agents_live 4/4 pass in agent mode 28 s; P1 live agent-mode inconclusive (killed); default mode + timeouts unchanged
Controller: measuring live intake extraction directly (genai / ADK agent / ADK workflow, timeout 300 s) to decide P2-R11
Controller live measurement (14 Oct, real tender PDF, extract_tender, 300 s ceiling): genai/medium 144.5 s 22 req 2 contra; ADK agent/medium 94.4 s 22/2; ADK workflow/medium 130.1 s 22/2; ADK agent/low 27.6 s 20/0 and 54.7 s 22/0 (low thinking misses the §4.2 vs App. B contradiction)
Ruling P2-R11 (resolved): keep INTAKE thinking medium; INTAKE timeout 240 s, ORCHESTRATOR 120 s, POWER/COOLING 90 s; AdkRunner default mode 'agent' (workflow selectable) — cost if wrong: live intake step ~1.5–2.5 min (video is time-compressed; lanes stream progress)
Task 11: fix round 2 dispatched (config only; controller runs live smokes after)
Task 11: fix round 2/5 implemented 8035ab4 (INTAKE 240 s, ORCHESTRATOR 120 s, POWER/COOLING 90 s; AdkRunner default 'agent'; 388 passed) — controller running live P1 + P2 smokes
Task 12: dispatched (BASE 8035ab4, implementer sonnet; pipelined with Task 11's controller live smoke — Ruling P2-R12: T12 touches api/** only, T11 fixes (if any) touch runs/phase*/agents/specs — cost if wrong: a merge of two small commits); WS4 proxy mount test must now run; engine warm_up at startup in background
