# Changelog

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
