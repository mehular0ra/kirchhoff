#!/usr/bin/env bash
# Copy each workstream's SDD ledger (git-ignored, in its worktree) into docs/status/ so the whole team
# can read progress and rulings on GitHub. Email addresses are redacted; the repo goes public.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/docs/status"
mkdir -p "$OUT"
for pair in "ws1-engine:2026-10-13-p1-engine" "ws2-agents:2026-10-13-p2-agents-api" \
            "ws3-web:2026-10-13-p3-web" "ws4-infra:2026-10-13-p4-enterprise-demo-infra"; do
  wt="${pair%%:*}"; plan="${pair#*:}"
  src="$ROOT/.worktrees/$wt/.superpowers/sdd/$plan/progress.md"
  [ -f "$src" ] || { echo "skip $wt (no ledger)"; continue; }
  python3 - "$src" "$OUT/$plan.md" <<'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
text = re.sub(r"[A-Za-z0-9._%+-]+@(?!anthropic\.com)[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "<redacted email>", text)
open(sys.argv[2], "w", encoding="utf-8").write(text)
PY
  echo "exported $plan ($(grep -c '^Task [0-9]*: complete' "$OUT/$plan.md" || true) tasks complete)"
done
