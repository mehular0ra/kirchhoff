#!/usr/bin/env bash
#
# assemble.sh — Kirchhoff AI Builder Cup video assembler
#
# Concatenates the per-beat clips (named per GitHub issue #25: vNN-<beat>.mp4),
# applies the trims and speed ramps from edit-plan.md, mixes in the voiceover
# (and an optional ducked music bed), and puts captions.srt in a caption band
# UNDER the picture (caption_band.sh: picture at 90 % inside the 16:9 frame, so a
# caption never covers the app's own text). The finished file is then checked by
# check_export.py (the export gate: 16:9, picture untouched, captions inside the band).
#
# This script never touches the repo. It only reads from and writes to the
# WORK_DIR you pass it on the command line. Put your clips, vo.wav, and
# (optionally) music.mp3 in WORK_DIR before running.
#
# Usage:
#   ./assemble.sh <work_dir> [beat5_speed_factor]
#
#   <work_dir>            Folder containing v01-cold-open.mp4 ... v13-end-card.mp4,
#                         vo.wav, and optionally music.mp3. Output is written here too.
#   [beat5_speed_factor]  Speed multiplier for beat 5 (agents at work), e.g. 4, 6, 8.
#                         Compute this as (real captured length of beat 5) / 13 s,
#                         per edit-plan.md. Defaults to 1 (no speed-up) if omitted —
#                         the script will NOT guess a multiplier for you, because an
#                         honest label requires the real number.
#
# This script does NOT install ffmpeg. It only checks whether it's on PATH.

set -euo pipefail

# ---------------------------------------------------------------------------
# 0. Preflight: ffmpeg must already be installed. We never install anything.
# ---------------------------------------------------------------------------
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ERROR: ffmpeg is not installed or not on PATH." >&2
  echo "This script will not install it. Install ffmpeg yourself, then re-run." >&2
  exit 1
fi
echo "ffmpeg found: $(command -v ffmpeg)"
ffmpeg -version | head -1

# ---------------------------------------------------------------------------
# 1. Arguments
# ---------------------------------------------------------------------------
if [ $# -lt 1 ]; then
  echo "Usage: $0 <work_dir> [beat5_speed_factor]" >&2
  exit 1
fi

WORK_DIR="$1"
BEAT5_SPEED="${2:-1}"

if [ ! -d "$WORK_DIR" ]; then
  echo "ERROR: work_dir '$WORK_DIR' does not exist." >&2
  exit 1
fi
# An absolute directory a native ffmpeg can open: on Git Bash for Windows `pwd -W` gives C:/... (plain `pwd` gives
# /c/..., which ffmpeg cannot open); everywhere else `pwd -W` fails and plain `pwd` is used.
native_pwd() { pwd -W 2>/dev/null || pwd; }
WORK_DIR="$(cd "$WORK_DIR" && native_pwd)"   # absolute path; we never cd into the repo
echo "Working folder: $WORK_DIR"
echo "Beat 5 speed factor: ${BEAT5_SPEED}x"

TMP_DIR="$WORK_DIR/.assemble_tmp"
mkdir -p "$TMP_DIR"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && native_pwd)"
SRT_PATH="$SCRIPT_DIR/captions.srt"
if [ ! -f "$SRT_PATH" ]; then
  echo "WARNING: captions.srt not found next to this script ($SRT_PATH)." >&2
  echo "Captions will NOT be burned in. Re-sync captions.srt against vo.wav first," >&2
  echo "then copy it into this folder or re-run once it's present." >&2
  SRT_PATH=""
fi

VO_PATH="$WORK_DIR/vo.wav"
if [ ! -f "$VO_PATH" ]; then
  echo "ERROR: $VO_PATH not found. Put the voiceover recording there as vo.wav." >&2
  exit 1
fi

MUSIC_PATH="$WORK_DIR/music.mp3"
HAS_MUSIC=0
if [ -f "$MUSIC_PATH" ]; then
  HAS_MUSIC=1
  echo "Music bed found: $MUSIC_PATH (will be ducked under the VO)."
  echo "Reminder: confirm it is royalty-free and note its source/licence in edit-plan.md."
else
  echo "No music.mp3 found in $WORK_DIR — proceeding VO-only (compliant default)."
fi

# ---------------------------------------------------------------------------
# 2. Beat definitions, per edit-plan.md
#    format: "clip_filename|trim_in_seconds|trim_out_seconds|speed_factor"
#    trim_in/out are offsets INTO THE CLIP (the clip has a 2s handle before
#    and after per issue #25, so trim_in=2.0 starts right at the beat's
#    intended first frame for an un-padded clip of exactly beat-duration+4s).
#    *** These in/out values are placeholders from the planned beat durations.
#    *** Re-check each one against the REAL clip length before running —
#    *** a clip shot longer or shorter than planned needs its own trim.
# ---------------------------------------------------------------------------
BEATS=(
  "v01-cold-open.mp4|2.0|12.0|1"
  "v02-title.mp4|2.0|8.0|1"
  "v03-problem.mp4|2.0|12.0|1"
  "v04-tender-in.mp4|2.0|18.0|1"
  "v05-agents-at-work.mp4|2.0|15.0|${BEAT5_SPEED}"
  "v06-checker.mp4|2.0|30.0|1"
  "v07-erp-swap.mp4|2.0|19.0|1"
  "v08-what-if-voice.mp4|2.0|18.0|1"
  "v09-sign-off.mp4|2.0|18.0|1"
  "v10-integrations.mp4|2.0|9.0|1"
  "v11-grid-solar.mp4|2.0|10.0|1"
  "v12-proof.mp4|2.0|12.0|1"
  "v13-end-card.mp4|2.0|10.0|1"
)

# ---------------------------------------------------------------------------
# 3. Trim (and speed-ramp beat 5) each clip into a uniform intermediate
#    (1920x1080, 30fps, yuv420p, no audio — audio comes from vo.wav/music).
# ---------------------------------------------------------------------------
CONCAT_LIST="$TMP_DIR/concat_list.txt"
: > "$CONCAT_LIST"

idx=0
for beat in "${BEATS[@]}"; do
  idx=$((idx + 1))
  IFS='|' read -r clip_name in_s out_s speed <<< "$beat"
  src="$WORK_DIR/$clip_name"
  out="$TMP_DIR/$(printf 'beat%02d.mp4' "$idx")"

  if [ ! -f "$src" ]; then
    echo "ERROR: expected clip not found: $src" >&2
    echo "Check the clip map in edit-plan.md against what Jayadratha delivered." >&2
    exit 1
  fi

  echo "Beat $idx: $clip_name  in=${in_s}s out=${out_s}s speed=${speed}x"

  # Video-only trim, scale/pad to 1080p, conform to 30fps, strip audio.
  # If speed != 1, apply setpts to compress the clip (speed-ramp / time-compress).
  if [ "$speed" = "1" ]; then
    ffmpeg -y -loglevel error \
      -ss "$in_s" -to "$out_s" -i "$src" \
      -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30" \
      -an -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p \
      "$out"
  else
    ffmpeg -y -loglevel error \
      -ss "$in_s" -to "$out_s" -i "$src" \
      -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setpts=PTS/${speed},fps=30" \
      -an -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p \
      "$out"
  fi

  echo "file '$out'" >> "$CONCAT_LIST"
done

# ---------------------------------------------------------------------------
# 4. Concatenate all beats into one silent video timeline.
# ---------------------------------------------------------------------------
ASSEMBLED_VIDEO="$TMP_DIR/assembled_video.mp4"
ffmpeg -y -loglevel error -f concat -safe 0 -i "$CONCAT_LIST" -c copy "$ASSEMBLED_VIDEO"
echo "Assembled silent video: $ASSEMBLED_VIDEO"

# ---------------------------------------------------------------------------
# 5. Mix audio: VO is the anchor track. If a music bed exists, duck it under
#    the VO with a sidechain compressor, and normalise the final mix to
#    -14 LUFS integrated.
# ---------------------------------------------------------------------------
MIXED_AUDIO="$TMP_DIR/mixed_audio.m4a"
if [ "$HAS_MUSIC" = "1" ]; then
  ffmpeg -y -loglevel error \
    -i "$VO_PATH" -i "$MUSIC_PATH" \
    -filter_complex "\
      [1:a]volume=0.5[music]; \
      [music][0:a]sidechaincompress=threshold=0.05:ratio=8:attack=5:release=300[ducked]; \
      [0:a][ducked]amix=inputs=2:duration=first:dropout_transition=2[aout]; \
      [aout]loudnorm=I=-14:TP=-1.0:LRA=11[final]" \
    -map "[final]" -c:a aac -b:a 192k \
    "$MIXED_AUDIO"
else
  ffmpeg -y -loglevel error \
    -i "$VO_PATH" \
    -filter_complex "[0:a]loudnorm=I=-14:TP=-1.0:LRA=11[final]" \
    -map "[final]" -c:a aac -b:a 192k \
    "$MIXED_AUDIO"
fi
echo "Mixed audio (-14 LUFS target): $MIXED_AUDIO"

# ---------------------------------------------------------------------------
# 6. Mux video + mixed audio, trimming/padding audio to the video length, and put
#    captions.srt (if found) in the caption band under a 90 % picture (see
#    caption_band.sh). Without captions the picture stays full-frame.
# ---------------------------------------------------------------------------
FINAL_OUT="$WORK_DIR/final.mp4"
bash "$SCRIPT_DIR/caption_band.sh" "$ASSEMBLED_VIDEO" "$MIXED_AUDIO" "${SRT_PATH:--}" "$FINAL_OUT"

echo ""
echo "Done. Final export: $FINAL_OUT"
echo "Check runtime is strictly under 3:00:"
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$FINAL_OUT" 2>/dev/null || true

# ---------------------------------------------------------------------------
# 7. The export gate: the final file must be 16:9 with the picture untouched and every
#    caption inside the band (check_export.py, standard library + ffmpeg only).
# ---------------------------------------------------------------------------
GATE_FAILED=0
PY="$(command -v python3 || command -v python || true)"
if [ -z "$PY" ]; then
  echo "WARNING: python3 not found, the export gate did NOT run. Run it by hand:" >&2
  echo "  python3 $SCRIPT_DIR/check_export.py $FINAL_OUT --clean $ASSEMBLED_VIDEO" >&2
elif [ -z "$SRT_PATH" ]; then
  echo "WARNING: no captions were burned in, so the export gate (which checks them) was skipped." >&2
else
  echo ""
  echo "Export gate (check_export.py):"
  "$PY" "$SCRIPT_DIR/check_export.py" "$FINAL_OUT" --clean "$ASSEMBLED_VIDEO" --srt "$SRT_PATH" || GATE_FAILED=1
fi

echo ""
echo "Reminders before upload:"
echo "  - Re-sync captions.srt against the real vo.wav if you haven't already (see its header note)."
echo "  - Verify every on-screen number against the actual recorded run (see edit-plan.md Open items)."
echo "  - Confirm the fictional-data banner and disclaimers are visible where required."
echo "  - Upload as Public on YouTube, not Unlisted."

if [ "$GATE_FAILED" != "0" ]; then
  echo "" >&2
  echo "EXPORT GATE FAILED: do not upload $FINAL_OUT. See the FAIL lines above." >&2
  exit 2
fi
