---
name: cheer-driven-highlights
description: Detect crowd cheers, applause, or screams in long videos (sports matches, concerts, events) from the AUDIO track and auto-cut highlight reels. Use when a user has a long match or event recording and wants to extract goal or highlight moments by cheering or crowd reaction without manually scrubbing. Works even when the footage is a fixed wide-angle camera with no visible audience — audio is the locator. Requires ffmpeg/ffprobe and python3 with numpy, scipy, and Pillow.
agent_created: true
---

# Cheer-Driven Highlights

## Overview
Locate audio climax moments (crowd cheers, applause, screams) in long videos
and cut them into a highlight reel — fully automatically, no manual scrubbing.
The pipeline streams audio features, scores each frame with a local z-score
cheer detector, merges bursts into events, ranks/filters candidates, then cuts
and assembles the reel with fades + caption cards.

This is the right skill when the user says things like:
- "按欢呼声把进球片段剪出来" / "cut the goals by cheering"
- "这场比赛/演出太长，帮我把精彩瞬间自动剪一下"
- "观众鼓掌/尖叫的地方都剪出来"

Key constraint: when the footage is a fixed wide-angle shot (no visible
audience, no commentary, tiny people), audio is the **only** reliable locator —
the pipeline can say *when* a cheer happened but cannot tell from the picture
whether it was a goal or a miss. Always tell the user to eyeball the results.

**Near-goal precondition (re-check on every run):** a fixed overhead camera
normally covers only half the pitch plus one goal; cheers are full-field but the
picture can verify only the visible side. Analyse **only the goal nearest the
camera**. Re-identify it on every invocation (larger goal rectangle, nearer the
frame edge, wider posts) — teams swap ends at half-time, so the near goal
changes, and cross-half footage must be judged per segment. Never apply visual
criteria, review crops, or `check_goal.py` scans to the far goal. See
`references/goal-review.md`.

## Quick Start
```bash
# Use the isolated venv python (has numpy/scipy/PIL)
python scripts/run_pipeline.py VIDEO_DIR --mode top --top 10
# full reel, every candidate, no filtering:
python scripts/run_pipeline.py VIDEO_DIR --mode all
# just produce the candidate list first, decide later:
python scripts/run_pipeline.py VIDEO_DIR --dry-run
# add a generated, on-beat soundtrack (ducked under the crowd cheers):
python scripts/run_pipeline.py VIDEO_DIR --mode top --top 10 --bgm
```
Outputs land in `./cheer_out/` (reel + `clips/` or `clips_all/`; `--bgm`
additionally writes `高光集_配乐.mp4` / `全集_配乐.mp4`).

## Workflow
1. **Probe** video dir → list videos (mp4/mov/mkv/avi). **Calibrate the camera
   and identify the near goal** (near-goal precondition above) → fix
   `NEAR_GOAL = {side, crop, box}` for this run; all visual review uses only it.
2. **Extract audio** → 16k mono WAV per video (ffmpeg, `feats.extract_audio`).
3. **Features** → `feats.py` streams RMS / band / flat / cent / zcr / baseline
   (never load the whole WAV into memory — OOM risk on large files).
4. **Detect** → `detect2.py` local z-score cheer score, 93rd-pctile adaptive
   gate, morphological cleanup, burst merging (22s join).
5. **Merge candidates** → `pick_highlights.py` clusters bursts into events,
   auto-matches source video by filename prefix, writes `highlights.json`.
6. **Select** →
   - `top` mode: `final_pick.py` keeps strong events (total_cheer≥6s,
     n_events≥3, band≥0.70, not in first 15s) → `cut.py` + `assemble.py`.
   - `all` mode: `cut_all.py` + `assemble_all.py` (every candidate, batched).
7. **Assemble** → 0.3s xfade + PIL caption cards (auto-fade after 3.5s) +
   loudnorm −16 LUFS. `assemble_all` batches ≤40 segments then concat, and
   applies a final `alimiter` to keep True Peak < 0 dBTP. Cards use a
   low-saturation warm palette (warm-beige accent, warm-gray subtitle) so they
   sit naturally on night footage; `--grade` colors only the video layer.
8. **Optional BGM** (`--bgm`) → `bgm.py` synthesizes an original A-minor
   on-beat soundtrack (numpy, no external music assets, no licensing issues),
   places an impact + chord change at **every cut point**, then ducks the music
   under the crowd cheers and muxes with loudnorm. See `references/goal-review.md`
   for why the crowd layer must stay audible.

## Tuning knobs
- `--pre/--post` : clip length around the detected moment (default 5s/8s).
  For goal reels, prefer `pre≈8s` so the attacking build-up is visible —
  starting at `goal_est−3s` cuts in after the attack has already reached the
  box and viewers report "no beginning". See `references/goal-review.md`.
- `--top N` : how many strong highlights to keep.
- `--mode all` : skip filtering entirely (user wants every candidate).
- `gate` in `detect2.py` (93rd-pctile by default) : lower = more sensitive.
- Strong-event thresholds in `final_pick.py` : relax to catch more.
- `--bgm` + `--bgm-field-gain` / `--bgm-music-gain` / `--bgm-duck` : soundtrack
  balance. Defaults `1.35 / 0.58 / 0.60` keep music clearly audible (it lands
  ~4.3 dB under the total mix) while cheers still lead. **Do not go back to
  `0.40 / 0.80`** — that buried the music at ~-35 dB and users reported "there
  is no music at all". `bgm.py` now prints the measured music level and warns
  below -8 dB.
- `--fps` on `cut*.py` / `assemble*.py` : 0 = keep the source frame rate
  (default). Forcing 30 on 24fps footage duplicates frames and makes fast pans
  judder.
- `--grade` : optional ffmpeg color filter applied **only to the footage**, not
  to caption cards. Night LED pitches typically read ~`R-B=-8` in highlights;
  `eq=gamma_r=1.026:gamma_b=0.984:saturation=0.96` brings that to ~`-2.7`
  without shifting brightness. Avoid `colortemperature` at 5800K — it overshoots
  to `R-B=+11` (yellow) and darkens midtones.

## Scripts
| script | role |
|---|---|
| `run_pipeline.py` | one-shot end-to-end entry |
| `feats.py` | streaming audio feature extractor |
| `detect2.py` | cheer detector (local z-score) |
| `pick_highlights.py` | merge bursts → events, match source video |
| `final_pick.py` | strong-event filter |
| `cut.py` / `cut_all.py` | cut clips (selected / all) |
| `assemble.py` / `assemble_all.py` | assemble reel (selected / all) |
| `bgm.py` | on-beat generated soundtrack + cheer-ducking mix (`--bgm`) |
| `check_goal.py` | **is the ball in the net?** static-blob goalmasks detector — the only way to claim a goal |

## References
- `references/algorithm.md` — feature definitions, z-score scoring, merge &
  filter criteria, real-data distributions. Read before changing thresholds.
- `references/pitfalls.md` — OOM, threshold traps, xfade graph bug, batching,
  True Peak overflow, portable font/ffmpeg paths. Read before debugging.
- `references/goal-review.md` — **near-goal precondition** (analyse only the
  goal nearest the camera; re-identify it every run) plus **five goal
  verification criteria** (ball in net, players in front of goal, goalmouth
  errors, high-pitched reaction, **solo run with defenders giving up**), the
  `+1~+5s` timing offset, the `pre≈8s` build-up window, and why audio alone
  produces false positives. Read before claiming a candidate is a goal.
  Note criterion 5 inverts the "empty goalmouth = noise" heuristic — solo goals
  look empty precisely because the defence has given up, **but only on the near
  goal**; an empty far-goal mouth means the attack happened off-screen.

## Notes / environment
- Needs `ffmpeg`/`ffprobe` on PATH (or set `$FFMPEG`) and `python3` with
  `numpy scipy Pillow`.
- **This skill never tells you whether it was a goal.** Cheers locate moments;
  only `check_goal.py` + native-resolution eyeballing can label a goal. Measured
  on one 88-min match: 9 strong audio candidates → only 4 actual goals. Never
  put "goal" in a caption without a frame showing the ball inside the net.
- Random-seek frame extraction (`ffmpeg -ss`) is used only for spot-checking
  the picture — never full-volume decode of huge sources.
- The detector targets *crowd* reactions; single whistles / collisions /
  single shouts are mostly suppressed by the `n_events`/`band` filters but not
  perfectly — human review is expected. For "goal" requests, do the visual +
  audio cross-check in `references/goal-review.md`; a cheer with an empty
  goalmouth is usually off-screen noise, not a goal.
- **Do not review the far goal.** Crops/boxes, `check_goal.py` scans and
  native-resolution eyeballing apply to the near goal only. A cheer whose
  near-goal mouth stays empty is either a solo run (criterion 5) or an
  off-screen attack at the far goal — the latter is "audio hit, visually
  undecidable": never a goal, and never a whistle to be discarded as noise.
- `--bgm` needs only `numpy` (already required). It generates the soundtrack
  locally, so no music library or network service is needed. The music track
  can be replaced with `--music-out` output plus a re-mux if the user supplies
  their own song.
