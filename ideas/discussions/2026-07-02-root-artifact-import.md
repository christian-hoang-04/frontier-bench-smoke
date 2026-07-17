# Root Artifact Import

Date: 2026-07-02

## What Was Discussed

Reviewed loose benchmark artifacts that had been sitting at the `D:\projects` root and verified whether they belonged to this project or to the more generic `personal/kaggle-agent-compute` infrastructure workspace.

## Decisions Made

- Treated the frontier benchmark task JSON files and the captured audio-probe run JSON as `frontier-bench-smoke` artifacts, not as generic Kaggle compute infrastructure artifacts.
- Imported those files into `execution/results/root_runs/imported_root_cleanup_2026-07-02/` instead of overwriting same-named files already present under the normal `audio_probe/`, `smoke/`, and `audio_vimedcss/` result folders.
- Kept the imported files grouped under an explicit cleanup folder so their provenance stays clear.

## Open Questions

- Decide later whether the imported root-cleanup files should be merged into the canonical result folders, kept only as provenance snapshots, or removed after manual comparison.
- Decide whether future ad hoc benchmark runs should default to `execution/results/root_runs/<task>/` immediately so they never appear at the workspace root.

## Next Actions

- When comparing historical task definitions, use the imported cleanup folder as the root-origin snapshot.
- Keep future frontier benchmark artifacts inside `execution/results/`.

## Important User Preferences

- Keep durable progress in project notes and handoff files.
- Avoid loose project artifacts at the `D:\projects` root.
