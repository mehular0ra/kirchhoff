#!/usr/bin/env bash
# Slices the live-run recording (shots/footage-live.spec.ts) into beat clips with 2 s handles, using its marks file, and
# prints each clip's real length for the issue #25 checklist. No audio; the voiceover is added in the edit.
#
# usage: shots/footage_cut.sh [live-run-full.webm] [live-run-marks.json] [out_dir]
#        defaults: e2e/out/footage/live-run-full.webm, .../live-run-marks.json, e2e/out/footage/mp4
# env:   FOOTAGE_VIDEO_OFFSET  seconds the recording starts before the marks' zero (default 0.5)
#        FOOTAGE_FPS (30)  FOOTAGE_CRF (14)
#
# Clips (alternatives to the static ones of footage.spec.ts; the editor picks per beat, see docs/submission/video/edit-plan.md):
#   v04-tender-in-live       the tender package, the drop onto the drop zone, the run starting
#   v04-intake-cards-live    the plan gate: requirement cards, "quote verified" chips, the quote counter, the open question
#   v05-agents-at-work       plan approved until the option gate (the compressed beat: speed = real length / 13 s)
#   v07-erp-swap-live        the option gate: three cards and the R15 swap line
#   v09-sign-off             the review page, Approve, the stamp, the PRs and the CRM stage
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
IN="${1:-$HERE/../out/footage/live-run-full.webm}"
MARKS="${2:-$HERE/../out/footage/live-run-marks.json}"
OUT="${3:-$HERE/../out/footage/mp4}"
OFFSET="${FOOTAGE_VIDEO_OFFSET:-0.5}"
FPS="${FOOTAGE_FPS:-30}"
CRF="${FOOTAGE_CRF:-14}"
HANDLE=2

command -v ffmpeg >/dev/null 2>&1 || { echo "footage_cut: ffmpeg is not on PATH" >&2; exit 1; }
[ -f "$IN" ] || { echo "footage_cut: no recording at $IN" >&2; exit 1; }
[ -f "$MARKS" ] || { echo "footage_cut: no marks file at $MARKS" >&2; exit 1; }
mkdir -p "$OUT"

# name  start-mark  end-mark   (the 2 s handles are added on both sides)
SPEC="v04-tender-in-live page_ready started
v04-intake-cards-live plan_gate plan_approved
v05-agents-at-work plan_approved option_gate
v05b-routing-and-check-live? r1_shown r2_held
v07-erp-swap-live option_gate option_hold_end
v09-sign-off review_page_ready end"

printf '%-24s %9s %9s  %s\n' clip start_s seconds marks
while read -r name a b; do
  [ -n "$name" ] || continue
  # a trailing ? marks a clip that older recordings do not have the marks for: it is skipped when they are missing
  skip_missing="${FOOTAGE_SKIP_MISSING:-0}"
  case "$name" in *\?) name="${name%\?}"; skip_missing=1 ;; esac
  read -r start dur < <(FOOTAGE_SKIP_MISSING="$skip_missing" python3 - "$MARKS" "$a" "$b" "$OFFSET" "$HANDLE" <<'PY' | tr -d '\015'
import json, os, sys
marks = json.load(open(sys.argv[1]))["marks_s"]
a, b, off, h = sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5])
if a not in marks or b not in marks:
    if os.environ.get("FOOTAGE_SKIP_MISSING") == "1":
        print("SKIP SKIP")  # an unsigned live run (E2E_FOOTAGE_SIGN=0) has no sign-off marks
        sys.exit(0)
    sys.exit(f"footage_cut: mark {a!r} or {b!r} missing from the marks file")
start = max(0.0, marks[a] + off - h)
end = marks[b] + off + h
print(f"{start:.2f} {end - start:.2f}")
PY
)
  if [ "$start" = "SKIP" ]; then
    printf '%-24s %9s %9s  %s -> %s (marks missing, skipped)\n' "$name" - - "$a" "$b"
    continue
  fi
  ffmpeg -nostdin -y -v error -ss "$start" -i "$IN" -t "$dur" -an -vf "fps=$FPS" -c:v libx264 -preset slow -crf "$CRF" -pix_fmt yuv420p -movflags +faststart "$OUT/$name.mp4"
  real="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$OUT/$name.mp4")"
  printf '%-24s %9.1f %9.1f  %s -> %s\n' "$name" "$start" "$real" "$a" "$b"
done <<< "$SPEC"
