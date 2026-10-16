#!/usr/bin/env python3
"""Render the Kirchhoff motion-graphic scenes to 1080p30 MP4s.

Each scene is a self-contained HTML page under this folder that draws itself as a pure
function of time (lib/stage.js). This script:

  1. re-reads the demo data (build_data.py → lib/data.js), so numbers always match the capture;
  2. turns each intro voice track into an amplitude envelope (lib/audio-<who>.js) with ffmpeg;
  3. opens each scene in Playwright's Chromium at 1920×1080, sets t = i/30 for every frame,
     screenshots it, and pipes the PNGs into ffmpeg (H.264, yuv420p, CRF 16);
  4. muxes the intro voice into the intro clips, so the editor gets picture and sound in sync;
  5. optionally writes one preview still per scene.

Run it from anywhere (no network; Chromium comes from ~/Library/Caches/ms-playwright):

  uv run --with playwright==1.64.0 python docs/submission/video/scenes/render.py out/
  uv run --with playwright==1.64.0 python docs/submission/video/scenes/render.py out/ \
      --intro-mehul ~/vo/intro_mehul.wav --scenes s1b-intro-mehul

Options worth knowing:
  --scenes a,b        render only these (names from --list)
  --previews          also write scenes/previews/<scene>.png at each scene's hero time
  --stills 1.5,4      write PNG frames at these times instead of video (for review)
  --no-jayadratha     leave out Jayadratha's optional intro
  --check             only run the layout check: at each scene's final frame, no element may
                      extend beyond its card (it also runs, as a warning, before every render)
  --intro-mehul-video clip.mp4   use a short video instead of the photo (its audio is used
                      unless --intro-mehul gives a separate WAV)

The output folder is created if needed and is never inside the repo's tracked files
(scenes/.gitignore ignores out/). Re-running overwrites the MP4s; frames are deterministic.
"""
from __future__ import annotations

import argparse
import array
import hashlib
import json
import math
import shutil
import subprocess
import sys
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
FFPROBE = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"
FPS = 30

# name → (html file, query, includes audio of)
SCENES = [
    ("s1-title", "s1-title.html", "", None),
    ("s1b-intro-mehul", "s1b-intro.html", "who=mehul", "mehul"),
    ("s1c-intro-jayadratha", "s1b-intro.html", "who=jayadratha", "jayadratha"),
    ("s2-problem", "s2-problem.html", "", None),
    ("s3-requirements-in", "s3-requirements-in.html", "", None),
    ("s4-agents", "s4-agents.html", "", None),
    ("s5-checks", "s5-checks.html", "", None),
    ("s6-sign", "s6-sign.html", "", None),
    ("s7-connectors", "s7-connectors.html", "", None),
    ("s8-google-cloud", "s8-google-cloud.html", "", None),
    ("s9-end", "s9-end.html", "", None),
]


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, **kw)


def probe_duration(path: Path) -> float:
    out = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of",
                          "default=noprint_wrappers=1:nokey=1", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


# ---------------------------------------------------------------------------
# audio → envelope
# ---------------------------------------------------------------------------
def envelope(src: Path, cache: Path, rate: int = 100) -> dict:
    """Decode to 16 kHz mono PCM with ffmpeg and return an RMS envelope at `rate` Hz (0..1)."""
    cache.mkdir(parents=True, exist_ok=True)
    pcm = cache / (src.stem + ".16k.wav")
    run([FFMPEG, "-y", "-loglevel", "error", "-i", str(src), "-ac", "1", "-ar", "16000", "-sample_fmt", "s16", str(pcm)])
    with wave.open(str(pcm), "rb") as w:
        n = w.getnframes()
        data = array.array("h", w.readframes(n))
    sr = 16000
    hop = sr // rate
    env = []
    for i in range(0, len(data), hop):
        chunk = data[i:i + hop]
        if not chunk:
            break
        env.append(math.sqrt(sum(s * s for s in chunk) / len(chunk)) / 32768.0)
    peak = max(env) if env else 0.0
    # normalise to the loudest moment; the scene applies a gentle curve so quiet words still show
    ref = peak if peak > 1e-4 else 1.0
    norm = [round(min(1.0, v / ref), 3) for v in env]
    return {"file": src.name, "duration": round(len(data) / sr, 3), "rate": rate, "env": norm,
            "silent": peak < 1e-4}


LEAD_S = 0.4  # the picture settles for 0.4 s before the voice starts


def trim_silence(src: Path, dst: Path, pad: float = 0.25) -> Path:
    """Cut leading and trailing room tone (the record command runs a fixed 15 s), keep `pad` s either side."""
    env = envelope(src, dst.parent)
    e, rate = env["env"], env["rate"]
    speech = [i for i, v in enumerate(e) if v > 0.12]
    if not speech:
        return src
    a = max(0.0, speech[0] / rate - pad)
    b = min(env["duration"], speech[-1] / rate + pad + 0.1)
    run([FFMPEG, "-y", "-loglevel", "error", "-i", str(src), "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-ac", "1",
         "-ar", "48000", str(dst)])
    print(f"  trimmed {src.name}: {a:.2f}–{b:.2f} s of {env['duration']:.2f} s")
    return dst


def silent_wav(path: Path, seconds: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    run([FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", f"{seconds}",
         "-c:a", "pcm_s16le", str(path)])
    return path


def prepare_intro(who: str, wav: Path | None, video: Path | None, cache: Path, team: dict) -> dict:
    """Pick the voice track (given WAV → video's own audio → team.json path → silent placeholder)."""
    member = team["members"][who]
    src = None
    if wav:
        src = wav
    elif video:
        src = cache / f"{who}_from_video.wav"
        run([FFMPEG, "-y", "-loglevel", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", "48000", str(src)])
    elif member.get("audio") and (HERE / member["audio"]).exists():
        src = HERE / member["audio"]
    placeholder = src is None
    if src is None:
        src = silent_wav(cache / f"silent_{who}.wav", 9.0 if who == "mehul" else 6.0)
        print(f"  {who}: no recording yet → silent placeholder ({src.name})")
    elif not video:  # a video keeps its own timing, so only a separate voice WAV is trimmed
        src = trim_silence(src, cache / f"{who}_trimmed.wav")
    env = envelope(src, cache)
    env["who"] = who
    env["placeholder"] = placeholder
    env["lead"] = LEAD_S
    frames_dir = None
    if video:
        frames_dir = cache / f"frames_{who}"
        if frames_dir.exists():
            shutil.rmtree(frames_dir)
        frames_dir.mkdir(parents=True)
        run([FFMPEG, "-y", "-loglevel", "error", "-i", str(video), "-vf", f"fps={FPS},scale=1280:-2", "-q:v", "3",
             str(frames_dir / "f_%05d.jpg")])
        env["video_frames"] = frames_dir.resolve().as_uri() + "/"
        env["video_count"] = len(list(frames_dir.glob("f_*.jpg")))
    (HERE / "lib" / f"audio-{who}.js").write_text(
        "// Generated by render.py from the intro voice track. Do not edit.\n"
        f"window.KAUDIO = window.KAUDIO || {{}};\nwindow.KAUDIO[{json.dumps(who)}] = {json.dumps(env)};\n",
        encoding="utf-8")
    return {"src": src, **env}


# ---------------------------------------------------------------------------
# frame capture
# ---------------------------------------------------------------------------
def open_scene(browser, html: str, query: str):
    page = browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
    url = (HERE / html).resolve().as_uri() + "?render=1" + (f"&{query}" if query else "")
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(url)
    meta = page.evaluate("window.__sceneReady")
    if errors:
        raise RuntimeError(f"{html}: page errors: {errors}")
    return page, meta


def shot(page, t: float) -> bytes:
    page.evaluate("t => window.__scene.setTime(t)", t)
    return page.screenshot(type="png", caret="hide", animations="disabled")


# Every element inside a box must stay inside it (1 px tolerance). Boxes are .card elements and
# anything marked data-box. SVG internals are skipped; the <svg> element itself is checked.
OVERFLOW_JS = """
() => {
  const tol = 1, out = [];
  const label = (e) => e.id ? '#' + e.id : (e.className && e.className.baseVal === undefined && e.className
    ? e.tagName.toLowerCase() + '.' + String(e.className).trim().split(/\\s+/).join('.') : e.tagName.toLowerCase());
  document.querySelectorAll('.card, [data-box]').forEach((box) => {
    const b = box.getBoundingClientRect();
    if (!b.width || !b.height) return;
    box.querySelectorAll('*').forEach((el) => {
      if (el.closest('svg') && el.tagName.toLowerCase() !== 'svg') return;
      const cs = getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden') return;
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height) return;
      const over = [b.left - r.left, r.right - b.right, b.top - r.top, r.bottom - b.bottom].map((v) => Math.round(v));
      if (Math.max(...over) > tol) {
        const text = (el.textContent || '').trim().slice(0, 50);
        out.push(`${label(box)} ⊃ ${label(el)} overflows by ${Math.max(...over)} px` + (text ? ` ("${text}")` : ''));
      }
    });
  });
  return out;
}
"""


def check_overflow(browser, scenes) -> list[str]:
    """Open each scene at its final frame and report any element that pokes out of its card."""
    problems = []
    for name, html, q, _ in scenes:
        page, meta = open_scene(browser, html, q)
        page.evaluate("t => window.__scene.setTime(t)", float(meta["duration"]))
        found = page.evaluate(OVERFLOW_JS)
        page.close()
        print(f"  {name}: " + ("ok" if not found else f"{len(found)} overflow(s)"))
        problems += [f"{name}: {f}" for f in found]
    return problems


def render_scene(browser, name: str, html: str, query: str, out: Path, audio: Path | None, crf: int) -> dict:
    page, meta = open_scene(browser, html, query)
    dur = float(meta["duration"])
    n = int(round(dur * FPS))
    dst = out / f"{name}.mp4"
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "png", "-i", "-"]
    if audio:
        ms = int(LEAD_S * 1000)
        cmd += ["-i", str(audio), "-map", "0:v", "-map", "1:a", "-af", f"adelay={ms}:all=1,apad", "-shortest",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-movflags", "+faststart", str(dst)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    h = hashlib.sha256()
    for i in range(n):
        png = shot(page, i / FPS)
        h.update(png)
        proc.stdin.write(png)
        if i % 60 == 0:
            print(f"    {name}: frame {i}/{n}", end="\r", flush=True)
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg failed for {name}")
    page.close()
    real = probe_duration(dst)
    print(f"    {name}: {n} frames, {real:.2f} s → {dst}  (frames sha256 {h.hexdigest()[:12]})")
    return {"name": name, "frames": n, "seconds": round(real, 2), "file": str(dst), "frames_sha": h.hexdigest()[:12]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path, nargs="?", default=HERE / "out", help="output folder (default scenes/out)")
    ap.add_argument("--scenes", default="", help="comma-separated scene names (default: all)")
    ap.add_argument("--list", action="store_true", help="list scene names and exit")
    ap.add_argument("--previews", action="store_true", help="also write scenes/previews/<scene>.png")
    ap.add_argument("--previews-only", action="store_true", help="only write the preview stills")
    ap.add_argument("--stills", default="", help="comma-separated times: write PNGs to OUT/stills instead of video")
    ap.add_argument("--intro-mehul", type=Path, help="Mehul's intro voice (WAV); default team.json path or silence")
    ap.add_argument("--intro-mehul-video", type=Path, help="optional short MP4 to use instead of the photo")
    ap.add_argument("--intro-jayadratha", type=Path, help="Jayadratha's intro voice (WAV)")
    ap.add_argument("--intro-jayadratha-video", type=Path)
    ap.add_argument("--no-jayadratha", action="store_true", help="skip the optional Jayadratha intro")
    ap.add_argument("--check", action="store_true", help="only run the overflow check (final frame of each scene)")
    ap.add_argument("--crf", type=int, default=16)
    ap.add_argument("--project", default="hall-a")
    ap.add_argument("--email", default="em-hall-b")
    ap.add_argument("--demo-dir", type=Path)
    args = ap.parse_args()

    if args.list:
        for s in SCENES:
            print(s[0])
        return 0
    from playwright.sync_api import sync_playwright  # imported late so --list works without it

    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    cache = out / ".cache"
    cache.mkdir(exist_ok=True)

    print("1/4 data: re-reading the demo bundle")
    cmd = [sys.executable, str(HERE / "build_data.py"), "--project", args.project, "--email", args.email]
    if args.demo_dir:
        cmd += ["--demo-dir", str(args.demo_dir)]
    run(cmd)

    team = json.loads((HERE / "team.json").read_text(encoding="utf-8"))
    print("2/4 intro audio → waveform envelopes")
    intros = {
        "mehul": prepare_intro("mehul", args.intro_mehul, args.intro_mehul_video, cache, team),
        "jayadratha": prepare_intro("jayadratha", args.intro_jayadratha, args.intro_jayadratha_video, cache, team),
    }
    for who, info in intros.items():
        print(f"  {who}: {info['src'].name} · {info['duration']} s" + (" · placeholder (silent)" if info["placeholder"] else ""))

    wanted = [s for s in args.scenes.split(",") if s]
    scenes = [s for s in SCENES if (not wanted or s[0] in wanted)]
    if args.no_jayadratha:
        scenes = [s for s in scenes if s[3] != "jayadratha"]
    unknown = set(wanted) - {s[0] for s in SCENES}
    if unknown:
        print(f"ERROR: unknown scenes {sorted(unknown)}; see --list", file=sys.stderr)
        return 1

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--force-color-profile=srgb", "--font-render-hinting=none",
                                          "--disable-lcd-text", "--allow-file-access-from-files"])
        print("layout check: nothing may overflow its card (final frame)")
        problems = check_overflow(browser, scenes)
        for pr in problems:
            print(f"  OVERFLOW {pr}")
        if args.check:
            browser.close()
            return 1 if problems else 0
        if args.stills:
            print("3/4 stills")
            sd = out / "stills"
            sd.mkdir(exist_ok=True)
            for name, html, q, _ in scenes:
                page, meta = open_scene(browser, html, q)
                for ts in args.stills.split(","):
                    t = min(float(ts), meta["duration"])
                    path = sd / f"{name}@{float(ts):05.2f}.png"
                    path.write_bytes(shot(page, t))
                    print(f"  {path}")
                page.close()
            browser.close()
            return 0
        if not args.previews_only:
            print(f"3/4 video → {out}")
            for name, html, q, who in scenes:
                # intro clips carry their voice (or the silent placeholder, so every intro has an audio stream)
                audio = intros[who]["src"] if who else None
                results.append(render_scene(browser, name, html, q, out, audio, args.crf))
        if args.previews or args.previews_only:
            print("4/4 preview stills → scenes/previews/")
            pd = HERE / "previews"
            pd.mkdir(exist_ok=True)
            for name, html, q, _ in scenes:
                page, meta = open_scene(browser, html, q)
                (pd / f"{name}.png").write_bytes(shot(page, float(meta["hero"])))
                print(f"  previews/{name}.png @ {meta['hero']} s")
                page.close()
        browser.close()

    if results:
        total = sum(r["seconds"] for r in results)
        (out / "render-manifest.json").write_text(json.dumps({"fps": FPS, "scenes": results, "total_seconds": round(total, 2)},
                                                             indent=1), encoding="utf-8")
        print(f"done: {len(results)} clips, {total:.1f} s of motion graphics → {out}/render-manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
