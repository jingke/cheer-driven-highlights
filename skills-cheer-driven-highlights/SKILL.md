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

## Quick Start
```bash
# Use the isolated venv python (has numpy/scipy/PIL)
python scripts/run_pipeline.py VIDEO_DIR --mode top --top 10
# full reel, every candidate, no filtering:
python scripts/run_pipeline.py VIDEO_DIR --mode all
# just produce the candidate list first, decide later:
python scripts/run_pipeline.py VIDEO_DIR --dry-run
```
Outputs land in `./cheer_out/` (reel + `clips/` or `clips_all/`).

## Workflow
1. **Probe** video dir → list videos (mp4/mov/mkv/avi).
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
   applies a final `alimiter` to keep True Peak < 0 dBTP.

## Tuning knobs
- `--pre/--post` : clip length around the detected moment (default 5s/8s).
- `--top N` : how many strong highlights to keep.
- `--mode all` : skip filtering entirely (user wants every candidate).
- `gate` in `detect2.py` (93rd-pctile by default) : lower = more sensitive.
- Strong-event thresholds in `final_pick.py` : relax to catch more.

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

## References
- `references/algorithm.md` — feature definitions, z-score scoring, merge &
  filter criteria, real-data distributions. Read before changing thresholds.
- `references/pitfalls.md` — OOM, threshold traps, xfade graph bug, batching,
  True Peak overflow, portable font/ffmpeg paths. Read before debugging.

## Notes / environment
- Needs `ffmpeg`/`ffprobe` on PATH (or set `$FFMPEG`) and `python3` with
  `numpy scipy Pillow`.
- Random-seek frame extraction (`ffmpeg -ss`) is used only for spot-checking
  the picture — never full-volume decode of huge sources.
- The detector targets *crowd* reactions; single whistles / collisions /
  single shouts are mostly suppressed by the `n_events`/`band` filters but not
  perfectly — human review is expected.
