#!/usr/bin/env python3
"""assemble_selftest.py: tests for assemble.sh (issue #25). Standard library plus ffmpeg/ffprobe/bash only.

    python3 assemble_selftest.py [--skip-v1] [--skip-v2] [--cases ABCDEF] [--baseline-ref <sha>]

Everything is built from synthetic clips whose content says which beat they are: a solid grey per beat (so the order and the trims are read
back from the final picture), a sine tone per voice file and per clip-with-sound (so where every voice starts is read back from the final
sound). Nothing is rendered or recorded, nothing leaves the temp folder.

v1  the original cut must not change: the same 13 clips and vo.wav are assembled by the COMMITTED assemble.sh (--baseline-ref) and by this
    working tree's; the pictures (frame by frame), the mixed sound and the final video and sound must be identical, and the gate must give the same
    verdicts. Intended difference, listed and checked separately: with no captions the old script skipped the whole gate, the new one runs it.
v2  PLAN=v2 on its own: the beat order and trims, every beat's start measured and written to beat-starts.txt, each voice file where its beat starts,
    the intro voice and the in-clip sound, the music bed off over the intro, the "time-compressed xN" label, the runtime ceiling, the picture and
    sound the same length, and the ways it must refuse (missing clip, two voice files for one beat, unknown plan).
"""
import argparse
import array
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASH = shutil.which("bash")
FINAL_ENV = {"FINAL_PRESET": "ultrafast", "FINAL_CRF": "20"}
results = []


def posix(p):
    return Path(p).as_posix()


def ff(*args):
    r = subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", *map(str, args)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg {' '.join(map(str, args))[:200]} failed: {r.stderr.strip()[-300:]}")


def probe_s(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True)
    return float(r.stdout.strip())


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"   {detail}" if detail else ""), flush=True)
    return ok


# ---------------------------------------------------------------------------------------------------------------- synthetic media
def grey(n):
    """Beat n's grey level: 36 + 6 n, so 22 beats stay distinct, dark enough that the white label is the only bright thing."""
    return 36 + 6 * n


def hexgrey(g):
    return f"0x{g:02X}{g:02X}{g:02X}"


def solid(path, secs, g, hz=None):
    args = ["-f", "lavfi", "-i", f"color=c={hexgrey(g)}:s=320x180:r=30:d={secs}"]
    if hz == "silent":
        args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono"]
    elif hz:
        args += ["-f", "lavfi", "-i", f"sine=frequency={hz}:sample_rate=48000:duration={secs}"]
    args += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"]
    args += ["-c:a", "aac", "-b:a", "96k"] if hz else ["-an"]
    if hz == "silent":
        args += ["-shortest"]
    ff(*args, path)


def footage(path, body, g, hz=None, hue=None):
    """A 2 s bright head handle, the body, a 2 s dark tail handle (the #25 clip layout): a wrong in/out shows as the wrong grey.
    With `hue` the body is a moving test pattern instead of a solid grey: a solid frame encodes the same at any quality setting, so only
    textured clips can show a change of encoder settings (the v1 pass-to-pass check needs that)."""
    body_src = f"color=c={hexgrey(g)}:s=320x180:r=30:d={body}" if hue is None else f"testsrc2=s=320x180:r=30:d={body},hue=h={hue}"
    fc = (f"color=c=0xFAFAFA:s=320x180:r=30:d=2[a];{body_src}[b];"
          "color=c=0x050505:s=320x180:r=30:d=2[c];[a][b][c]concat=n=3:v=1:a=0[v]")
    args = []
    if hz:
        args += ["-f", "lavfi", "-i", f"sine=frequency={hz}:sample_rate=48000:duration={body + 4}"]
    args += ["-filter_complex", fc, "-map", "[v]"] + (["-map", "0:a", "-c:a", "aac", "-b:a", "96k"] if hz else ["-an"])
    ff(*args, "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", path)


def tone_wav(path, hz, secs):
    ff("-f", "lavfi", "-i", f"sine=frequency={hz}:sample_rate=48000:duration={secs}", "-af", "volume=0.5", "-ac", "1", "-c:a", "pcm_s16le", path)


# ---------------------------------------------------------------------------------------------------------------- reading the result back
def grey_at(video, t, box=(860, 500, 200, 100)):
    x, y, w, h = box
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1", "-vf",
                        f"crop={w}:{h}:{x}:{y},scale=1:1:flags=area", "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True)
    return r.stdout[0] if r.stdout else -1


def bright_pixels(video, t, box, level=200):
    x, y, w, h = box
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1", "-vf", f"crop={w}:{h}:{x}:{y}",
                        "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True)
    return sum(1 for b in r.stdout if b > level), r.stdout


RATE = 16000


def pcm(video):
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", str(RATE), "-f", "s16le", "-"], capture_output=True)
    a = array.array("h")
    a.frombytes(r.stdout)
    return a


def power(samples, hz):
    """Goertzel power of one frequency in a window."""
    n = len(samples)
    k = 2 * math.cos(2 * math.pi * hz / RATE)
    s1 = s2 = 0.0
    for x in samples:
        s0 = x + k * s1 - s2
        s2, s1 = s1, s0
    return (s1 * s1 + s2 * s2 - k * s1 * s2) / (n * n)


CONTROL = (777, 1555, 2999, 5111, 7000)      # frequencies nothing in the test plays: the noise floor


def present(audio, t0, hz, span=0.5):
    """How many times louder than the noise floor `hz` is in [t0, t0+span]."""
    w = audio[int(t0 * RATE):int((t0 + span) * RATE)]
    if len(w) < RATE * span * 0.9:
        return 0.0
    floor = sum(power(w, c) for c in CONTROL) / len(CONTROL) + 1e-9
    return power(w, hz) / floor


# ---------------------------------------------------------------------------------------------------------------- running the script
def run_assemble(script, work, env_extra=None, args=(), expect_exit=None):
    env = dict(os.environ, **FINAL_ENV, **(env_extra or {}))
    r = subprocess.run([BASH, posix(script), posix(work), *args], capture_output=True, text=True, env=env, encoding="utf-8", errors="replace")
    if expect_exit is not None and r.returncode != expect_exit:
        print(f"--- {script.name} exit {r.returncode} (expected {expect_exit}); output tail:\n{(r.stdout + r.stderr)[-1500:]}", file=sys.stderr)
    return r


def gate_verdicts(text):
    """[(PASS|FAIL|SKIP, name)] from the gate's report lines."""
    return [(m.group(1), m.group(2)) for m in re.finditer(r"^(PASS|FAIL|SKIP)\s+(\w+)", text, re.M)]


# ================================================================================================================ v2
# The test's OWN copy of edit-plan-v2.md's beat table: id, seconds in the cut (footage = the body between the handles), has a voice file.
V2 = [("1", 7, True), ("2", 3, True), ("3", 4, False), ("3b", 3, False), ("4", 3, True), ("5", 3, True), ("5b", 14, True), ("6", 13, True), ("7", 3, True),
      ("8", 10, True), ("9", 3, True), ("10", 15, True), ("10b", 12, True), ("11", 10, True), ("12", 12, True), ("13", 3, True), ("14", 6, False),
      ("15", 3, True), ("15b", 11, True), ("16", 3, True), ("16b", 3, True), ("17", 3, True)]
FOOTAGE = {"1": "v01-cold-open", "5b": "v12-inbox-triage", "6": "v04-tender-in", "8": "v05-agents-at-work", "10": "v06-checker", "10b": "v13-trust-quote",
           "11": "v07-erp-swap", "12": "v08-what-if-voice", "14": "v09-sign-off", "15b": "v11-grid-solar"}
SCENES = {"2": "s1-title", "3": "s1b-intro-mehul", "3b": "s1c-intro-jayadratha", "4": "s2-problem", "5": "s3-requirements-in", "7": "s4-agents", "9": "s5-checks",
          "13": "s6-sign", "15": "s7-connectors", "16": "s8-google-cloud", "16b": "s10-numbers", "17": "s9-end"}
VOICE_NAME = {"1": "cold-open", "2": "title", "4": "problem", "5": "requirements", "5b": "inbox", "6": "tender", "7": "agents", "8": "agents-at-work", "9": "checks",
              "10": "checker", "10b": "trust", "11": "erp", "12": "what-if", "13": "sign", "15": "connectors", "15b": "platform", "16": "cloud", "16b": "numbers", "17": "end"}
VO_NO = {"5b": 18, "10b": 19, "15b": 20, "16b": 21}   # the NN of bNN-<name>.wav where it is not the beat's own number: the extra beats of the longer cut
INTRO_HZ, JD_HZ, V08_HZ, MUSIC_HZ = 2800, 3400, 4200, 6200
LABEL_STRIP = (780, 56, 360, 44)             # the top-centre strip of the 1920 x 1080 picture where the label is burned in


def vo_no(i):
    return VO_NO.get(i) or int(i)


def vo_hz(i):
    return 400 + 100 * vo_no(i)


def n_of(i):
    return {"3b": 18, "5b": 19, "10b": 20, "15b": 21, "16b": 22}.get(i) or int(i)


def make_v2_workspace(root, v08_audio=True, comp_body=40, intro_silent=False):
    work, scenes, vo = root / "work", root / "scenes", root / "work" / "vo"
    for d in (work, scenes, vo):
        d.mkdir(parents=True, exist_ok=True)
    for i, secs, has_vo in V2:
        g = grey(n_of(i))
        if i in FOOTAGE:
            body = comp_body if i == "8" else secs
            footage(work / f"{FOOTAGE[i]}.mp4", body, g, V08_HZ if (i == "12" and v08_audio) else None)
        else:
            solid(scenes / f"{SCENES[i]}.mp4", secs, g, {"3": "silent" if intro_silent else INTRO_HZ, "3b": JD_HZ}.get(i))
        if has_vo:
            tone_wav(vo / f"b{vo_no(i):02d}-{VOICE_NAME[i]}.wav", vo_hz(i), max(1.8, secs * 0.6))
    return work, scenes


def expected_starts(with_jd):
    t, out = 0.0, {}
    for i, secs, _ in V2:
        if i == "3b" and not with_jd:
            continue
        out[i] = (t, secs)
        t += secs
    return out, t


def write_srt(path, total):
    lines, k, t = [], 1, 1.0
    f = lambda s: f"00:{int(s // 60):02d}:{int(s) % 60:02d},{int((s % 1) * 1000):03d}"
    while t + 3.5 < total - 2:
        lines += [str(k), f"{f(t)} --> {f(t + 3.5)}", f"Caption number {k}", ""]
        k, t = k + 1, t + 6.0
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def parse_starts(text):
    rows = {}
    for m in re.finditer(r"^\s{2}(\S+)\s+(\S+)\s+([\d.]+)\s+([\d.]+)\s+(\d+)\s+(.*)$", text, re.M):
        rows[m.group(1)] = (float(m.group(3)), float(m.group(4)), m.group(6).strip())
    return rows


def verify_v2(tag, work, run, with_jd, label_n, music=False, own_audio=True):
    """Everything a v2 run must have done, read back from its files."""
    final, clean = work / "final.mp4", work / ".assemble_tmp" / "assembled_video.mp4"
    exp, total = expected_starts(with_jd)
    check(f"{tag}: the script and the gate exit 0", run.returncode == 0, f"exit {run.returncode}")
    d_final, d_clean = probe_s(final), probe_s(clean)
    check(f"{tag}: the cut is the sum of the beats ({total:.0f} s)", abs(d_clean - total) < 0.15, f"assembled {d_clean:.3f} s")
    check(f"{tag}: sound and picture are the same length (the final is not cut short)", abs(d_final - d_clean) < 1 / 30 + 0.02, f"final {d_final:.3f} s, picture {d_clean:.3f} s")
    txt = (work / "beat-starts.txt").read_text(encoding="utf-8")
    starts = parse_starts(txt)
    bad = [i for i, (s, _) in exp.items() if i not in starts or abs(starts[i][0] - s) > 0.1]
    check(f"{tag}: beat-starts.txt lists every beat at its measured start", not bad and len(starts) == len(exp), f"{len(starts)} beats, off: {bad}")
    got = [(a.rsplit("@", 1)[0].split("/")[-1], float(a.rsplit("@", 1)[1])) for a in shlex.split(txt.strip().splitlines()[-1])]
    own = {"3": "own_3.wav"}  # the clips' own audio, extracted by the script: it is captioned too, in beat order after the beat's voice file
    if with_jd:
        own["3b"] = "own_3b.wav"
    if own_audio:
        own["12"] = "own_12.wav"
    want = []
    for i, _, v in V2:
        if i not in exp:
            continue
        if v:
            want.append((f"b{vo_no(i):02d}-{VOICE_NAME[i]}.wav", exp[i][0]))
        if i in own:
            want.append((own[i], exp[i][0]))
    ok = len(got) == len(want) and all(g[0] == w[0] and abs(g[1] - w[1]) < 0.1 for g, w in zip(got, want))
    check(f"{tag}: the transcribe.py arguments are wav@start for every voice file AND every clip's own audio (the intros, the in-clip question)", ok, f"{len(got)} of {len(want)}")
    wrong = []
    for i, (s, secs) in exp.items():
        g = grey(n_of(i))
        for t in (s + 0.2, s + secs - 0.2):
            seen = grey_at(clean, t)
            if abs(seen - g) > 4:
                wrong.append((i, round(t, 1), seen, g))
    check(f"{tag}: every beat is the right clip, trimmed between its handles (first and last frame)", not wrong, str(wrong[:3]))
    audio = pcm(final)
    miss, leak = [], []
    voiced = [i for i, _, v in V2 if v and i in exp]
    for i in voiced:
        s = exp[i][0]
        if present(audio, s + 0.4, vo_hz(i)) < 50:
            miss.append(i)
        if any(present(audio, s + 0.4, vo_hz(j)) > 8 for j in voiced if j != i):
            leak.append(i)
    check(f"{tag}: each voice file starts with its own beat", not miss, f"missing: {miss}")
    check(f"{tag}: no voice file plays in another beat", not leak, f"leaking: {leak}")
    check(f"{tag}: the intro voice from the scene clip is at the start of beat 3", present(audio, exp["3"][0] + 0.4, INTRO_HZ) > 50)
    if with_jd:
        check(f"{tag}: Jayadratha's intro voice is at the start of beat 3b", present(audio, exp["3b"][0] + 0.4, JD_HZ) > 50)
    if own_audio:
        check(f"{tag}: the sound of the in-clip question is in beat 12", present(audio, exp["12"][0] + 0.4, V08_HZ) > 50)
    if music:
        on = present(audio, exp["14"][0] + 1.0, MUSIC_HZ)
        off = max(present(audio, exp["3"][0] + 0.6, MUSIC_HZ), present(audio, exp["3b"][0] + 0.6, MUSIC_HZ) if with_jd else 0)
        check(f"{tag}: the music bed plays under the film but is OFF over the intro voices", on > 50 and off < 8, f"in beat 14 x{on:.0f}, over the intros x{off:.1f}")
    s8 = exp["8"][0]
    quiet = max(bright_pixels(clean, exp[i][0] + exp[i][1] / 2, LABEL_STRIP)[0] for i in ("7", "9"))
    if label_n:
        on_a, px_a = bright_pixels(clean, s8 + 2.0, LABEL_STRIP)
        on_b, px_b = bright_pixels(clean, s8 + 6.0, LABEL_STRIP)
        check(f"{tag}: beat 8 carries the 'time-compressed x{label_n}' label, the neighbours do not", on_a > 150 and on_b > 150 and quiet == 0,
              f"label {on_a}/{on_b} bright px, neighbours {quiet}")
        moved = sum(1 for a, b in zip(px_a, px_b) if abs(a - b) > 60)
        check(f"{tag}: the real-time clock in the label moves", moved > 40, f"{moved} px differ between 2 s and 6 s")
    return exp


def v2_tests(root, cases="ABCD"):
    print("\n== v2")
    root.mkdir(parents=True, exist_ok=True)
    music_wav = root / "music.mp3"
    ff("-f", "lavfi", "-i", f"sine=frequency={MUSIC_HZ}:sample_rate=48000:duration=200", "-c:a", "libmp3lame", "-b:a", "128k", music_wav)
    script = HERE / "assemble.sh"

    # A: the plain cut, captions, the speed factor measured from the clip (44 s clip -> (44 - 4) / 10 = 4)
    if "A" in cases:
        work, scenes = make_v2_workspace(root / "a")
        _, total = expected_starts(False)
        srt = root / "a" / "captions.srt"
        write_srt(srt, total)
        r = run_assemble(script, work, {"PLAN": "v2", "SCENES_DIR": posix(scenes), "CAPTIONS": posix(srt)}, expect_exit=0)
        check("A: the speed factor is measured from the clip and said so", "speed factor 4.0x MEASURED" in r.stdout + r.stderr)
        verify_v2("A", work, r, False, 4)
        g = gate_verdicts(r.stdout)
        check("A: the gate ran with the captions: format, picture, gutters, captions, gaps all PASS", [v for v, _ in g] == ["PASS"] * 5, str(g))
        check("A: a beat with no voice file (14) is reported, not an error", "No voice file for beat(s): 14" in r.stdout)
        check("A: voiced own audio (the intro, the in-clip question) is NOT flagged silent", "but it is silent" not in r.stderr, r.stderr[-300:])
        check("A: a cut under 3:00 is warned about (the form asks for 3 to 4 minutes), without failing", "under 3:00" in r.stderr and r.returncode == 0, r.stderr[-200:])
        check("A: with no MAX_SECONDS the v2 gate ceiling is 239 s (3:59: the form asks for 3 to 4 minutes)", "Runtime ceiling for the export gate: 239 s" in r.stdout, r.stdout[:300])

    # B: with Jayadratha's intro, music, an explicit speed factor, no captions, a clip with no sound in beat 12
    if "B" in cases:
        work, scenes = make_v2_workspace(root / "b", v08_audio=False)
        shutil.copy(music_wav, work / "music.mp3")
        r = run_assemble(script, work, {"PLAN": "v2", "SCENES_DIR": posix(scenes), "INCLUDE_JD_INTRO": "1", "CAPTIONS": posix(root / "none.srt")}, args=("2",), expect_exit=0)
        verify_v2("B", work, r, True, 2, music=True, own_audio=False)
        g = gate_verdicts(r.stdout)
        check("B: no captions: the gate STILL ran (format PASS, the band checks SKIP)", g[:1] == [("PASS", "format")] and all(v == "SKIP" for v, _ in g[1:]) and len(g) == 5, str(g))
        check("B: a clip with no sound in beat 12 is warned about, not silently mixed", "beat 12 (v08-what-if-voice.mp4) has no audio track" in r.stderr)

    # C: speed factor 1 means no label; a runtime ceiling the cut exceeds fails the gate with exit 2 (the test can fail)
    if "C" in cases:
        work, scenes = make_v2_workspace(root / "c")
        r = run_assemble(script, work, {"PLAN": "v2", "SCENES_DIR": posix(scenes), "CAPTIONS": posix(root / "none.srt"), "MAX_SECONDS": "60"}, args=("1",), expect_exit=2)
        check("C: an explicit MAX_SECONDS wins over the default", "Runtime ceiling for the export gate: 60 s" in r.stdout)
        check("C: a cut over the ceiling fails the gate and the script exits 2", r.returncode == 2 and re.search(r"^FAIL\s+format.*not under 60s", r.stdout, re.M) is not None,
              f"exit {r.returncode}")
        clean = work / ".assemble_tmp" / "assembled_video.mp4"
        exp, _ = expected_starts(False)
        none = max(bright_pixels(clean, exp["8"][0] + t, LABEL_STRIP)[0] for t in (2.0, 6.0))
        check("C: at a speed factor of 1 beat 8 has no label", none == 0, f"{none} bright px")

    # D: refusals (all before anything is encoded)
    if "D" in cases:
        work, scenes = make_v2_workspace(root / "d")
        (work / "v06-checker.mp4").unlink()
        r = run_assemble(script, work, {"PLAN": "v2", "SCENES_DIR": posix(scenes)})
        check("D: a missing footage clip stops the run and names it", r.returncode == 1 and "beat 10: clip not found" in r.stderr and "v06-checker.mp4" in r.stderr, f"exit {r.returncode}")
        r = run_assemble(script, work, {"PLAN": "v2", "SCENES_DIR": posix(root / "no-such-scenes")})
        missing_scenes = len(re.findall(r"clip not found", r.stderr))
        check("D: a missing scenes folder lists every missing scene in one go", r.returncode == 1 and missing_scenes >= 10, f"{missing_scenes} listed")
        shutil.copy(work / "vo" / "b04-problem.wav", work / "vo" / "b04-problem-take2.wav")
        r = run_assemble(script, work, {"PLAN": "v2", "SCENES_DIR": posix(scenes)})
        check("D: two voice files for one beat stop the run", r.returncode == 1 and "more than one voice file for beat 4" in r.stderr, f"exit {r.returncode}")
        r = run_assemble(script, work, {"PLAN": "v3"})
        check("D: an unknown PLAN is refused", r.returncode == 1 and "PLAN must be v1 or v2" in r.stderr)


    # E: an intro scene whose audio track is only silence (render.py's placeholder, before the real recording is put in) is warned about, not an error
    if "E" in cases:
        work, scenes = make_v2_workspace(root / "e", intro_silent=True)
        r = run_assemble(script, work, {"PLAN": "v2", "SCENES_DIR": posix(scenes), "CAPTIONS": posix(root / "none.srt")}, expect_exit=0)
        check("E: an intro with a silent audio track is warned about as the placeholder it is", "beat 3 " in r.stderr and "silent" in r.stderr and "render.py" in r.stderr, r.stderr[-300:])
        check("E: and the run still exits 0", r.returncode == 0)
        last = (work / "beat-starts.txt").read_text(encoding="utf-8").strip().splitlines()[-1]
        check("E: the silent intro is NOT in the printed transcribe.py line (it would stop transcribe.py), the voiced own audio still is",
              "own_3.wav" not in last and "own_12.wav" in last, last[:200])

    # F: a voice folder that does not exist is warned about (every voice beat would otherwise play silent with only a list of beat numbers as the signal)
    if "F" in cases:
        work, scenes = make_v2_workspace(root / "f")
        r = run_assemble(script, work, {"PLAN": "v2", "SCENES_DIR": posix(scenes), "CAPTIONS": posix(root / "none.srt"), "VO_DIR": posix(root / "no-such-voices")}, expect_exit=0)
        check("F: a missing voice folder is warned about on stderr, and the run still exits 0", "voice folder" in r.stderr and "does not exist" in r.stderr and r.returncode == 0, r.stderr[-300:])

    # the gate must not be skippable: with no python the script has to FAIL, not just print a warning (a source check: a run without python cannot be staged here)
    text = script.read_text(encoding="utf-8")
    m = re.search(r'if \[ -z "\$PY" \]; then\n(.*?)\nelse', text, re.S)
    check("the export gate fails closed when python is missing (GATE_FAILED=1 in that branch)", m is not None and "GATE_FAILED=1" in m.group(1))
    i_unset, i_pin = text.find("unset LC_ALL"), text.find("export LC_NUMERIC=C")
    check("the number locale is pinned after LC_ALL is cleared (LC_ALL would override it)", 0 <= i_unset < i_pin)


# ================================================================================================================ v1
V1 = [("v01-cold-open", 12), ("v02-title", 8), ("v03-problem", 12), ("v04-tender-in", 18), ("v05-agents-at-work", 15), ("v06-checker", 30), ("v07-erp-swap", 19),
      ("v08-what-if-voice", 18), ("v09-sign-off", 18), ("v10-integrations", 9), ("v11-grid-solar", 10), ("v12-proof", 12), ("v13-end-card", 10)]


def make_v1_workspace(root):
    root.mkdir(parents=True, exist_ok=True)
    for k, (name, out_s) in enumerate(V1, 1):
        footage(root / f"{name}.mp4", out_s - 2, grey(k), hue=(k * 23) % 360)
    ff("-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=170", "-f", "lavfi", "-i", "sine=frequency=660:sample_rate=48000:duration=170",
       "-filter_complex", "[0][1]amix=inputs=2:normalize=0,volume=0.4", "-ac", "1", "-c:a", "pcm_s16le", root / "vo.wav")


def framemd5(path):
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-map", "0:v", "-f", "framemd5", "-"], capture_output=True, text=True)
    return [ln for ln in r.stdout.splitlines() if not ln.startswith("#")]


def audio_md5(path):
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-vn", "-f", "md5", "-"], capture_output=True, text=True)
    return r.stdout.strip()


def v1_tests(root, ref):
    print("\n== v1 (unchanged: the committed script and this one on the same clips)")
    root.mkdir(parents=True, exist_ok=True)
    new_dir, old_dir = HERE, root / "old"
    old_dir.mkdir(parents=True, exist_ok=True)
    for f in ("assemble.sh", "caption_band.sh", "check_export.py"):
        r = subprocess.run(["git", "show", f"{ref}:docs/submission/video/{f}"], capture_output=True, cwd=HERE)
        if r.returncode != 0:
            check("v1: the baseline scripts can be read from git", False, f"{ref}:{f}: {r.stderr.decode()[:120]}")
            return
        (old_dir / f).write_bytes(r.stdout.replace(b"\r\n", b"\n"))
    shutil.copy(HERE / "captions.srt", old_dir / "captions.srt")
    make_v1_workspace(root / "src")
    runs = {}
    for tag, script in (("old", old_dir / "assemble.sh"), ("new", new_dir / "assemble.sh")):
        w = root / f"v1-{tag}"
        shutil.copytree(root / "src", w)
        runs[tag] = (w, run_assemble(script, w, args=("1",), expect_exit=0))
    (wo, ro), (wn, rn) = runs["old"], runs["new"]
    check("v1: both scripts exit 0", ro.returncode == 0 and rn.returncode == 0, f"old {ro.returncode}, new {rn.returncode}")
    check("v1: the gate ceiling stays 180 s", "Runtime ceiling for the export gate: 180 s" in rn.stdout)
    fo, fn = framemd5(wo / ".assemble_tmp/assembled_video.mp4"), framemd5(wn / ".assemble_tmp/assembled_video.mp4")
    check("v1: the assembled picture is identical frame by frame", fo == fn and len(fo) > 4000, f"{len(fo)} frames")
    check("v1: the mixed sound is identical", audio_md5(wo / ".assemble_tmp/mixed_audio.m4a") == audio_md5(wn / ".assemble_tmp/mixed_audio.m4a"))
    fo, fn = framemd5(wo / "final.mp4"), framemd5(wn / "final.mp4")
    check("v1: the final picture (with the caption band) is identical frame by frame", fo == fn and len(fo) > 4000, f"{len(fo)} frames")
    check("v1: the final sound is identical", audio_md5(wo / "final.mp4") == audio_md5(wn / "final.mp4"))
    check("v1: the gate gives the same verdicts", gate_verdicts(ro.stdout) == gate_verdicts(rn.stdout) and len(gate_verdicts(rn.stdout)) == 5, str(gate_verdicts(rn.stdout)))
    check("v1: v1 writes no beat-starts.txt", not (wn / "beat-starts.txt").exists())

    # the intended change (follow-up 1 of the #44 review): with no captions the old script skipped the whole gate, the new one runs it
    (old_dir / "captions.srt").unlink()
    w_old, w_new = root / "v1-old-nocap", root / "v1-new-nocap"
    shutil.copytree(root / "src", w_old)
    shutil.copytree(root / "src", w_new)
    ro = run_assemble(old_dir / "assemble.sh", w_old, args=("1",), expect_exit=0)
    rn = run_assemble(new_dir / "assemble.sh", w_new, {"CAPTIONS": posix(root / "none.srt")}, args=("1",), expect_exit=0)
    check("v1, no captions (intended change): the committed script skipped the whole gate", "export gate (which checks them) was skipped" in ro.stderr and not gate_verdicts(ro.stdout))
    g = gate_verdicts(rn.stdout)
    check("v1, no captions (intended change): this script runs the gate (format PASS, band checks SKIP)", g[:1] == [("PASS", "format")] and all(v == "SKIP" for v, _ in g[1:]) and len(g) == 5, str(g))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-v1", action="store_true")
    ap.add_argument("--skip-v2", action="store_true")
    ap.add_argument("--cases", default="ABCDEF", help="which v2 cases to run: A plain cut with captions, B intro + music, no captions, C ceiling and no label, D refusals, E silent intro placeholder, F missing voice folder")
    ap.add_argument("--baseline-ref", default="e76c4a097cd8245b64686b1cb9e5ae3849e3238c", help="the git ref whose assemble.sh, caption_band.sh and check_export.py are the v1 baseline: pinned to the build commit this change was made on (e76c4a0), so the comparison stays meaningful after it is merged")
    a = ap.parse_args()
    if not BASH or not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        print("assemble_selftest: needs bash, ffmpeg and ffprobe on PATH", file=sys.stderr)
        return 2
    root = Path(tempfile.mkdtemp(prefix="assemble-selftest-"))
    try:
        if not a.skip_v2:
            v2_tests(root / "v2", a.cases.upper())
        if not a.skip_v1:
            v1_tests(root / "v1", a.baseline_ref)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    if not results:
        print("assemble_selftest: no check ran (every part was skipped)", file=sys.stderr)
        return 2
    failed = [n for n, ok, _ in results if not ok]
    print(f"\n-- {len(results) - len(failed)} passed, {len(failed)} failed")
    if failed:
        print("SELF-TEST FAILED: " + "; ".join(failed), file=sys.stderr)
        return 1
    print("SELF-TEST PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
