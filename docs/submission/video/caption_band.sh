#!/usr/bin/env bash
#
# caption_band.sh — the final step of the Kirchhoff video export: mux the picture with the audio and put the captions in
# a band UNDER the picture, so a caption never covers the app's own text (issue #25, Mehul's option 1).
#
# Layout (16:9 stays 16:9, 1920 x 1080):
#
#     +------------------------------------------+   y = 0
#     |  gutter |   picture, 90 %  1728 x 972 | gutter |
#     |   96 px |  (the 1080p picture, scaled)  | 96 px |
#     +------------------------------------------+   y = 972
#     |          caption band, 108 px            |   captions only, white on black
#     +------------------------------------------+   y = 1080
#
# Usage:
#   caption_band.sh <picture.mp4> <audio.m4a> <captions.srt | -> <out.mp4>
#
#   <picture.mp4>   the assembled, silent 1920x1080 picture (assemble.sh's .assemble_tmp/assembled_video.mp4)
#   <audio.m4a>     the mixed audio
#   <captions.srt>  the captions, or "-" for none (then the picture stays full-frame, no band, as before)
#
# Why an ASS file and not `subtitles=captions.srt` with force_style: ffmpeg converts an SRT into ASS with a 384x288
# coordinate space, so a pixel margin or font size in force_style is scaled by about 5x and pushes the text off the
# band. We convert once, then set PlayResX/PlayResY to the real output size so every number in the style is a real pixel.
#
# Overridable (environment): FINAL_PRESET (default slow), FINAL_CRF (default 18), FONT_NAME (default Arial),
# FONT_SIZE (default 34). Keep the geometry in sync with check_export.py (its --self-test fails if they drift).
#
# This script only reads its four arguments and writes <out.mp4> (plus a temp folder it removes).

set -euo pipefail

OUT_W=1920
OUT_H=1080
PIC_W=1728                      # 90 % of 1920
PIC_H=972                       # 90 % of 1080, so the picture keeps 16:9 exactly
PIC_X=$(( (OUT_W - PIC_W) / 2 ))   # 96
FONT_NAME="${FONT_NAME:-Arial}"
FONT_SIZE="${FONT_SIZE:-34}"    # two lines fit the 108 px band (2 x ~41 px + margin)
PRESET="${FINAL_PRESET:-slow}"
CRF="${FINAL_CRF:-18}"

if [ $# -ne 4 ]; then
  echo "Usage: $0 <picture.mp4> <audio.m4a> <captions.srt | -> <out.mp4>" >&2
  exit 1
fi
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ERROR: ffmpeg is not installed or not on PATH." >&2
  exit 1
fi

# An absolute path a native ffmpeg understands. On Git Bash for Windows, `pwd -W` gives C:/... where plain `pwd`
# gives /c/..., which ffmpeg cannot open; everywhere else `pwd -W` fails and plain `pwd` is used.
abspath() {
  local dir
  dir="$(cd "$(dirname "$1")" && { pwd -W 2>/dev/null || pwd; })"
  printf '%s/%s' "$dir" "$(basename "$1")"
}

PICTURE="$(abspath "$1")"
AUDIO="$(abspath "$2")"
SRT="$3"
OUT="$(abspath "$4")"

for f in "$PICTURE" "$AUDIO"; do
  [ -f "$f" ] || { echo "ERROR: not found: $f" >&2; exit 1; }
done

ENCODE=(-map 0:v -map 1:a -c:v libx264 -preset "$PRESET" -crf "$CRF" -pix_fmt yuv420p -c:a aac -b:a 192k -shortest)

if [ "$SRT" = "-" ]; then
  # No captions: nothing to put in a band, so the picture stays full-frame (the old behaviour).
  ffmpeg -y -loglevel error -i "$PICTURE" -i "$AUDIO" "${ENCODE[@]}" "$OUT"
  echo "Muxed without captions: $OUT"
  exit 0
fi

[ -f "$SRT" ] || { echo "ERROR: captions not found: $SRT" >&2; exit 1; }
SRT="$(abspath "$SRT")"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# SRT -> ASS, then make the ASS coordinate space the real output size and set the caption style in real pixels:
# white text, black outline, bottom-centre, side margins aligned with the picture, 14 px above the bottom edge.
# Drop draft-note cues (shorter than 0.1 s, like the 10 ms note at the top of captions.srt) before burning in: libass stacks a later
# cue ABOVE an overlapping one and keeps it there for the whole cue, so the note would float the first real caption over the picture.
tr -d '\r' < "$SRT" | awk -v RS= -v ORS='\n\n' '
  function secs(t,   a) { split(t, a, /[:,.]/); return a[1] * 3600 + a[2] * 60 + a[3] + a[4] / 1000 }
  { n = split($0, L, "\n"); if (n >= 3 && L[2] ~ /-->/) { split(L[2], T, / --> /); if (secs(T[2]) - secs(T[1]) < 0.1) next } print }' > "$TMP/clean.srt"
grep -q -- '-->' "$TMP/clean.srt" || { echo "ERROR: no usable caption cue left in $SRT" >&2; exit 1; }
ffmpeg -y -loglevel error -i "$TMP/clean.srt" "$TMP/raw.ass"
STYLE="Style: Default,${FONT_NAME},${FONT_SIZE},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,0,2,${PIC_X},${PIC_X},14,1"
# In a sed replacement an unescaped "&" means "the whole match", and the ASS colours are written &H00FFFFFF: escape them.
STYLE_SED="$(printf '%s' "$STYLE" | sed 's/[&|\\]/\\&/g')"
tr -d '\r' < "$TMP/raw.ass" | sed \
  -e "s|^PlayResX:.*|PlayResX: ${OUT_W}|" \
  -e "s|^PlayResY:.*|PlayResY: ${OUT_H}|" \
  -e "s|^Style: Default,.*|${STYLE_SED}|" > "$TMP/captions.ass"
grep -qxF "PlayResX: ${OUT_W}" "$TMP/captions.ass" || { echo "ERROR: could not set PlayResX in the ASS file" >&2; exit 1; }
grep -qxF "PlayResY: ${OUT_H}" "$TMP/captions.ass" || { echo "ERROR: could not set PlayResY in the ASS file" >&2; exit 1; }
grep -qxF "$STYLE" "$TMP/captions.ass" || { echo "ERROR: the caption style line is not what was asked for" >&2; exit 1; }

# Run ffmpeg from the temp folder with a RELATIVE subtitle file name: no path escaping problems on any OS.
VF="scale=${PIC_W}:${PIC_H}:flags=lanczos,pad=${OUT_W}:${OUT_H}:${PIC_X}:0:color=black,setsar=1,subtitles=captions.ass"
( cd "$TMP" && ffmpeg -y -loglevel error -i "$PICTURE" -i "$AUDIO" -vf "$VF" "${ENCODE[@]}" "$OUT" )
echo "Muxed with the caption band: $OUT"
