#!/usr/bin/env bash
#
# assemble.sh — Kirchhoff AI Builder Cup video assembler
#
# Concatenates the per-beat clips, applies the trims and speed ramps, mixes in the voiceover (and an optional
# ducked music bed), and puts the captions in a caption band UNDER the picture (caption_band.sh: picture at 90 %
# inside the 16:9 frame, so a caption never covers the app's own text). The finished file is then checked by
# check_export.py (the export gate: 16:9, runtime ceiling, picture untouched, captions inside the band). The gate
# ALWAYS runs: with no captions file it checks the format and the ceiling and reports the band checks as SKIPPED.
#
# Two plans, chosen with PLAN (default v1, unchanged):
#
#   PLAN=v1  the original 13-beat cut (edit-plan.md): clips v01..v13 plus ONE voiceover file, vo.wav.
#   PLAN=v2  the 17-beat cut of edit-plan-v2.md: product footage from WORK_DIR, scene clips from scenes/out/, ONE
#            voice WAV per beat, and the intro voices carried by the intro scene clips themselves.
#
# This script never touches the repo. It only reads from and writes to the WORK_DIR you pass it on the command
# line (plus the scene folder, read-only).
#
# Usage:
#   ./assemble.sh <work_dir> [speed_factor]                    # v1
#   PLAN=v2 ./assemble.sh <work_dir> [speed_factor]            # v2
#
#   <work_dir>      v1: v01-cold-open.mp4 ... v13-end-card.mp4, vo.wav, optionally music.mp3.
#                   v2: the product footage v01-cold-open.mp4, v04-tender-in.mp4, v05-agents-at-work.mp4,
#                       v06-checker.mp4, v07-erp-swap.mp4, v08-what-if-voice.mp4, v09-sign-off.mp4; the voice WAVs
#                       bNN-<name>.wav (NN = the beat number in edit-plan-v2.md, e.g. b04-problem.wav) in $VO_DIR;
#                       optionally music.mp3. Output is written here too.
#   [speed_factor]  Speed multiplier of the time-compressed beat (v1: beat 5, v2: beat 8, agents at work), i.e.
#                   (real length of that beat in the clip) / (its length in the video). v1 defaults to 1 (no
#                   speed-up): the script will NOT guess a multiplier, because an honest label needs the real number.
#                   v2 defaults to the MEASURED number, (clip length - 2 s head handle - 2 s tail handle) / 10 s, and says
#                   so; pass your own if the clip has other handles. v2 burns "time-compressed xN" and the real
#                   time covered into the picture of that beat; at 1 there is no label.
#
# Environment (all optional):
#   PLAN             v1 (default) or v2.
#   CAPTIONS         the captions file. v1 default: captions.srt next to this script. v2 default: captions-v2.srt next to
#                    this script. Without a file the picture stays full-frame and the gate skips only the band checks.
#   MAX_SECONDS      the runtime ceiling the gate enforces. v1 default 180 (strictly under 3:00), v2 default 239 (3:59: the form asks for 3 to 4 minutes, Mehul's decision of 17 Oct).
#   SCENES_DIR       v2: the rendered scene clips (default: scenes/out next to this script).
#   VO_DIR           v2: the voice WAVs (default: <work_dir>/vo).
#   INCLUDE_JD_INTRO v2: 1 adds Jayadratha's intro (beat 3b, s1c-intro-jayadratha.mp4). Default 0.
#   FINAL_PRESET     passed to caption_band.sh (default slow); FINAL_CRF (default 18).
#
# v2 writes <work_dir>/beat-starts.txt: every beat's MEASURED start and length, and the wav@start arguments for
# transcribe.py, so the captions are timed against the cut that was really built.
#
# Self-test: python3 assemble_selftest.py (synthetic clips; v1 is compared with the committed version, v2 is checked on its own).
#
# This script does NOT install ffmpeg. It only checks whether it's on PATH.

set -euo pipefail
if [ -n "${LC_ALL:-}" ]; then export LANG="$LC_ALL"; fi   # keep its character set (UTF-8 paths) once LC_ALL is cleared
unset LC_ALL   # LC_ALL would override the next line (a decimal-comma LC_ALL makes bash printf reject the "7.000000" of ffprobe)
export LC_NUMERIC=C   # bash printf and awk must read the numbers of ffprobe the same way in every locale

# ---------------------------------------------------------------------------
# 0. Preflight: ffmpeg must already be installed. We never install anything.
# ---------------------------------------------------------------------------
if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  echo "ERROR: ffmpeg/ffprobe is not installed or not on PATH." >&2
  echo "This script will not install it. Install ffmpeg yourself, then re-run." >&2
  exit 1
fi
echo "ffmpeg found: $(command -v ffmpeg)"
ffmpeg -version | head -1

# ---------------------------------------------------------------------------
# 1. Arguments
# ---------------------------------------------------------------------------
if [ $# -lt 1 ]; then
  echo "Usage: [PLAN=v2] $0 <work_dir> [speed_factor]" >&2
  exit 1
fi

PLAN="${PLAN:-v1}"
case "$PLAN" in
  v1|v2) ;;
  *) echo "ERROR: PLAN must be v1 or v2, not '$PLAN'." >&2; exit 1 ;;
esac

WORK_DIR="$1"
SPEED_ARG="${2:-}"           # empty = not given

if [ ! -d "$WORK_DIR" ]; then
  echo "ERROR: work_dir '$WORK_DIR' does not exist." >&2
  exit 1
fi
# An absolute directory a native ffmpeg can open: on Git Bash for Windows `pwd -W` gives C:/... (plain `pwd` gives
# /c/..., which ffmpeg cannot open); everywhere else `pwd -W` fails and plain `pwd` is used.
native_pwd() { pwd -W 2>/dev/null || pwd; }
WORK_DIR="$(cd "$WORK_DIR" && native_pwd)"   # absolute path; we never cd into the repo
echo "Working folder: $WORK_DIR"
echo "Plan: $PLAN"

TMP_DIR="$WORK_DIR/.assemble_tmp"
mkdir -p "$TMP_DIR"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && native_pwd)"
if [ "$PLAN" = "v2" ]; then
  DEFAULT_SRT="$SCRIPT_DIR/captions-v2.srt"
  MAX_SECONDS="${MAX_SECONDS:-239}"
else
  DEFAULT_SRT="$SCRIPT_DIR/captions.srt"
  MAX_SECONDS="${MAX_SECONDS:-180}"
fi
SRT_PATH="${CAPTIONS:-$DEFAULT_SRT}"
echo "Runtime ceiling for the export gate: ${MAX_SECONDS} s"
if [ ! -f "$SRT_PATH" ]; then
  echo "WARNING: captions not found ($SRT_PATH)." >&2
  if [ "$PLAN" = "v2" ]; then
    echo "Captions will NOT be burned in. Build captions-v2.srt with transcribe.py from your recording" >&2
    echo "(see beat-starts.txt for the wav@start arguments), then re-run." >&2
  else
    echo "Captions will NOT be burned in. Re-sync captions.srt against vo.wav first," >&2
    echo "then copy it into this folder or re-run once it's present." >&2
  fi
  SRT_PATH=""
fi

MUSIC_PATH="$WORK_DIR/music.mp3"
HAS_MUSIC=0
if [ -f "$MUSIC_PATH" ]; then
  HAS_MUSIC=1
  echo "Music bed found: $MUSIC_PATH (will be ducked under the VO)."
  echo "Reminder: confirm it is royalty-free and note its source/licence in the edit plan."
else
  echo "No music.mp3 found in $WORK_DIR — proceeding VO-only (compliant default)."
fi

probe_duration() { ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$1"; }
has_audio() { [ -n "$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$1" 2>/dev/null)" ]; }

# conform_beat <src> <in_s> <out_s|end> <speed> <dst> [label.ass in $TMP_DIR]
# Video-only trim, scale/pad to 1080p, conform to 30fps, strip audio (the audio is mixed separately below).
# If speed != 1, setpts compresses the clip (speed-ramp / time-compress). With a label file the beat gets it burned in.
conform_beat() {
  local src="$1" in_s="$2" out_s="$3" speed="$4" dst="$5" label="${6:-}"
  local vf="scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2"
  if [ "$speed" != "1" ]; then vf="$vf,setpts=PTS/${speed}"; fi
  vf="$vf,fps=30"
  if [ -n "$label" ]; then vf="$vf,subtitles=$label"; fi
  local -a seek=(-ss "$in_s")
  if [ "$out_s" != "end" ]; then seek+=(-to "$out_s"); fi
  (
    # a RELATIVE subtitle file name, run from the temp folder: no path escaping problems on any OS
    if [ -n "$label" ]; then cd "$TMP_DIR"; fi
    ffmpeg -y -loglevel error "${seek[@]}" -i "$src" -vf "$vf" \
      -an -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p "$dst"
  )
}

CONCAT_LIST="$TMP_DIR/concat_list.txt"
: > "$CONCAT_LIST"

# The audio the next steps mix: v1 = vo.wav, v2 = the timeline built in section 4b.
VO_PATH=""
MUTE_MUSIC_WINDOWS=()        # v2: "start|end" seconds in which the music bed is off (the intro voices)

if [ "$PLAN" = "v1" ]; then
  # -------------------------------------------------------------------------
  # 2. v1: beat definitions, per edit-plan.md
  #    format: "clip_filename|trim_in_seconds|trim_out_seconds|speed_factor"
  #    trim_in/out are offsets INTO THE CLIP (the clip has a 2s handle before
  #    and after per issue #25, so trim_in=2.0 starts right at the beat's
  #    intended first frame for an un-padded clip of exactly beat-duration+4s).
  #    *** These in/out values are placeholders from the planned beat durations.
  #    *** Re-check each one against the REAL clip length before running —
  #    *** a clip shot longer or shorter than planned needs its own trim.
  # -------------------------------------------------------------------------
  BEAT5_SPEED="${SPEED_ARG:-1}"
  echo "Beat 5 speed factor: ${BEAT5_SPEED}x"
  VO_PATH="$WORK_DIR/vo.wav"
  if [ ! -f "$VO_PATH" ]; then
    echo "ERROR: $VO_PATH not found. Put the voiceover recording there as vo.wav." >&2
    exit 1
  fi
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

  # -------------------------------------------------------------------------
  # 3. Trim (and speed-ramp beat 5) each clip into a uniform intermediate
  #    (1920x1080, 30fps, yuv420p, no audio — audio comes from vo.wav/music).
  # -------------------------------------------------------------------------
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
    conform_beat "$src" "$in_s" "$out_s" "$speed" "$out"
    echo "file '$out'" >> "$CONCAT_LIST"
  done
else
  # -------------------------------------------------------------------------
  # 2. v2: beat definitions, per edit-plan-v2.md §2
  #    format: "id|where|clip|in|out|plan_s|keep_audio|voice_beat"
  #      where  w = product footage in WORK_DIR (a 2 s handle each side: in=2.0, out = 2.0 + the beat's seconds)
  #             s = scene clip in SCENES_DIR (no trim: in=0, out=end)
  #             J = optional scene, only with INCLUDE_JD_INTRO=1
  #      out    "COMP" = the time-compressed beat: 2.0 + 10 s x speed
  #      plan_s the beat's planned seconds (0 = follows the clip: a warning is printed when the real length is more
  #             than 1 s off the plan)
  #      keep_audio  keep = the clip's own audio goes into the mix (the intro voices; the in-clip question of beat 12)
  #      voice_beat  the NN of bNN-<name>.wav in VO_DIR, or - for a beat with no WAV
  #    Order and lengths are edit-plan-v2.md's. Re-check every footage in/out against the REAL clip length.
  # -------------------------------------------------------------------------
  SCENES_DIR="${SCENES_DIR:-$SCRIPT_DIR/scenes/out}"
  VO_DIR="${VO_DIR:-$WORK_DIR/vo}"
  INCLUDE_JD_INTRO="${INCLUDE_JD_INTRO:-0}"
  V2_BEATS=(
    "1|w|v01-cold-open.mp4|2.0|9.0|7|-|1"
    "2|s|s1-title.mp4|0|end|5|-|2"
    "3|s|s1b-intro-mehul.mp4|0|end|0|keep|-"
    "3b|J|s1c-intro-jayadratha.mp4|0|end|0|keep|-"
    "4|s|s2-problem.mp4|0|end|9|-|4"
    "5|s|s3-requirements-in.mp4|0|end|14|-|5"
    "6|w|v04-tender-in.mp4|2.0|15.0|13|-|6"
    "7|s|s4-agents.mp4|0|end|7|-|7"
    "8|w|v05-agents-at-work.mp4|2.0|COMP|10|-|8"
    "9|s|s5-checks.mp4|0|end|8|-|9"
    "10|w|v06-checker.mp4|2.0|17.0|15|-|10"
    "11|w|v07-erp-swap.mp4|2.0|12.0|10|-|11"
    "12|w|v08-what-if-voice.mp4|2.0|14.0|12|keep|12"
    "13|s|s6-sign.mp4|0|end|6|-|13"
    "14|w|v09-sign-off.mp4|2.0|8.0|6|-|14"
    "15|s|s7-connectors.mp4|0|end|12|-|15"
    "16|s|s8-google-cloud.mp4|0|end|8|-|16"
    "17|s|s9-end.mp4|0|end|7|-|17"
  )

  # find the voice WAV of a beat: exactly one bNN-*.wav, or none (that beat is silent). Sets VO_FOUND.
  find_vo() {
    local n="$1" pad
    pad="$(printf '%02d' "$n")"
    local -a m
    shopt -s nullglob
    m=("$VO_DIR"/b"$pad"-*.wav)
    shopt -u nullglob
    VO_FOUND=""
    if [ "${#m[@]}" -gt 1 ]; then
      echo "ERROR: more than one voice file for beat $n in $VO_DIR: ${m[*]##*/}" >&2
      exit 1
    fi
    if [ "${#m[@]}" -eq 1 ]; then VO_FOUND="${m[0]}"; fi
  }

  # Pre-flight: every clip that will be needed must exist. Report all that are missing in one go.
  missing=0
  for beat in "${V2_BEATS[@]}"; do
    IFS='|' read -r id where clip in_s out_s plan_s keep vo <<< "$beat"
    if [ "$where" = "J" ] && [ "$INCLUDE_JD_INTRO" != "1" ]; then continue; fi
    if [ "$where" = "w" ]; then src="$WORK_DIR/$clip"; else src="$SCENES_DIR/$clip"; fi
    if [ ! -f "$src" ]; then
      echo "ERROR: beat $id: clip not found: $src" >&2
      missing=1
    fi
    if [ "$vo" != "-" ]; then find_vo "$vo"; fi   # two voice files for one beat is an error: stop before encoding anything
  done
  if [ "$missing" != "0" ]; then
    echo "Render the scenes (scenes/render.py, see edit-plan-v2.md §1) and put the footage in $WORK_DIR." >&2
    exit 1
  fi

  # -------------------------------------------------------------------------
  # 3. v2: conform every beat to its own intermediate, then measure each one
  # -------------------------------------------------------------------------
  idx=0
  IDS=(); NAMES=(); DURS=(); PLANS=(); SRCS=(); INS=(); OUTS=(); KEEPS=(); VOS=()
  for beat in "${V2_BEATS[@]}"; do
    IFS='|' read -r id where clip in_s out_s plan_s keep vo <<< "$beat"
    if [ "$where" = "J" ] && [ "$INCLUDE_JD_INTRO" != "1" ]; then continue; fi
    idx=$((idx + 1))
    if [ "$where" = "w" ]; then src="$WORK_DIR/$clip"; else src="$SCENES_DIR/$clip"; fi
    out="$TMP_DIR/$(printf 'beat%02d.mp4' "$idx")"
    speed=1
    label=""
    if [ "$out_s" = "COMP" ]; then
      if [ -n "$SPEED_ARG" ]; then
        speed="$SPEED_ARG"
        echo "Beat $id: time-compressed, speed factor ${speed}x (given)"
      else
        clip_len="$(probe_duration "$src")"
        speed="$(awk -v L="$clip_len" 'BEGIN { s = (L - 4) / 10; if (s < 1) s = 1; printf "%.1f", s }')"
        echo "Beat $id: time-compressed, speed factor ${speed}x MEASURED from the clip: (${clip_len} s - 2 s head handle - 2 s tail handle) / 10 s." >&2
        echo "         If the clip has other handles, pass the factor yourself as the second argument." >&2
      fi
      if awk -v s="$speed" 'BEGIN { exit !(s == 1) }'; then speed=1; fi
      out_s="$(awk -v S="$speed" 'BEGIN { printf "%.3f", 2.0 + 10 * S }')"
      if [ "$speed" != "1" ]; then
        # "time-compressed xN" and the real time covered, from the speed factor: one caption event per half second of the 10 s
        # beat, at the top centre (the free part of the app's header row). With a factor of 1 there is nothing to declare.
        label="beat_label.ass"
        awk -v N="$speed" -v D=10 '
          function ts(t,   cs) { cs = int(t * 100 + 0.5); return sprintf("%d:%02d:%02d.%02d", int(cs / 360000), int(cs / 6000) % 60, int(cs / 100) % 60, cs % 100) }
          BEGIN {
            x = "\303\227"
            print "[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 2\n"
            print "[V4+ Styles]"
            print "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding"
            print "Style: Default,Arial,22,&H00FFFFFF,&H00FFFFFF,&H40000000,&H40000000,0,0,0,0,100,100,0,0,3,5,0,8,20,20,62,1\n"
            print "[Events]"
            print "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text"
            for (i = 0; i * 0.5 < D; i++) {
              real = int(i * 0.5 * N)
              printf "Dialogue: 0,%s,%s,Default,,0,0,0,,time-compressed %s%g  \302\267  real time %d:%02d\n", ts(i * 0.5), ts((i + 1) * 0.5), x, N, int(real / 60), real % 60
            }
          }' > "$TMP_DIR/$label"
      fi
    fi
    if [ "$out_s" = "end" ]; then out_show="end"; else out_show="${out_s}s"; fi
    echo "Beat $id: $clip  in=${in_s}s out=${out_show} speed=${speed}x"
    conform_beat "$src" "$in_s" "$out_s" "$speed" "$out" "$label"
    echo "file '$out'" >> "$CONCAT_LIST"
    IDS+=("$id"); NAMES+=("$clip"); SRCS+=("$src"); INS+=("$in_s"); OUTS+=("$out_s"); KEEPS+=("$keep"); VOS+=("$vo"); PLANS+=("$plan_s")
    DURS+=("$(probe_duration "$out")")
  done
fi

# ---------------------------------------------------------------------------
# 4. Concatenate all beats into one silent video timeline.
# ---------------------------------------------------------------------------
ASSEMBLED_VIDEO="$TMP_DIR/assembled_video.mp4"
ffmpeg -y -loglevel error -f concat -safe 0 -i "$CONCAT_LIST" -c copy "$ASSEMBLED_VIDEO"
echo "Assembled silent video: $ASSEMBLED_VIDEO"
TOTAL_S="$(probe_duration "$ASSEMBLED_VIDEO")"

# ---------------------------------------------------------------------------
# 4b. v2: build the voice timeline. Every beat starts where the beats before it END (measured, not planned), the
#     voice WAV of a beat starts with the beat, the intro clips' own voice and the in-clip question of beat 12 go in
#     at their beat's start, and the result is padded with silence to exactly the picture's length (caption_band.sh
#     stops at the shorter of picture and sound, so a short sound would cut the picture).
# ---------------------------------------------------------------------------
if [ "$PLAN" = "v2" ]; then
  STARTS_FILE="$WORK_DIR/beat-starts.txt"
  VOICE_TIMELINE="$TMP_DIR/voice_timeline.wav"
  inputs=(); filt=""; labels=""; n=0
  add_audio() {   # <file> <start_s> <atrim prefix or empty>
    local ms
    ms="$(awk -v s="$2" 'BEGIN { printf "%d", s * 1000 + 0.5 }')"
    inputs+=(-i "$1")
    filt+="[$n:a]${3}aresample=48000,aformat=channel_layouts=mono,adelay=${ms}:all=1[a$n];"
    labels+="[a$n]"
    n=$((n + 1))
  }

  {
    echo "# Beat starts MEASURED from the encoded beats (edit-plan-v2.md order). Total: ${TOTAL_S} s."
    printf '# %-4s %-26s %9s %8s %6s  %s\n' beat clip start_s len_s plan_s voice
  } > "$STARTS_FILE"
  start="0"
  TRANSCRIBE_ARGS=()
  no_voice=()
  for i in "${!IDS[@]}"; do
    id="${IDS[$i]}"; dur="${DURS[$i]}"; keep="${KEEPS[$i]}"; vo="${VOS[$i]}"
    voice_note="-"
    if [ "$vo" != "-" ]; then
      find_vo "$vo"
      if [ -n "$VO_FOUND" ]; then
        vo_len="$(probe_duration "$VO_FOUND")"
        add_audio "$VO_FOUND" "$start" ""
        voice_note="$(basename "$VO_FOUND") ($(awk -v d="$vo_len" 'BEGIN { printf "%.1f", d }') s)"
        TRANSCRIBE_ARGS+=("$VO_FOUND@$(awk -v s="$start" 'BEGIN { printf "%.3f", s }')")
        if awk -v d="$vo_len" -v b="$dur" 'BEGIN { exit !(d > b + 2.0) }'; then
          echo "WARNING: the voice file of beat $id is $(awk -v d="$vo_len" 'BEGIN { printf "%.1f", d }') s, the beat only $(awk -v b="$dur" 'BEGIN { printf "%.1f", b }') s: unless the end of the file is silence it runs into the next beat." >&2
        fi
      else
        voice_note="(none: silent)"
        no_voice+=("$id")
      fi
    fi
    if [ "$keep" = "keep" ]; then
      if has_audio "${SRCS[$i]}"; then
        if [ "${OUTS[$i]}" = "end" ]; then pre=""; else pre="atrim=start=${INS[$i]}:end=${OUTS[$i]},asetpts=PTS-STARTPTS,"; fi
        add_audio "${SRCS[$i]}" "$start" "$pre"
        voice_note="$voice_note + own audio"
        # The clip's own audio over the SAME span that is mixed, as a WAV that starts with the beat: transcribe.py captions it (the intro voices, whose
        # delay render.py already put inside the clip, and the in-clip question of beat 12). Without this they would have no captions.
        own_wav="$TMP_DIR/own_${id}.wav"
        if [ "${OUTS[$i]}" = "end" ]; then
          ffmpeg -y -loglevel error -i "${SRCS[$i]}" -vn -ac 1 -ar 48000 -c:a pcm_s16le "$own_wav"
        else
          ffmpeg -y -loglevel error -ss "${INS[$i]}" -t "$(awk -v a="${INS[$i]}" -v b="${OUTS[$i]}" 'BEGIN { printf "%.3f", b - a }')" -i "${SRCS[$i]}" -vn -ac 1 -ar 48000 -c:a pcm_s16le "$own_wav"
        fi
        rm -f "$own_wav.words.json"   # transcribe.py caches word timings next to each WAV: a regenerated WAV must not be captioned from the old take
        own_silent=0
        own_max="$(ffmpeg -nostdin -hide_banner -i "$own_wav" -af volumedetect -vn -f null - 2>&1 | sed -n 's/.*max_volume: *\([^ ]*\) dB.*/\1/p' | head -1 || true)"
        case "$own_max" in
          "") own_silent=1 ;;   # volumedetect printed no level: the extracted track has no samples at all
          *inf*) own_silent=1 ;;
          *) if awk -v m="$own_max" 'BEGIN { exit !(m < -60) }'; then own_silent=1; fi ;;
        esac
        if [ "$own_silent" = "1" ]; then
          echo "WARNING: beat $id (${NAMES[$i]}) has an audio track, but it is silent or empty (no sample above -60 dB)." >&2
          if [ "$id" = "3" ] || [ "$id" = "3b" ]; then
            echo "         This intro still carries render.py's silent placeholder: re-render it with the real recording (render.py --intro-mehul/--intro-jayadratha, edit-plan-v2.md §1 step 3)." >&2
          fi
          voice_note="$voice_note (silent)"
        else
          # only a track with something to caption goes into the transcribe.py line: a silent one would make it stop with "heard no words"
          TRANSCRIBE_ARGS+=("$own_wav@$(awk -v s="$start" 'BEGIN { printf "%.3f", s }')")
        fi
      else
        echo "WARNING: beat $id (${NAMES[$i]}) has no audio track, so there is no voice or question from the clip itself." >&2
        if [ "$id" = "3" ] || [ "$id" = "3b" ]; then
          echo "         Re-render the intro scene with the real recording (render.py --intro-mehul/--intro-jayadratha, edit-plan-v2.md §1 step 3)." >&2
        else
          echo "         The footage scripts record video only; add the question to the clip, or record it into this beat's voice file." >&2
        fi
        voice_note="$voice_note (clip has no audio)"
      fi
    fi
    if [ "$id" = "3" ] || [ "$id" = "3b" ]; then
      MUTE_MUSIC_WINDOWS+=("$start|$(awk -v s="$start" -v d="$dur" 'BEGIN { printf "%.3f", s + d }')")
    fi
    printf '  %-4s %-26s %9.3f %8.3f %6s  %s\n' "$id" "${NAMES[$i]}" "$start" "$dur" "${PLANS[$i]}" "$voice_note" >> "$STARTS_FILE"
    if [ "${PLANS[$i]}" != "0" ] && awk -v d="$dur" -v p="${PLANS[$i]}" 'BEGIN { x = d - p; if (x < 0) x = -x; exit !(x > 1.0) }'; then
      echo "WARNING: beat $id (${NAMES[$i]}) is $(awk -v d="$dur" 'BEGIN { printf "%.1f", d }') s long, the plan says ${PLANS[$i]} s: check its in/out against the real clip." >&2
    fi
    start="$(awk -v s="$start" -v d="$dur" 'BEGIN { printf "%.6f", s + d }')"
  done
  {
    echo ""
    echo "# transcribe.py arguments (each WAV@START is where that beat's voice, or its clip's own audio, starts in this cut):"
    if [ "${#TRANSCRIBE_ARGS[@]}" -gt 0 ]; then printf '%q ' "${TRANSCRIBE_ARGS[@]}"; fi
    echo
  } >> "$STARTS_FILE"
  echo "Beat starts (measured), written to $STARTS_FILE:"
  sed -n '1,/^$/p' "$STARTS_FILE"
  if [ "${#no_voice[@]}" -gt 0 ]; then
    echo "No voice file for beat(s): ${no_voice[*]} (they play silent; video-script-v2.md says beat 14 may be silent)."
  fi
  if [ ! -d "$VO_DIR" ]; then
    echo "WARNING: the voice folder $VO_DIR does not exist (set VO_DIR; the default is <work_dir>/vo): every beat without its own audio plays silent." >&2
  fi
  if awk -v t="$TOTAL_S" 'BEGIN { exit !(t < 180) }'; then
    echo "WARNING: this cut is $(awk -v t="$TOTAL_S" 'BEGIN { printf "%d:%02d", t / 60, t % 60 }'), under 3:00: the form asks for 3 to 4 minutes (target 3:30 to 3:50). Add product footage (edit-plan-v2.md §6, docs/HANDOFF.md §4.3), unless Hack2skill support says otherwise." >&2
  fi

  total_fmt="$(awk -v t="$TOTAL_S" 'BEGIN { printf "%.3f", t }')"
  if [ "$n" -eq 0 ]; then
    echo "WARNING: no voice and no clip audio at all: the video will be silent." >&2
    ffmpeg -y -loglevel error -f lavfi -i "anullsrc=r=48000:cl=mono" -t "$total_fmt" -c:a pcm_s16le "$VOICE_TIMELINE"
  else
    ffmpeg -y -loglevel error "${inputs[@]}" \
      -filter_complex "${filt}${labels}amix=inputs=${n}:normalize=0:duration=longest:dropout_transition=0,apad=whole_dur=${total_fmt},atrim=end=${total_fmt}[aout]" \
      -map "[aout]" -c:a pcm_s16le -ar 48000 -ac 1 "$VOICE_TIMELINE"
  fi
  VO_PATH="$VOICE_TIMELINE"
fi

# ---------------------------------------------------------------------------
# 5. Mix audio: VO is the anchor track. If a music bed exists, duck it under
#    the VO with a sidechain compressor, and normalise the final mix to
#    -14 LUFS integrated. v2: the music bed is OFF (not ducked) over the intro voices.
# ---------------------------------------------------------------------------
MIXED_AUDIO="$TMP_DIR/mixed_audio.m4a"
if [ "$HAS_MUSIC" = "1" ]; then
  MUSIC_GAIN="volume=0.5"
  for w in "${MUTE_MUSIC_WINDOWS[@]:-}"; do
    [ -n "$w" ] || continue
    MUSIC_GAIN="$MUSIC_GAIN,volume=enable='between(t,${w%%|*},${w##*|})':volume=0"
  done
  ffmpeg -y -loglevel error \
    -i "$VO_PATH" -i "$MUSIC_PATH" \
    -filter_complex "\
      [1:a]${MUSIC_GAIN}[music]; \
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
#    the captions (if found) in the caption band under a 90 % picture (see
#    caption_band.sh). Without captions the picture stays full-frame.
# ---------------------------------------------------------------------------
FINAL_OUT="$WORK_DIR/final.mp4"
bash "$SCRIPT_DIR/caption_band.sh" "$ASSEMBLED_VIDEO" "$MIXED_AUDIO" "${SRT_PATH:--}" "$FINAL_OUT"

echo ""
echo "Done. Final export: $FINAL_OUT"
echo "Final runtime in seconds (the export gate ceiling is ${MAX_SECONDS} s):"
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$FINAL_OUT" 2>/dev/null || true

# ---------------------------------------------------------------------------
# 7. The export gate: the final file must be 16:9 and under the runtime ceiling; with captions also the picture
#    untouched and every caption inside the band (check_export.py, standard library + ffmpeg only). It ALWAYS runs:
#    without a captions file the band checks are reported as SKIPPED, the format and ceiling checks still run.
# ---------------------------------------------------------------------------
GATE_FAILED=0
PY="$(command -v python3 || command -v python || true)"
GATE_ARGS=("$FINAL_OUT" --clean "$ASSEMBLED_VIDEO" --max-seconds "$MAX_SECONDS")
if [ -n "$SRT_PATH" ]; then GATE_ARGS+=(--srt "$SRT_PATH"); fi
if [ -z "$PY" ]; then
  echo "WARNING: python3 not found, the export gate did NOT run, so this export is NOT approved. Run it by hand:" >&2
  { printf '  python3 %q' "$SCRIPT_DIR/check_export.py"; printf ' %q' "${GATE_ARGS[@]}"; echo; } >&2
  GATE_FAILED=1
else
  echo ""
  echo "Export gate (check_export.py):"
  "$PY" "$SCRIPT_DIR/check_export.py" "${GATE_ARGS[@]}" || GATE_FAILED=1
fi

echo ""
echo "Reminders before upload:"
if [ "$PLAN" = "v2" ]; then
  echo "  - Time the captions from beat-starts.txt (the wav@start arguments for transcribe.py), then re-run."
else
  echo "  - Re-sync captions.srt against the real vo.wav if you haven't already (see its header note)."
fi
echo "  - Verify every on-screen number against the actual recorded run (see the edit plan's open items)."
echo "  - Confirm the fictional-data banner and disclaimers are visible where required."
echo "  - Upload as Public on YouTube, not Unlisted."

if [ "$GATE_FAILED" != "0" ]; then
  echo "" >&2
  echo "EXPORT GATE FAILED (or could not run): do not upload $FINAL_OUT. See the FAIL lines above, or the warning that python was not found." >&2
  exit 2
fi
