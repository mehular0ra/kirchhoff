# Kirchhoff demo video: edit plan v2

This plan goes with `../video-script-v2.md`. The v1 kit (`edit-plan.md`, `captions.srt`, `assemble.sh`) stays as it is. The teammate building the caption band in `assemble.sh` (#25) owns that file. This plan only lists the clip order v2 needs, so the order can be folded in once #25 lands.

**Targets:** 3:28 without Jayadratha's intro and 3:35 with it, as planned here, inside the form's 3:00 to 4:00 and near the 3:30 to 3:50 target (HANDOFF §4.3). The first version of this plan ran 2:39 and 2:46, under the form's minimum; four extra beats (5b, 10b, 15b, 16b: 49 s) bring it up, and a real take that runs over its beat adds a little more. The ceiling is 3:59: the form asks for 3 to 4 minutes (Mehul's decision, 17 Oct). Picture is 1920×1080 at 30 fps, H.264, yuv420p.

## 1. The flow

1. **Render the scenes.** Do this after the golden capture, because the scenes read their numbers from the demo bundle.
2. **Record the voice, one WAV per beat** (§4). Record Mehul's intro first.
3. **Re-render the intro scenes with the real voice.** Their waveform and length come from the recording.
4. **Transcribe the voice** with `transcribe.py`, which uses Cloud Speech-to-Text (Chirp 2). The glossary pass and the cue rules give `captions-v2.srt`.
5. **Assemble** in beat order (§2), with the caption band from #25, and burn in `captions-v2.srt`.
6. **Check:** the runtime is under 3:59 (the gate ceiling, 239 s) and inside the 3:30 to 3:50 target, every number marked *from capture* matches, and every connector tag is visible.

### Commands

```bash
# 1 · scenes (from the repo root; no network; ~4 min for all 12 clips)
uv run --with playwright==1.64.0 python docs/submission/video/scenes/render.py docs/submission/video/scenes/out/ --previews

# 3 · intro scenes with the real voice (or a short clip instead of the photo)
uv run --with playwright==1.64.0 python docs/submission/video/scenes/render.py docs/submission/video/scenes/out/ \
    --scenes s1b-intro-mehul,s1c-intro-jayadratha \
    --intro-mehul ~/vo/intro_mehul.wav --intro-jayadratha ~/vo/intro_jayadratha.wav
#   video instead of the photo:  --intro-mehul-video ~/vo/intro_mehul.mp4
#   drop Jayadratha everywhere:  --no-jayadratha

# 4 · captions from the real recording (this is the only step that calls Google Cloud: Speech-to-Text Chirp 2, the default engine)
GOOGLE_CLOUD_QUOTA_PROJECT=ordinal-mep \
uv run --python 3.12 --with google-cloud-speech python docs/submission/video/transcribe.py \
    ~/vo/b01-cold-open.wav@0.0 ~/vo/b02-title.wav@7.0 <work_dir>/.assemble_tmp/own_3.wav@12.0 ~/vo/b04-problem.wav@22.0 \
    ~/vo/b05-requirements.wav@31.0 ... --out docs/submission/video/captions-v2.srt
#   each WAV@START is where that beat's voice starts in the final cut (seconds)
#   the intro voices live INSIDE the scene clips (render.py trims and delays them): caption them from the own_3.wav (own_3b.wav) that assemble.sh
#   extracts, not from the raw recording; beat-starts.txt prints the exact arguments. After re-rendering an intro, run assemble.sh again first.
#   word timings are cached next to each WAV (<wav>.words.json); --refresh calls Speech-to-Text again
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
| 5b | 0:45 | 0:59 | 14 | `v12-inbox-triage.mp4` (footage) | The bids inbox, six emails: Pursue on the Hall B tender with its reasons; the Vindhya BOQ gets a Decline (a substation is not one of our asset packs) and its load, only on a scanned page, is marked "Not verified (scan)". Nothing is clicked that writes to the sandbox. Voice `b18-inbox`. |
| 6 | 0:59 | 1:12 | 13 | `v04-tender-in.mp4` (footage) | Hall B intake: the quotes-verified counter, the §2.3 chip, the contradiction, plan approval. |
| 7 | 1:12 | 1:19 | 7 | `scenes/out/s4-agents.mp4` | |
| 8 | 1:19 | 1:29 | 10 | `v05-agents-at-work.mp4` (footage) | Time-compressed. Burn in "time-compressed ×N" with the real N and an elapsed clock. |
| 9 | 1:29 | 1:37 | 8 | `scenes/out/s5-checks.mp4` | |
| 10 | 1:37 | 1:52 | 15 | `v06-checker.mp4` (footage) | The R05 and R11 drawers, the fixes, "r2 · all pass". |
| 10b | 1:52 | 2:04 | 12 | `v13-trust-quote.mp4` (footage) | The R05 drawer for FA-01, then "Open tender §4.6": the tender PDF opens on that page with a box around the verified quote. Voice `b19-trust`. |
| 11 | 2:04 | 2:14 | 10 | `v07-erp-swap.mp4` (footage) | |
| 12 | 2:14 | 2:26 | 12 | `v08-what-if-voice.mp4` (footage) | The in-clip question stays as sync audio. |
| 13 | 2:26 | 2:32 | 6 | `scenes/out/s6-sign.mp4` | |
| 14 | 2:32 | 2:38 | 6 | `v09-sign-off.mp4` (footage) | The real stamp. Trim this beat first if the cut is long. |
| 15 | 2:38 | 2:50 | 12 | `scenes/out/s7-connectors.mp4` | SAP S/4HANA, Google Drive and CRM, each tagged "connector · sandbox". |
| 15b | 2:50 | 3:01 | 11 | `v11-grid-solar.mp4` (footage) | The 132 kV grid intake and the 5 MWp solar project, each with its own checks. Voice `b20-platform`. |
| 16 | 3:01 | 3:09 | 8 | `scenes/out/s8-google-cloud.mp4` | |
| 16b | 3:09 | 3:21 | 12 | `scenes/out/s10-numbers.mp4` | Four measured numbers, each with its source: planted faults caught, quotes verified, median seconds, cost per design. Voice `b21-numbers`. |
| 17 | 3:21 | 3:28 | 7 | `scenes/out/s9-end.mp4` | Fade to white or black at the very end. Both disclaimers are on the card. |

**Runtime budget:** product footage 110 s, flow scenes 47 s, other scenes 51 s, for **208 s (3:28)**. Jayadratha's intro adds 7 s, for **215 s (3:35)**. This is inside the form's 3:00 to 4:00 and a few seconds under the 3:30 to 3:50 target (HANDOFF §4.3); a voice take that runs over its beat, or an intro longer than 10 s, closes that gap. If the cut runs past 3:50, trim beat 14 first, then beat 8 to 8 s, then beat 5b to 12 s, then beat 2 to 4 s.

For `assemble.sh` the v2 order is: `v01-cold-open`, `s1-title`, `s1b-intro-mehul`, optionally `s1c-intro-jayadratha`, `s2-problem`, `s3-requirements-in`, `v12-inbox-triage`, `v04-tender-in`, `s4-agents`, `v05-agents-at-work`, `s5-checks`, `v06-checker`, `v13-trust-quote`, `v07-erp-swap`, `v08-what-if-voice`, `s6-sign`, `v09-sign-off`, `s7-connectors`, `v11-grid-solar`, `s8-google-cloud`, `s10-numbers`, `s9-end`. The scene clips need no trim (`in=0`, `out=duration`, speed 1). The two intro clips carry audio, so mix their audio in rather than stripping it, in the same way as beat 8's in-clip question.

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

`render.py` trims the leading and trailing room tone automatically, so the fixed 15 s is fine. Record Jayadratha with the same command and `-t 10 intro_jayadratha.wav`. For each other beat, use the same command with that beat's name and a `-t` a few seconds longer than the beat, for example `-t 16 b05-requirements.wav`. The four extra beats of the longer cut are recorded as `b18-inbox.wav`, `b19-trust.wav`, `b20-platform.wav` and `b21-numbers.wav`: the number in a file name is the voice number, not the beat's place in the order (beats 5b, 10b, 15b and 16b). Run `ffmpeg -f avfoundation -list_devices true -i ""` first if the mic is not device 0.

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
- `transcribe.py` sends each WAV to Cloud Speech-to-Text (Chirp 2, `us-central1`, `en-IN`, with phrase hints for our names) and asks for word-level start and end times. It does not use Gemini by default: on 16 Oct Vertex blocked most Gemini calls with a safety filter and a lite model invented timings, so Chirp is the default engine (`--engine gemini` keeps the old path, which needs `google-genai` and `GOOGLE_GENAI_USE_VERTEXAI=true`).
- It then runs a glossary pass. That pass fixes product names (Kirchhoff, Ordinal, Gemini, Vertex AI, Cloud Run, Firestore, Firebase, SAP S/4HANA, Ariba, Gmail, Google Drive), units (kW, MW, MVA, kV, %), ids (R05, R11, R15, FA-01, FB-03, H-Z2, 2N) and acronyms (MEP, CDU, UPS, LLM, ADK). It also applies British and Indian spelling: organise, colour, programme, centre, metre, licence.
- Finally it applies the cue rules: at most 42 characters per line, at most 2 lines per cue, and 1.5–6 s per cue. A pause of 0.6 s or a sentence end starts a new cue.
- It prints `CHECK:` for any cue that still breaks a rule, so you can fix those few by hand in the SRT.

The cue rules and the glossary were tested in `--dry-run` mode (no network) on one clip made with macOS `say`; the real Chirp call was run on 16 Oct on Mehul's intro and heard every product word. The first run on the full narration happens when Jayadratha records it (docs/HANDOFF.md §4.2).

## 6. Open items

1. Mehul's intro recording, and Jayadratha's if it is used, then a re-render of the intro clips. The current intro clips carry a silent placeholder track and read "voice track pending".
2. Done for `d9b6f46`. Re-render again after any later capture; `build_data.py` prints WARNING lines for anything it has to derive.
3. The repo URL in `scenes/team.json`.
4. Done (#25): `PLAN=v2 ./assemble.sh <work_dir>` builds this order (the header of `assemble.sh` lists the inputs and options; `python3 assemble_selftest.py` tests it). It writes `beat-starts.txt` with the measured `wav@start` arguments for `transcribe.py`.
5. Music, as before: optional and royalty-free only, never under the intro voice.
