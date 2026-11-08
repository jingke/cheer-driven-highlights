# cheer-driven-highlights

A [WorkBuddy](https://www.workbuddy.cn) skill that detects crowd cheers, applause, or screams in long videos (sports matches, concerts, events) **from the audio track** and auto-cuts highlight reels — no manual scrubbing.

Works even when the footage is a fixed wide-angle camera with no visible audience and no commentary: audio is the locator. It can tell you *when* a cheer happened, but not from the picture whether it was a goal or a miss — human review of the reel is expected.

## What's inside

```
skills-cheer-driven-highlights/
├── SKILL.md                  # skill definition (triggers, workflow, tuning knobs)
├── scripts/                  # 10 decoupled scripts
│   ├── run_pipeline.py      # one-shot end-to-end orchestrator (--bgm)
│   ├── feats.py             # streaming audio feature extractor (OOM-safe)
│   ├── detect2.py           # cheer detector (local z-score, adaptive gate)
│   ├── pick_highlights.py   # merge bursts → events, match source video
│   ├── final_pick.py        # strong-event filter (goal/miss vs whistle/collision)
│   ├── cut.py / cut_all.py  # cut clips (selected / all)
│   ├── assemble.py / assemble_all.py  # xfade reel + caption cards + TP-safe loudnorm
│   └── bgm.py               # generated on-beat soundtrack + cheer-ducking mix
├── references/
│   ├── algorithm.md         # feature defs, z-score scoring, filter criteria, real distributions
│   ├── pitfalls.md          # OOM / threshold traps / xfade bug / batching / True Peak / portability
│   └── goal-review.md       # goal verification criteria (ball in net / players / errors / pitch)
└── assets/
```

## Install

Copy the skill folder into your WorkBuddy skills directory:

```bash
cp -R skills-cheer-driven-highlights ~/.workbuddy/skills/
```

Requires `ffmpeg`/`ffprobe` on PATH (or set `$FFMPEG`) and `python3` with `numpy scipy Pillow`.

## Quick start

```bash
python skills-cheer-driven-highlights/scripts/run_pipeline.py VIDEO_DIR --mode top --top 10
# full reel, every candidate, no filtering:
python skills-cheer-driven-highlights/scripts/run_pipeline.py VIDEO_DIR --mode all
# just produce the candidate list first, decide later:
python skills-cheer-driven-highlights/scripts/run_pipeline.py VIDEO_DIR --dry-run
# add a generated, on-beat soundtrack (ducked under the crowd cheers):
python skills-cheer-driven-highlights/scripts/run_pipeline.py VIDEO_DIR --mode top --top 10 --bgm
# optional natural color grade for night LED footage (footage only, cards unaffected):
python skills-cheer-driven-highlights/scripts/run_pipeline.py VIDEO_DIR --mode top --top 10 \
  --bgm --grade "eq=gamma_r=1.026:gamma_b=0.984:saturation=0.96"
```

`--bgm` synthesizes an original soundtrack locally with numpy — no music library,
no network service, no licensing concerns. Every cut point gets an impact and a
chord change, and the music automatically ducks when the crowd erupts.

See `skills-cheer-driven-highlights/SKILL.md` for the full workflow and tuning
knobs, and `references/goal-review.md` for verifying whether a cheer is actually
a goal (audio alone produces false positives).
