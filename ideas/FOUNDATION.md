# Frontier Bench Smoke Foundation

## Purpose

This project is the personal working area for lightweight frontier-model and ASR benchmark experiments, especially Kaggle Benchmarks tasks and ViMedCSS-oriented audio evaluation.

## Stable Rules

- Keep the project rooted at `D:\projects\personal\frontier-bench-smoke`.
- Use `ideas/` for reasoning, discussion records, and durable project memory.
- Use `execution/` for benchmark code, datasets, fixtures, results, analysis, and scratch artifacts.
- Prefer benchmark implementations that work without personal provider API keys when a hosted or platform-native path exists.
- Preserve durable restart context in `handoff.md` and dated discussion notes.
- Treat `execution/results/` as the artifact area and avoid dropping new run files at the project root.
- Refresh both auth layers before hosted work:
  - `kaggle benchmarks auth` for model-proxy access
  - `kaggle auth print-access-token` exported as `KAGGLE_API_TOKEN` for task push/run calls
- Keep Kaggle task pushes on the same durable slug unless the benchmark meaning changes materially.
- Keep the attached Kaggle dataset explicit on every push so dataset attachment is not dropped accidentally.
- Prefer single-model reruns when the user asks for a targeted validation rather than a broad comparison pass.

## Current Working Benchmark Path

- Main reliable path: `execution/benchmarks/audio_vimedcss/frontier_audio_vimedcss_bench.py`
- Current Gemini 3.5 Flash-only task version: `frontier-audio-vimedcss-bench/13`
- Current comparison baseline task version: `frontier-audio-vimedcss-bench/11`
- Current clean comparison baseline is between:
  - `gemini-3.1-pro-preview`
  - `gemini-3.5-flash`

## Standard Run Flow

1. Refresh auth and enable UTF-8-safe console behavior on Windows.
2. Validate the smallest relevant local smoke path before a hosted rerun.
3. Push a new task version only when code or task behavior changed.
4. Wait for task creation to complete before starting a model run.
5. Run only the requested model unless the task is explicitly a comparison benchmark.
6. Download hosted artifacts into `execution/results/task_downloads/`.
7. Update `handoff.md` with the new task URL, run ID, and summary metrics.

## Organization Intent

- `execution/benchmarks/` contains runnable task entrypoints only.
- `execution/data/` contains local bundles and manifests.
- `execution/results/` contains retained benchmark outputs.
- `execution/scratch/` contains disposable caches and temporary artifacts.
- `execution/analysis/` contains reports prepared for external publication or review.
