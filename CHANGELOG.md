# Changelog

## v1.3.8 (2026-11-18)

- **8-frame confirmation gate for final selection** (`pitfalls.md` §14 supplement) —
  the 3-frame pre-screen window (`goal_est+[1,3,5]`) is too narrow and missed
  goals visible in other frames: a 3-clip result was found to omit 6 of a
  previous 9-clip set. Final candidates must pass an 8-frame sequence review
  (`goal_est+[-2..+5]`, 1s step) and the review pool must be the union of
  pre-screen top-30 and high deep-review scores, not just the pre-screen top.
- **Batch slicing with per-clip probe** — slicing 9 clips in one run hit SIGTERM
  (exit 137) and left a corrupt `moov atom not found` file. Slice in batches
  of ≤3 and probe each clip's duration (~15.0s); re-cut corrupt ones via `cut_one()`.

## v1.3.7 (2026-11-18)

- **Pre-screen before slicing** (`references/pitfalls.md` §14, expert notes) —
  all-mode slicing of 117 candidates took >10 min without finishing and
  produced false positives such as a corner-kick setup (`band=0.073`). New
  workflow: random-seek 3 frames per candidate at `goal_est+[1,3,5]`
  (351 frames / 3m37s measured), small-size numpy blob score for rough ranking
  only, then contact-sheet visual review to pick real ball-in-goal-area frames.
  Result: 117 → 3 clips, ~97% reduction, an order of magnitude faster than
  full slicing. Explicitly warns that the blob score is NOT a verdict (the
  highest scorer was two players with no ball visible).

## v1.3.6 (2026-11-18)

- **Clip filenames use in-video timestamps** — `cut.py` / `cut_all.py` now name
  clips `hl###_<src>_<hh>_<mm>_<ss>.mp4` (and `hl###_<grade>_<src>_<hh>_<mm>_<ss>.mp4`
  in all-mode) instead of raw seconds, so names map directly onto the player
  timeline and stay correct past one hour. Computed via
  `hh,rem = divmod(int(goal_est),3600)` then `mm,ss = divmod(rem,60)`, zero-padded.
  Examples: 2791s → `00_46_31`, 5238s → `01_27_18`.
  Expert Phase 5 documents the convention.

## v1.3.5 (2026-11-18)

- **Goal-extent-first hard gate** — expert G0a and `goal-review.md` now require
  marking the goal's exact bounds on a native-resolution frame **before any goal
  or shot judgement**: `GOAL_RECT` (outer posts + crossbar) and `NET_BOX` (valid
  goal area, explicitly excluding the grass in front). All "ball resting / ball
  in net / net shake" evidence must fall inside `NET_BOX`; balls outside the
  posts, behind the goal line, or in front of the goal never count. If the box
  cannot be fully drawn or the ball stays <20px after zoom, the segment is
  declared unresolvable and no goal verdict is made. Review workflow gained
  this as step 2, ahead of audio scoring. G0 picks *which* goal, G0a fixes its
  *exact boundary*; both required before G1–G7.

## v1.3.4 (2026-11-18)

- **Net-shake promoted to a standalone goal condition** — `goal-review.md` and
  expert G1 now treat a localized net dimple/oscillation (0.2–1s, sudden, with
  rebound) as direct physical evidence of a ball hitting the net, valid on its
  own for goal-behind cameras. Explicit false-positive exclusions added: wind
  (whole net sways slowly), player/keeper contact (limb visible at contact
  point), and camera shake (entire frame including posts moves together).
  G1 expanded from four to five conditions; goal-review criteria from five to
  six (new #6, cross-referenced to the goal-behind chapter, top-down only where
  the net is large enough to observe deformation).

## v1.3.3 (2026-11-18)

- **Goal-behind camera editing guide** (`references/goal-review.md`) — a new
  dedicated chapter systematises the camera-behind-goal workflow that was
  previously scattered across pitfalls §11–12 and work logs: camera recognition
  (net in foreground, far goal invisible), four-tier goal evidence specific to
  this view (ball growing toward camera → net impact → ball resting in net →
  keeper retrieving), why `check_goal.py` three-frame intersection fails here
  (median net-box noise 2493 px), the 8fps dense-window + vectorized-blob
  fallback, `pre≈8` slicing rationale, and honest chance/shot labelling when
  no net impact is visible.
- Expert G0 now routes goal-behind cameras to that chapter instead of relying
  on the top-down heuristics. No behavioural change for standard top-down
  footage.

## v1.3.2 (2026-11-17)

- **No-crowd guard** (`references/goal-review.md`) — the audio-locator premise
  collapses on empty-stadium matches. A new pre-flight check requires confirming
  spectators/crowd cheers before trusting audio scores. Measured on an 87-min
  empty-stand match: 209+84 audio events, 117 candidates, and even band 0.81/0.92
  S-grade candidates showed completely calm native-resolution frames. When no
  crowd is present, visual review is mandatory and audio rank must never be
  reported as a goal.
- **Goal-behind camera caveats** (`references/pitfalls.md` §11–12) — the
  three-frame static-ball detector (`check_goal.py`) fails when the camera sits
  behind the goal (median net-box noise 2493 px vs ~0 top-down). Dense-window
  sampling replaced full-film 4fps scanning (2360 frames / 2 min vs 21k frames /
  >6 min), and a vectorized numpy scorer replaced `ndimage.label` which hit
  SIGTERM (exit 137) on 2360 frames.
- **Black first frame fix** (`references/pitfalls.md` §13, expert G5) — an
  opening `fade=t=in:st=0:d=0.2` on the video layer made frame 0 pure black
  (mean=0.0), causing black Finder/preview thumbnails. Remove the video-layer
  fade (measured frame-0 mean 0.0 → 91.5) and embed a `attached_pic` cover via
  `-c copy`. Enforced a delivery gate: frame-0 mean must be ≥10.
- Aligned `goal-highlight-editor` expert G5 with the above. No goal was claimed
  for the 11/16 footage; a 9-clip "chance" reel was delivered with honest labels.

## v1.3.1 (2026-11-12)

- **Experience write-back protocol** — the agent now persists reusable lessons
  instead of relying on manual iteration. `SKILL.md` and `references/pitfalls.md`
  define where each kind of finding goes (daily log, user-level MEMORY.md,
  pitfalls.md, goal-review.md, SKILL.md / CHANGELOG), require reproducible
  quantitative evidence, and gate promotion on three conditions: reproducible,
  evidenced, non-conflicting (single observations stay "pending reproduction";
  ≥2 occurrences graduate to rules).
- After any write-back: re-run `package_skill.py`, sync the repo copy, and for
  expert changes re-run `validate_expert.py` + `register_expert.py`. Never
  auto-commit or auto-push.
- Mirrored in the `goal-highlight-editor` expert MD as its "经验回写协议" section,
  paired with a weekly distillation automation.

## v1.3.0 (2026-11-12)

- **Near-goal precondition** — a fixed overhead camera covers only half the
  pitch plus one goal, while cheers are full-field. `SKILL.md` and
  `references/goal-review.md` now require analysing **only the goal nearest the
  camera** and **re-identifying that goal on every run** (larger goal rectangle,
  nearer the frame edge, wider posts). Teams swap ends at half-time, so the near
  goal changes; cross-half footage must be judged per segment. Visual criteria,
  review crops and `check_goal.py` scans apply to the near goal only; the far
  goal is marked "audio hit, visually undecidable". Reports must state the
  near-goal side and coverage up front.
- **Criterion 5 scope narrowed** — its inversion of "empty goalmouth = noise"
  holds **only on the near goal**. An empty far-goal mouth means the attack
  happened off-screen: reading it as noise deletes valid clips, reading it as a
  solo goal invents a false one. Motivation: after the half-time swap only 13 of
  51 candidates had any goalmouth event.
- Aligned with the `goal-highlight-editor` expert's G0 hard gate (same rule).
- Doc sync: folds in previously uncommitted `SKILL.md` updates (`--bgm` defaults
  `1.35/0.58/0.60`, `--fps 0`, `check_goal.py`, "audio never labels a goal") and
  the fifth criterion / `pre≈8s` guidance in `goal-review.md`. README script
  count and criterion description corrected.

## v1.2.0 (2026-11-08)

- **Natural color palette** — caption cards now use a low-saturation warm-beige
  accent (`#D6BA8A`) and warm-gray subtitle instead of the pure-red bar and pink
  text; the bottom gradient is lighter (180 vs 200). More natural on night footage,
  with unchanged text legibility.
- **Optional `--grade` color filter** (`run_pipeline.py`, `assemble.py`,
  `assemble_all.py`) — applied only to the footage layer, so caption cards keep
  their designed colors. Verified on a night LED pitch: measured highlight
  `R-B` went from `-7.1` to `-2.7`, saturation `0.212 → 0.180`, with the
  brightness percentiles unchanged (`p5/p50/p95 = 30.3/77.0/178.3`).
  `colortemperature=5800` was tested and rejected (overshoots to `R-B=+11`,
  darkens midtones).
- Rebuilt the 5-minute / 23-clip reel with the new palette and grade.

## v1.1.0 (2026-11-08)

- **Generated on-beat soundtrack (`bgm.py`, `--bgm`)** — synthesizes an original
  A-minor score locally with numpy (kick / snare / hat / bass / pad / arp / riser /
  impact), with an impact + chord change at every cut point. Needs no music assets,
  network service, or licensing. Outputs `高光集_配乐.mp4` / `全集_配乐.mp4`.
- **Cheer-ducking mix** — the crowd layer stays audible: `field*1.35 +
  music*0.40*duck`, where `duck` follows the field's 20ms RMS envelope
  (0.20–1.00). Measured correlation with the field rose from 0.213 to 0.500
  versus an early music-heavy mix that drowned the goal reaction.
  Tunable via `--bgm-field-gain` / `--bgm-music-gain` / `--bgm-duck`.
- **Goal verification guide (`references/goal-review.md`)** — four review
  criteria (ball in net, players in front of goal, goalmouth errors, high-pitched
  reaction), plus the measured `+1~+5s` offset between the cheer peak and the
  visible goalmouth event. Documents why `goal_est+1s` single-frame checks
  systematically misclassify real events as empty frames, and why very high
  spectral centroid usually means a whistle rather than a crowd.
- Validated on a 75.7-minute HEVC 1080p match with a separate 48 kHz PCM WAV,
  producing a 120.000s nine-clip reel.

## v1.0.0 (2026-10-11)

Initial release of the `cheer-driven-highlights` WorkBuddy skill.

- **Audio-driven detection** — streams a 16k mono WAV and extracts RMS / band / flatness / centroid / zero-cross-rate / baseline features without ever loading the whole file into memory (safe on 25GB+ sources).
- **Local z-score cheer scorer** with a 93rd-percentile adaptive gate. Distribution-agnostic: it worked on three distinct matches with no per-match threshold tuning.
- **Burst merging** (22s join) → candidate events → S/A/B/C grading.
- **Strong-event filter** (`final_pick.py`) to separate goals/misses from whistles/collisions: `total_cheer ≥ 6s`, `n_events ≥ 3`, `band ≥ 0.70`.
- **End-to-end orchestrator** `run_pipeline.py` with `--mode top|all`, `--dry-run`, `--skip-extract`, single-file or directory input.
- **Reel assembly** — 0.3s xfade + PIL caption cards (auto-fade) + True-Peak-safe `loudnorm`/`alimiter`.
- **Validated** across 3 distinct matches, covering single-file, two-file source matching, and the multi-batch (≥40 segments) assembly path.

### Known limitations

- Fixed wide-angle footage with no visible audience: audio locates *when* a cheer happened, not whether it was a goal or a miss — the reel still needs human review.
- `--mode all` intentionally keeps low-band segments (e.g. whistles); use `--mode top` to drop them.
