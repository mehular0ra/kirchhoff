/* The measured numbers on the s10-numbers card. Hand-kept, each with where it comes from.
 * services/api/tests/enterprise/test_video_numbers.py checks every value here against its evidence (the benchmark is re-run
 * for the count), so this file cannot drift from the deck or from the engine. The fourth number on the card (25 of 26 quotes
 * verified) is not here: it comes from the recorded run through lib/data.js (KDATA.intake). */
window.KMEASURED = {
  faults: { caught: 35, total: 35, false_positives: 0, source: 'services/api/kirchhoff/engine/benchmark.py, run by services/api/tests/engine/test_benchmark.py' },
  median: { seconds: 149, runs: 3, basis: 'from the start of a run to a checker-clean revision, time at the gates excluded', source: 'docs/submission/deck/fill.yaml (upload_to_clean_median)' },
  cost: { usd: '0.066', basis: 'one full run, the golden capture of 16 Oct 2026', source: 'docs/submission/deck/fill.yaml (usd_per_run)' },
};
