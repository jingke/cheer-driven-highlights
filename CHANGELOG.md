# Changelog

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
