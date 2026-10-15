#!/usr/bin/env bash
# Converts the footage clips (WebM from Playwright, shots/footage.spec.ts) to .mp4 for the edit (issue #25) and prints each
# clip's real length, so the checklist on the issue is measured, not guessed. No audio track: the voiceover and the
# in-clip question are added in the edit.
#
# usage: shots/footage_to_mp4.sh [in_dir] [out_dir]
#        defaults: e2e/out/footage  and  e2e/out/footage/mp4
# env:   FOOTAGE_FPS (default 30)  FOOTAGE_CRF (default 14, lower is sharper)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
IN="${1:-$HERE/../out/footage}"
OUT="${2:-$IN/mp4}"
FPS="${FOOTAGE_FPS:-30}"
CRF="${FOOTAGE_CRF:-14}"

command -v ffmpeg >/dev/null 2>&1 || { echo "footage_to_mp4: ffmpeg is not on PATH" >&2; exit 1; }
command -v ffprobe >/dev/null 2>&1 || { echo "footage_to_mp4: ffprobe is not on PATH" >&2; exit 1; }
shopt -s nullglob
clips=("$IN"/*.webm)
[ ${#clips[@]} -gt 0 ] || { echo "footage_to_mp4: no .webm clips in $IN" >&2; exit 1; }
mkdir -p "$OUT"

printf '%-22s %9s %9s  %s\n' clip seconds MB size
for f in "${clips[@]}"; do
  name="$(basename "$f" .webm)"
  ffmpeg -nostdin -y -v error -i "$f" -an -vf "fps=$FPS" -c:v libx264 -preset slow -crf "$CRF" -pix_fmt yuv420p -movflags +faststart "$OUT/$name.mp4"
  secs="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$OUT/$name.mp4")"
  dims="$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$OUT/$name.mp4")"
  mb="$(du -m "$OUT/$name.mp4" | cut -f1)"
  printf '%-22s %9.1f %9s  %s\n' "$name" "$secs" "$mb" "$dims"
done
