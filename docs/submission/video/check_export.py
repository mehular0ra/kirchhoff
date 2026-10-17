#!/usr/bin/env python3
"""check_export.py: the gate for the final video export (issue #25). Standard library plus ffmpeg/ffprobe only.

    check_export.py <final.mp4> --clean <assembled_video.mp4> [--srt captions.srt] [--max-seconds 239]
    check_export.py --self-test

<final.mp4>   what caption_band.sh produced (assemble.sh runs this gate on it automatically)
--clean       the caption-free assembled picture the final was made from (.assemble_tmp/assembled_video.mp4)
--srt         the captions. WITHOUT it the format and 16:9 checks still run and the band checks are reported as SKIPPED (they need the
              cue times), so an export without captions is never waved through unchecked
--max-seconds the runtime ceiling (default 180, the v1 plan; the v2 cut uses 239: assemble.sh passes it, and run alone you must too)

Exit code 0 = every check passed, 1 = a check failed, 2 = it could not run (missing tool or file).

What it proves, from the final file's own frames (nothing is read from the build's bookkeeping):
  format    1920x1080, square pixels, 16:9, h264 yuv420p, the same frame rate as the clean picture, one audio track, shorter
            than 3:00, audio as long as the picture, as long as the clean picture
  picture   the 90 % picture (1728x972 at x=96,y=0) is the clean picture scaled the same way: SSIM against it, and no run of
            frames where it differs (a caption or a tag drawn over the app would show up here)
  gutters   the 96 px strips left and right of the picture are black
  captions  at the middle of every cue the band shows readable white text that sits inside the band and inside the side margins
  gaps      between cues (longer than 0.6 s) the band is empty
Geometry and the thresholds below are shared with caption_band.sh; --self-test builds a bad (old overlay style) and a good
(band) export and fails if the gate does not tell them apart, which also catches the two scripts drifting apart.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_W, OUT_H = 1920, 1080
PIC_W, PIC_H, PIC_X = 1728, 972, 96            # keep in sync with caption_band.sh
BAND_H = OUT_H - PIC_H                          # 108
MAX_SECONDS = 180.0
SSIM_MEAN_MIN = 0.985
SSIM_FRAME_MIN = 0.97                           # a frame below this counts as "the picture differs"
SSIM_RUN_FRAMES = 8                             # a run this long (0.27 s at 30 fps) fails; single cut frames are tolerated
BRIGHT = 200                                    # a text pixel (gray8)
MIN_TEXT_PIXELS = 120                           # fewer bright pixels than this is not readable text
GUTTER_MAX = 24                                 # gray8 level that still counts as black
GAP_MIN_S = 0.6                                 # only gaps at least this long are checked for an empty band
MIN_CUE_S = 0.1                                 # shorter cues are draft notes (the SRT's first cue), not captions


class ToolError(Exception):
    pass


def run(cmd, cwd=None, binary=False):
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=not binary)
    except FileNotFoundError:
        raise ToolError(f"{cmd[0]} is not installed or not on PATH")


def need(cmd, cwd=None, binary=False):
    r = run(cmd, cwd=cwd, binary=binary)
    if r.returncode != 0:
        err = r.stderr.decode("utf-8", "replace") if binary else r.stderr
        raise ToolError(f"{' '.join(map(str, cmd[:3]))} failed: {err.strip()[-300:]}")
    return r


def probe(path):
    r = need(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)])
    return json.loads(r.stdout)


def parse_srt(path):
    """-> [(start, end, text)] for cues of at least MIN_CUE_S."""
    src = Path(path).read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    cues = []
    for block in re.split(r"\n\s*\n", src.strip()):
        lines = block.split("\n")
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        m = re.match(r"\s*(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", lines[1])
        if not m:
            continue
        h1, m1, s1, f1, h2, m2, s2, f2 = m.groups()
        a = int(h1) * 3600 + int(m1) * 60 + int(s1) + int(f1.ljust(3, "0")[:3]) / 1000
        b = int(h2) * 3600 + int(m2) * 60 + int(s2) + int(f2.ljust(3, "0")[:3]) / 1000
        if b - a >= MIN_CUE_S:
            cues.append((a, b, " ".join(lines[2:])))
    return cues


def gray_crop(video, t, x, y, w, h):
    """One frame at time t, cropped, as w*h gray8 bytes."""
    r = need(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
              "-vf", f"crop={w}:{h}:{x}:{y}", "-f", "rawvideo", "-pix_fmt", "gray", "-"], binary=True)
    data = r.stdout
    if len(data) != w * h:
        raise ToolError(f"no frame at {t:.2f}s in {video}")
    return data


def text_box(data, w, h, level=BRIGHT):
    """-> (count of bright pixels, (left, top, right, bottom) of them or None)."""
    count, left, top, right, bottom = 0, w, h, -1, -1
    for yy in range(h):
        row = data[yy * w:(yy + 1) * w]
        if max(row) < level:
            continue
        xs = [i for i, b in enumerate(row) if b >= level]
        count += len(xs)
        left, right = min(left, xs[0]), max(right, xs[-1])
        top, bottom = min(top, yy), max(bottom, yy)
    return count, ((left, top, right, bottom) if count else None)


# ---------------------------------------------------------------------------------------------------- the checks
def check_format(final, clean, max_seconds=MAX_SECONDS, probe_fn=None):
    probe_fn = probe_fn or probe
    f, c = probe_fn(final), probe_fn(clean)
    fv = next((s for s in f["streams"] if s["codec_type"] == "video"), None)
    cv = next((s for s in c["streams"] if s["codec_type"] == "video"), None)
    fa = [s for s in f["streams"] if s["codec_type"] == "audio"]
    if not fv or not cv:
        return False, "no video stream"
    problems = []
    if (fv["width"], fv["height"]) != (OUT_W, OUT_H):
        problems.append(f"size {fv['width']}x{fv['height']} (need {OUT_W}x{OUT_H})")
    sar, dar = fv.get("sample_aspect_ratio"), fv.get("display_aspect_ratio")      # ffprobe omits them when unset: that is a failure, not a pass
    if sar != "1:1" or dar != "16:9":
        problems.append(f"SAR {sar or 'missing'} DAR {dar or 'missing'} (need 1:1 and 16:9)")
    if fv["codec_name"] != "h264" or fv.get("pix_fmt") != "yuv420p":
        problems.append(f"{fv['codec_name']} {fv.get('pix_fmt')} (need h264 yuv420p)")
    if fv["r_frame_rate"] != cv["r_frame_rate"]:
        problems.append(f"frame rate {fv['r_frame_rate']} differs from the clean picture's {cv['r_frame_rate']}")
    if len(fa) != 1:
        problems.append(f"{len(fa)} audio tracks (need 1)")
    d, dc = float(f["format"]["duration"]), float(c["format"]["duration"])
    if not d < max_seconds:
        problems.append(f"runtime {d:.1f}s is not under {max_seconds:.0f}s")
    if abs(d - dc) > 0.15:
        problems.append(f"runtime {d:.2f}s differs from the clean picture's {dc:.2f}s")
    if fa and abs(float(fa[0].get("duration", d)) - d) > 0.15:
        problems.append(f"audio {float(fa[0]['duration']):.2f}s differs from the picture's {d:.2f}s")
    if problems:
        return False, "; ".join(problems)
    return True, f"{OUT_W}x{OUT_H} 16:9, square pixels, {fv['codec_name']} {fv['pix_fmt']}, {d:.2f}s, 1 audio track"


def check_picture(final, clean):
    with tempfile.TemporaryDirectory() as tmp:
        lavfi = (f"[0:v]crop={PIC_W}:{PIC_H}:{PIC_X}:0,setsar=1[a];"
                 f"[1:v]scale={PIC_W}:{PIC_H}:flags=lanczos,setsar=1[b];[a][b]ssim=stats_file=ssim.log")
        need(["ffmpeg", "-nostdin", "-v", "error", "-i", str(Path(final).resolve()), "-i", str(Path(clean).resolve()),
              "-lavfi", lavfi, "-f", "null", "-"], cwd=tmp)
        vals = [float(m.group(1)) for m in re.finditer(r"All:([0-9.]+)", (Path(tmp) / "ssim.log").read_text())]
    if not vals:
        return False, "the SSIM comparison produced no frames"
    mean = sum(vals) / len(vals)
    run_len = worst_run = 0
    for v in vals:
        run_len = run_len + 1 if v < SSIM_FRAME_MIN else 0
        worst_run = max(worst_run, run_len)
    ok = mean >= SSIM_MEAN_MIN and worst_run < SSIM_RUN_FRAMES
    return ok, (f"SSIM against the clean picture: mean {mean:.4f} (need >= {SSIM_MEAN_MIN}), lowest {min(vals):.3f}, longest run of frames "
                f"below {SSIM_FRAME_MIN}: {worst_run} (limit {SSIM_RUN_FRAMES - 1}) over {len(vals)} frames")


def sample_times(cues, duration, n=8):
    mids = [(a + b) / 2 for a, b, _ in cues]
    step = max(1, len(mids) // n)
    return sorted(set([round(t, 2) for t in mids[::step]] + [round(duration * 0.5, 2)]))


def check_gutters(final, cues, duration):
    bad = []
    for t in sample_times(cues, duration):
        for x in (0, PIC_X + PIC_W):
            data = gray_crop(final, t, x, 0, PIC_X, PIC_H)
            if max(data) > GUTTER_MAX:
                bad.append((t, "left" if x == 0 else "right", max(data)))
    if bad:
        return False, f"gutters not black at {bad[:4]}"
    return True, f"the left and right {PIC_X}px strips are black at the sampled times"


def check_captions(final, cues):
    bad = []
    for a, b, text in cues:
        if b - a < 0.3:
            continue
        t = (a + b) / 2
        data = gray_crop(final, t, 0, PIC_H, OUT_W, BAND_H)
        n, box = text_box(data, OUT_W, BAND_H)
        if n < MIN_TEXT_PIXELS:
            bad.append((round(t, 1), f"no readable text ({n} bright px)", text[:40]))
            continue
        left, top, right, bottom = box
        if top < 2 or bottom > BAND_H - 4 or left < PIC_X - 8 or right > OUT_W - PIC_X + 8:
            bad.append((round(t, 1), f"text box {box} leaves the band or its margins", text[:40]))
    if bad:
        return False, f"{len(bad)} of {len(cues)} cues fail: {bad[:3]}"
    return True, f"all {len(cues)} cues show readable text inside the band and its margins"


def check_gaps(final, cues):
    mids = [(cues[i][1] + cues[i + 1][0]) / 2 for i in range(len(cues) - 1) if cues[i + 1][0] - cues[i][1] >= GAP_MIN_S]
    bad = []
    for t in mids[:12]:
        n, _ = text_box(gray_crop(final, t, 0, PIC_H, OUT_W, BAND_H), OUT_W, BAND_H)
        if n >= 40:
            bad.append((round(t, 1), n))
    if bad:
        return False, f"stray text in the band between cues at {bad[:4]}"
    return True, f"the band is empty in {min(len(mids), 12)} sampled gaps"


def run_checks(final, clean, srt=None, max_seconds=MAX_SECONDS):
    final, clean = Path(final), Path(clean)
    results = [("format", *check_format(final, clean, max_seconds))]
    if srt is None:
        skipped = "SKIPPED: no captions file given, the band checks need the cue times"
        return results + [(name, True, skipped) for name in ("picture", "gutters", "captions", "gaps")]
    cues = parse_srt(srt)
    duration = float(probe(final)["format"]["duration"])
    if results[0][1]:
        results += [("picture", *check_picture(final, clean)), ("gutters", *check_gutters(final, cues, duration)),
                    ("captions", *check_captions(final, cues)), ("gaps", *check_gaps(final, cues))]
    return results


def report(results):
    failed, skipped = 0, 0
    for name, ok, detail in results:
        skip = ok and detail.startswith("SKIPPED")
        failed += 0 if ok else 1
        skipped += 1 if skip else 0
        print(f"{'SKIP' if skip else 'PASS' if ok else 'FAIL'}  {name:9} {detail}")
    print(f"-- {len(results) - failed - skipped} passed, {failed} failed, {skipped} skipped")
    return failed


# ---------------------------------------------------------------------------------------------------- self-test
LONG_LINE = "This caption is deliberately long so that it needs two lines inside the band, and it still must not touch the picture above it."
# Cue 1 mirrors captions.srt's first cue: a 10 ms draft note that overlaps the first real caption. libass stacks a later cue ABOVE an
# overlapping one and keeps it there for its whole duration, so burning the note in floats the first caption over the picture;
# caption_band.sh therefore drops cues shorter than 0.1 s (the gate ignores them too).
DRAFT_NOTE = ("[NOTE - DRAFT TIMINGS, RE-SYNC BEFORE FINAL: cue in/out points in this file follow the script's beat timings, split proportionally by "
              "word count inside each beat. They are NOT timed against the real voiceover. Re-sync every cue below before burning in or exporting. "
              "This cue is 10ms, effectively invisible; delete it once re-sync is done.]")
SELF_SRT = f"""1
00:00:00,000 --> 00:00:00,010
{DRAFT_NOTE}

2
00:00:00,000 --> 00:00:01,100
Short caption on one line.

3
00:00:01,900 --> 00:00:03,100
{LONG_LINE}

4
00:00:03,900 --> 00:00:04,700
Last one.
"""
OVERFLOW_SRT = SELF_SRT.replace(LONG_LINE, ("This caption is far too long for any two line band, and it keeps going on and on so that it wraps to a third and "
                                            "a fourth line and ends up on top of the picture, which is the exact thing the gate exists to catch before "
                                            "the video is uploaded to the world. ") * 2)


def self_test():
    for tool in ("ffmpeg", "ffprobe", "bash"):
        if shutil.which(tool) is None:
            print(f"self-test needs {tool} on PATH", file=sys.stderr)
            return 2
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        (t / "caps.srt").write_text(SELF_SRT, encoding="utf-8")
        (t / "caps_overflow.srt").write_text(OVERFLOW_SRT, encoding="utf-8")
        need(["ffmpeg", "-nostdin", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30:duration=5",
              "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", "clean.mp4"], cwd=tmp)
        need(["ffmpeg", "-nostdin", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
              "-c:a", "aac", "-b:a", "192k", "audio.m4a"], cwd=tmp)
        env = {**os.environ, "FINAL_PRESET": "ultrafast"}
        for out, srt in (("good.mp4", "caps.srt"), ("overflow.mp4", "caps_overflow.srt")):
            r = subprocess.run([shutil.which("bash"), str(HERE / "caption_band.sh"), "clean.mp4", "audio.m4a", srt, out],
                               cwd=tmp, env=env, capture_output=True, text=True)
            if r.returncode != 0:
                print(f"caption_band.sh failed for {out}: {r.stderr.strip()[-300:]}", file=sys.stderr)
                return 2
        # the OLD export: captions burned onto the full-frame picture with libass's default style (what assemble.sh did before)
        need(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", "clean.mp4", "-i", "audio.m4a", "-vf", "subtitles=caps.srt", "-map", "0:v",
              "-map", "1:a", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
              "-shortest", "old.mp4"], cwd=tmp)

        def decoded_audio(p):
            return need(["ffmpeg", "-nostdin", "-v", "error", "-i", str(t / p), "-vn", "-f", "s16le", "-"], binary=True).stdout

        scenarios = (("good (band layout)", "good.mp4", "caps.srt", True),
                     ("old (captions over the full-frame picture)", "old.mp4", "caps.srt", False),
                     ("overflow (a caption too long for the band)", "overflow.mp4", "caps_overflow.srt", False))
        for label, video, srt, expect_pass in scenarios:
            print(f"\n== {label}: the gate must {'PASS' if expect_pass else 'FAIL'}")
            failed = report(run_checks(t / video, t / "clean.mp4", t / srt))
            if (failed == 0) != expect_pass:
                failures.append(label)
        print("\n== follow-up 1 (#44 review): an export WITHOUT captions still gets the format and 16:9 checks")
        r = subprocess.run([shutil.which("bash"), str(HERE / "caption_band.sh"), "clean.mp4", "audio.m4a", "-", "nocap.mp4"], cwd=tmp, env=env, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"caption_band.sh failed for nocap.mp4: {r.stderr.strip()[-300:]}", file=sys.stderr)
            return 2
        res = run_checks(t / "nocap.mp4", t / "clean.mp4", None)
        report(res)
        if not (res[0][1] and res[0][0] == "format" and all(d.startswith("SKIPPED") for _, _, d in res[1:])):
            failures.append("no-captions export is not format-checked")
        wrong = run_checks(t / "nocap.mp4", t / "clean.mp4", None, max_seconds=4.0)      # 5 s video against a 4 s ceiling: the runtime ceiling is enforced without captions too
        if wrong[0][1]:
            failures.append("the runtime ceiling is not enforced without captions")
        print("\n== follow-up 2 (#44 review): a missing display aspect ratio fails the format check (no default to 16:9)")
        base = probe(t / "good.mp4")
        fake = lambda missing: (lambda p: {**base, "streams": [({k: v for k, v in s.items() if not (missing and k == "display_aspect_ratio")} if s["codec_type"] == "video" else s) for s in base["streams"]]})
        ok_dar, _ = check_format(t / "good.mp4", t / "clean.mp4", probe_fn=fake(False))
        bad_dar, why = check_format(t / "good.mp4", t / "clean.mp4", probe_fn=fake(True))
        print(f"{'PASS' if ok_dar and not bad_dar else 'FAIL'}  dar      with DAR present: {ok_dar}; with DAR removed: {bad_dar} ({why[:60]})")
        if not (ok_dar and not bad_dar):
            failures.append("missing DAR is not a failure")
        print("\n== pass-to-pass: the band layout must not change the audio or the length")
        same_audio = decoded_audio("good.mp4") == decoded_audio("old.mp4")
        durs = [float(probe(t / p)["format"]["duration"]) for p in ("good.mp4", "old.mp4")]
        print(f"{'PASS' if same_audio else 'FAIL'}  audio    decoded samples identical to the old export")
        print(f"{'PASS' if abs(durs[0] - durs[1]) < 0.05 else 'FAIL'}  length   {durs[0]:.3f}s vs {durs[1]:.3f}s")
        if not same_audio:
            failures.append("audio changed")
        if abs(durs[0] - durs[1]) >= 0.05:
            failures.append("length changed")
    print("\nSELF-TEST " + ("FAILED: " + ", ".join(failures) if failures else "PASSED: the gate passes the band export and fails the old and the overflowing ones"))
    return 1 if failures else 0


def main():
    ap = argparse.ArgumentParser(description="Gate for the final Kirchhoff video export.")
    ap.add_argument("final", nargs="?")
    ap.add_argument("--clean")
    ap.add_argument("--srt", default=None)
    ap.add_argument("--max-seconds", type=float, default=MAX_SECONDS)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    try:
        if a.self_test:
            return self_test()
        if not a.final or not a.clean:
            ap.error("need <final.mp4> and --clean <assembled_video.mp4> (or --self-test)")
        for p in [a.final, a.clean] + ([a.srt] if a.srt else []):
            if not Path(p).is_file():
                print(f"not found: {p}", file=sys.stderr)
                return 2
        return 1 if report(run_checks(a.final, a.clean, a.srt, a.max_seconds)) else 0
    except ToolError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
