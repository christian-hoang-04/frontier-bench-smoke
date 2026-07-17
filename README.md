# Frontier Bench Smoke

Small, repeatable frontier-model checks built around Kaggle Benchmarks.

This repo is mainly for three things:

- fast local smoke tests for model availability and instruction-following
- local audio probes for transcription paths
- a hosted ViMedCSS ASR benchmark that can be pushed and rerun on Kaggle

## Repo Layout

- `execution/benchmarks/smoke/`
  - deterministic text smoke benchmark
- `execution/benchmarks/text_probe/`
  - text-only probe scripts, including token/cost inspection
- `execution/benchmarks/audio_probe/`
  - minimal audio probe for model and transport validation
- `execution/benchmarks/audio_vimedcss/`
  - hosted or local ViMedCSS ASR benchmark
- `execution/benchmarks/audio_meddies_small_test/`
  - local Meddies small-test diarized ASR benchmark
- `execution/data/bundles/vimedcss_audio_bundle_20/`
  - local 20-clip ViMedCSS bundle used by the ASR benchmark
- `execution/analysis/`
  - analysis helpers and retained report outputs
- `ideas/`
  - project notes, rules, and debugging history

## Prerequisites

This repo assumes you already have a working Kaggle Benchmarks environment.

- Python with the packages used by the scripts:
  - `kaggle_benchmarks`
  - `kaggle`
  - `pandas`
  - `pyarrow`
- Kaggle CLI logged in
- Kaggle Benchmarks auth available

## Setup

1. Clone the repo.
2. Copy `.env.example` to `.env`.
3. Refresh model-proxy credentials into `.env`:

```powershell
kaggle benchmarks auth -y --env-file .env
```

4. Before `tasks push` or `tasks run`, export the current OAuth token in the active shell:

```powershell
$env:KAGGLE_API_TOKEN=(kaggle auth print-access-token | Select-Object -First 1).Trim()
```

5. On Windows, use UTF-8 for CLI output when needed:

```powershell
$env:PYTHONUTF8="1"
```

## Quick Start

### 1. Text smoke benchmark

Runs a deterministic multi-sample check against the models exposed in your Kaggle Benchmarks environment.

```powershell
python execution/benchmarks/smoke/frontier_bench_smoke.py
```

Outputs are written to the current working directory:

- `frontier_bench_samples_summary.json`
- `frontier_bench_sample_responses.jsonl`
- `frontier_bench_smoke_availability.json`

### 2. Audio probe

Use this first when you only want to confirm that audio prompting works.

```powershell
python execution/benchmarks/audio_probe/frontier_audio_probe_benchmark.py
```

Optional override:

```powershell
$env:FRONTIER_AUDIO_FIXTURE_B64="<base64-audio>"
```

### 3. Local Meddies small-test smoke

Start with one row before attempting the full local run.

```powershell
$env:MEDDIES_SMALL_TEST_LIMIT="1"
python execution/benchmarks/audio_meddies_small_test/frontier_audio_meddies_small_test_bench.py
```

Useful overrides:

```powershell
$env:MEDDIES_SMALL_TEST_PARQUET_PATH="D:\path\to\test-00000.parquet"
$env:FRONTIER_AUDIO_MEDDIES_SMALL_TEST_MODEL="google/gemini-3.5-flash"
```

### 4. Local ViMedCSS ASR benchmark

Uses the bundled 20-clip sample set in this repo unless you override the bundle path.

```powershell
python execution/benchmarks/audio_vimedcss/frontier_audio_vimedcss_bench.py
```

Optional overrides:

```powershell
$env:VIMEDCSS_AUDIO_BUNDLE_DIR="D:\path\to\vimedcss_audio_bundle_20"
$env:FRONTIER_AUDIO_VIMEDCSS_MODEL="google/gemini-3.5-flash"
```

### 5. Hosted ViMedCSS task push and rerun

Keep the attached dataset on every push:

- dataset slug: `lehoangnam/vimedcss-audio-bundle-20`

Push:

```powershell
kaggle benchmarks tasks push frontier-audio-vimedcss-bench -f execution/benchmarks/audio_vimedcss/frontier_audio_vimedcss_bench.py -d lehoangnam/vimedcss-audio-bundle-20
```

Run a single model:

```powershell
kaggle benchmarks tasks run frontier-audio-vimedcss-bench -m gemini-3.5-flash
```

Check status:

```powershell
kaggle benchmarks tasks status frontier-audio-vimedcss-bench
```

Read logs:

```powershell
kaggle benchmarks tasks log frontier-audio-vimedcss-bench -m gemini-3.5-flash
```

Download artifacts:

```powershell
kaggle benchmarks tasks download frontier-audio-vimedcss-bench -m gemini-3.5-flash
```

## Current Known Good Baseline

- hosted task: `frontier-audio-vimedcss-bench/13`
- model: `google/gemini-3.5-flash`
- result: `20/20` completed
- mean WER: `0.101505`
- mean CER: `0.0721`

Task URL:

- `https://www.kaggle.com/benchmarks/tasks/lehoangnam/frontier-audio-vimedcss-bench/13`

## Notes

- Scripts resolve the project root automatically from nested locations.
- The Meddies small-test script reconfigures stdout/stderr to UTF-8 on Windows.
- Generated runs, caches, and credentials are intentionally not tracked in git.
- Durable context for the next session lives in `handoff.md` and `ideas/FOUNDATION.md`.
