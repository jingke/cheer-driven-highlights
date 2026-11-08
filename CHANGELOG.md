# Changelog

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
