# Kirchhoff demo video: edit plan v2

This plan goes with `../video-script-v2.md`. The v1 kit (`edit-plan.md`, `captions.srt`, `assemble.sh`) stays as it is. The teammate building the caption band in `assemble.sh` (#25) owns that file. This plan only lists the clip order v2 needs, so the order can be folded in once #25 lands.

**Targets:** 2:39 without Jayadratha's intro and 2:46 with it, as planned here; the real cut adds about a minute of product footage to reach 3:30 to 3:50 (HANDOFF §4.3). The ceiling is 3:59: the form asks for 3 to 4 minutes (Mehul's decision, 17 Oct). Picture is 1920×1080 at 30 fps, H.264, yuv420p.

## 1. The flow

1. **Render the scenes.** Do this after the golden capture, because the scenes read their numbers from the demo bundle.
2. **Record the voice, one WAV per beat** (§4). Record Mehul's intro first.
3. **Re-render the intro scenes with the real voice.** Their waveform and length come from the recording.
4. **Transcribe the voice** with `transcribe.py`, which uses Gemini on Vertex AI. The glossary pass and the cue rules give `captions-v2.srt`.
5. **Assemble** in beat order (§2), with the caption band from #25, and burn in `captions-v2.srt`.
6. **Check:** the runtime is under 3:59 (the gate ceiling, 239 s) and inside the 3:30 to 3:50 target, every number marked *from capture* matches, and every connector tag is visible.

### Commands

```bash
# 1 · scenes (from the repo root; no network; ~4 min for all 11 clips)
uv run --with playwright==1.64.0 python docs/submission/video/scenes/render.py docs/submission/video/scenes/out/ --previews

# 3 · intro scenes with the real voice (or a short clip instead of the photo)
uv run --with playwright==1.64.0 python docs/submission/video/scenes/render.py docs/submission/video/scenes/out/ \
    --scenes s1b-intro-mehul,s1c-intro-jayadratha \
    --intro-mehul ~/vo/intro_mehul.wav --intro-jayadratha ~/vo/intro_jayadratha.wav
#   video instead of the photo:  --intro-mehul-video ~/vo/intro_mehul.mp4
#   drop Jayadratha everywhere:  --no-jayadratha

# 4 · captions from the real recording (this is the only step that calls Vertex AI)
GOOGLE_GENAI_USE_VERTEXAI=true GOOGLE_CLOUD_PROJECT=ordinal-mep GOOGLE_CLOUD_QUOTA_PROJECT=ordinal-mep \
uv run --with google-genai python docs/submission/video/transcribe.py \
    ~/vo/b01-cold-open.wav@0.0 ~/vo/b02-title.wav@7.0 ~/vo/intro_mehul.wav@12.4 ~/vo/b04-problem.wav@22.0 \
    ~/vo/b05-requirements.wav@31.0 ... --out docs/submission/video/captions-v2.srt
#   each WAV@START is where that beat's voice starts in the final cut (seconds)
#   word timings are cached next to each WAV (<wav>.words.json); --refresh calls Gemini again
#   test without the network: add --dry-run --text "what was said"
```

`render.py` re-runs `build_data.py` first, which prints every number it will draw and a WARNING for anything it had to derive. The MP4s go to `scenes/out/`, which is git-ignored, together with `render-manifest.json`, which lists durations and frame hashes. Frames are a pure function of time. Repeat renders match frame for frame; a few blurred frames during motion can differ by sub-visible rounding (65 dB PSNR).

**Re-render after every capture.** The golden capture (`d9b6f46`) rewrote `hall-a.json`, `inbox.json` and `integrations.json`. The scenes were re-rendered from it: S3 now shows the captured triage (fields, the four main fit reasons and the supply sentence), and S4 shows "25/26 quotes verified". `render.py --check` runs before every render. It fails a scene if any visible element pokes out of its card at 8 sample times, including the final frame, so longer data shows up as an error rather than a clipped frame.

## 2. Beat table

| # | In | Out | Sec | Clip | Notes |
|---|---|---|---|---|---|
| 1 | 0:00 | 0:07 | 7 | `v01-cold-open.mp4` (footage) | Open on the product. The R11 clash is fixed and the hall turns green. Keep the fictional-data banner. |
| 2 | 0:07 | 0:12 | 5 | `scenes/out/s1-title.mp4` | Hard cut in. |
| 3 | 0:12 | 0:22 | ~10 | `scenes/out/s1b-intro-mehul.mp4` | Carries its own voice. The length follows the recording: speech plus 1 s. |
| 3b | — | — | ~7 | `scenes/out/s1c-intro-jayadratha.mp4` | **Optional.** Insert after 3 and shift everything by its length. |
| 4 | 0:22 | 0:31 | 9 | `scenes/out/s2-problem.mp4` | |
| 5 | 0:31 | 0:45 | 14 | `scenes/out/s3-requirements-in.mp4` | Gmail (connector · sandbox), Ariba and Drive (simulated). |
| 6 | 0:45 | 0:58 | 13 | `v04-tender-in.mp4` (footage) | Hall B intake: the quotes-verified counter, the §2.3 chip, the contradiction, plan approval. |
| 7 | 0:58 | 1:05 | 7 | `scenes/out/s4-agents.mp4` | |
| 8 | 1:05 | 1:15 | 10 | `v05-agents-at-work.mp4` (footage) | Time-compressed. Burn in "time-compressed ×N" with the real N and an elapsed clock. |
| 9 | 1:15 | 1:23 | 8 | `scenes/out/s5-checks.mp4` | |
| 10 | 1:23 | 1:38 | 15 | `v06-checker.mp4` (footage) | The R05 and R11 drawers, the fixes, "r2 · all pass". |
| 11 | 1:38 | 1:48 | 10 | `v07-erp-swap.mp4` (footage) | |
| 12 | 1:48 | 2:00 | 12 | `v08-what-if-voice.mp4` (footage) | The in-clip question stays as sync audio. |
| 13 | 2:00 | 2:06 | 6 | `scenes/out/s6-sign.mp4` | |
| 14 | 2:06 | 2:12 | 6 | `v09-sign-off.mp4` (footage) | The real stamp. Trim this beat first if the cut is long. |
| 15 | 2:12 | 2:24 | 12 | `scenes/out/s7-connectors.mp4` | SAP S/4HANA, Google Drive and CRM, each tagged "connector · sandbox". |
| 16 | 2:24 | 2:32 | 8 | `scenes/out/s8-google-cloud.mp4` | |
| 17 | 2:32 | 2:39 | 7 | `scenes/out/s9-end.mp4` | Fade to white or black at the very end. Both disclaimers are on the card. |

**Runtime budget:** product footage 73 s, flow scenes 47 s, other scenes 39 s, for **159 s (2:39)**. Jayadratha's intro adds 7 s, for **166 s (2:46)**. As planned this is shorter than the 3:30 to 3:50 target: the real cut adds about a minute of product footage (HANDOFF §4.3). If the cut runs past 3:50, trim beat 14 first, then beat 8 to 8 s, then beat 2 to 4 s.

For `assemble.sh`, after #25 lands, the v2 order is: `v01-cold-open`, `s1-title`, `s1b-intro-mehul`, optionally `s1c-intro-jayadratha`, `s2-problem`, `s3-requirements-in`, `v04-tender-in`, `s4-agents`, `v05-agents-at-work`, `s5-checks`, `v06-checker`, `v07-erp-swap`, `v08-what-if-voice`, `s6-sign`, `v09-sign-off`, `s7-connectors`, `s8-google-cloud`, `s9-end`. The scene clips need no trim (`in=0`, `out=duration`, speed 1). The two intro clips carry audio, so mix their audio in rather than stripping it, in the same way as beat 8's in-clip question.

**Caption-safe area:** every scene keeps its content above y = 900, and the corner labels sit at the top. The caption band from #25 can use the bottom 180 px without covering anything.

## 3. Honesty checklist (before export)

- [ ] Every connector on screen carries its tag. Scenes: Gmail "connector · sandbox"; Ariba RFQ and Drive spec folder "simulated"; SAP S/4HANA, Google Drive and CRM "connector · sandbox"; the S8 strip "connectors · sandbox". In footage, the Integrations page shows "sandbox (simulated)".
- [ ] No line of voice or caption claims a live customer integration.
- [ ] Every number marked *from capture* in the script matches the re-rendered scenes and the recorded footage.
- [ ] The fictional-data banner is visible in the footage. The end card carries "Demo companies, people and data are fictional · IEC-based, illustrative values, not for construction" and the connector disclaimer.
- [ ] Beat 8 shows the real time-compression multiple.
- [ ] No title such as founder or CEO appears anywhere. The lower thirds come from `scenes/team.json`.
- [ ] The repo URL placeholder in `scenes/team.json` (`end_card.repo`) is filled in, and `s9-end` is re-rendered.

## 4. Recording the voice

**Mehul's intro (≈10 s, first person, no title):**

```bash
ffmpeg -f avfoundation -i ":0" -ac 1 -ar 48000 -t 15 intro_mehul.wav
```

`render.py` trims the leading and trailing room tone automatically, so the fixed 15 s is fine. Record Jayadratha with the same command and `-t 10 intro_jayadratha.wav`. For each other beat, use the same command with that beat's name and a `-t` a few seconds longer than the beat, for example `-t 16 b05-requirements.wav`. Run `ffmpeg -f avfoundation -list_devices true -i ""` first if the mic is not device 0.

**Quiet-room checklist**
- [ ] Close the door and windows. Switch off fans, AC, and notification sounds on the laptop and phone.
- [ ] Use a soft room (curtains, a bed or a sofa nearby), not a bare tiled one. Avoid speaking straight at a wall.
- [ ] Keep the mic about a hand's width (15–20 cm) away, slightly off to one side of your mouth to soften plosives. Keep the same distance for every take.
- [ ] Record 5 s of silence and play it back. Fix any hum or hiss you can hear before going on.
- [ ] Drink some water. Sit up straight, smile on the first line, and speak at a calm pace in your own Indian English. You do not need an American read.
- [ ] Use the talking points, not the script. Paraphrase freely, but say the **numbers and product names** exactly.
- [ ] Do two takes of each beat and keep the better one. Leave a second of silence at the start and end.
- [ ] Play each take back once before moving on. If a number is wrong, redo the take; never fix a number in post.

## 5. Captions

Captions are built from what was actually said, not from the script:
- `transcribe.py` sends each WAV to `gemini-3.8-flash` on Vertex AI (project `ordinal-mep`, location `global`) as audio input, with a JSON schema that asks for word-level start and end times.
- It then runs a glossary pass. That pass fixes product names (Kirchhoff, Ordinal, Gemini, Vertex AI, Cloud Run, Firestore, Firebase, SAP S/4HANA, Ariba, Gmail, Google Drive), units (kW, MW, MVA, kV, %), ids (R05, R11, R15, FA-01, FB-03, H-Z2, 2N) and acronyms (MEP, CDU, UPS, LLM, ADK). It also applies British and Indian spelling: organise, colour, programme, centre, metre, licence.
- Finally it applies the cue rules: at most 42 characters per line, at most 2 lines per cue, and 1.5–6 s per cue. A pause of 0.6 s or a sentence end starts a new cue.
- It prints `CHECK:` for any cue that still breaks a rule, so you can fix those few by hand in the SRT.

The script was tested only in `--dry-run` mode, on one clip made with macOS `say`; it has not called Vertex yet. The first real call happens when Mehul runs it on his recordings.

## 6. Open items

1. Mehul's intro recording, and Jayadratha's if it is used, then a re-render of the intro clips. The current intro clips carry a silent placeholder track and read "voice track pending".
2. Done for `d9b6f46`. Re-render again after any later capture; `build_data.py` prints WARNING lines for anything it has to derive.
3. The repo URL in `scenes/team.json`.
4. Done (#25): `PLAN=v2 ./assemble.sh <work_dir>` builds this order (the header of `assemble.sh` lists the inputs and options; `python3 assemble_selftest.py` tests it). It writes `beat-starts.txt` with the measured `wav@start` arguments for `transcribe.py`.
5. Music, as before: optional and royalty-free only, never under the intro voice.
