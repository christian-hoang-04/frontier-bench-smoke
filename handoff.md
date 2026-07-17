# Frontier Bench Smoke Handoff

Current goal: keep a durable Kaggle Benchmarks audio task for ViMedCSS and preserve the latest clean Gemini ASR comparison.

Current status:
- Personal project path is `D:\projects\personal\frontier-bench-smoke`.
- Project root was reorganized so only durable top-level files remain:
  - `.env`
  - `README.md`
  - `handoff.md`
  - `ideas/`
  - `execution/`
- Latest hosted audio benchmark task is `frontier-audio-vimedcss-bench/13`:
  - `https://www.kaggle.com/benchmarks/tasks/lehoangnam/frontier-audio-vimedcss-bench/13`
- Prior clean comparison task remains `frontier-audio-vimedcss-bench/11`:
  - `https://www.kaggle.com/benchmarks/tasks/lehoangnam/frontier-audio-vimedcss-bench/11`
- The task mounts a private Kaggle dataset containing the 20 WAV clips:
  - dataset slug: `lehoangnam/vimedcss-audio-bundle-20`
- The task now:
  - avoids `__file__` notebook crashes
  - avoids expiring Hugging Face cached audio URLs
  - uses a top-level persisted benchmark task plus a non-persisted row task
  - retries transient `429` errors with exponential backoff
  - uses low-reasoning deterministic prompting for token efficiency
- Local Meddies small-test benchmark is now available:
  - `execution\benchmarks\audio_meddies_small_test\frontier_audio_meddies_small_test_bench.py`
  - reads local parquet with embedded audio bytes
  - prompts `google/gemini-3.5-flash` through the Kaggle model-proxy path
  - writes both raw and speaker-label-stripped WER/CER
  - reconfigures stdout/stderr to UTF-8 to avoid Windows transcript logging failures

Latest clean result artifacts:
- `execution\results\task_downloads\frontier-audio-vimedcss-bench\11\gemini-3.1-pro-preview\323456\frontier_audio_vimedcss_summary.json`
- `execution\results\task_downloads\frontier-audio-vimedcss-bench\11\gemini-3.5-flash\323457\frontier_audio_vimedcss_summary.json`
- `execution\results\task_downloads\frontier-audio-vimedcss-bench\13\gemini-3.5-flash\325605\frontier_audio_vimedcss_summary.json`
- `execution\results\root_runs\meddies_small_test_gemini_35_flash_diarized_20260705\frontier_audio_meddies_small_test_summary.json`
- `execution\results\root_runs\meddies_small_test_gemini_35_flash_diarized_smoke_retest_no_utf8_after_patch_20260706\frontier_audio_meddies_small_test_summary.json`

Latest clean results:
- `gemini-3.5-flash` task `13` run `325605`
  - `20/20` completed
  - mean WER `0.101505`
  - mean CER `0.0721`
- Meddies small-test full local run
  - `20/20` completed
  - mean raw WER `0.303295`
  - mean raw CER `0.277085`
  - mean stripped WER `0.262335`
  - mean stripped CER `0.224405`
- Meddies small-test smoke retest after UTF-8 patch
  - `1/1` completed
  - mean raw WER `0.2078`
  - mean raw CER `0.2083`
  - mean stripped WER `0.122`
  - mean stripped CER `0.094`
- `gemini-3.1-pro-preview` run `323456`
  - `20/20` completed
  - mean WER `0.08936`
  - mean CER `0.06116`
- `gemini-3.5-flash` run `323457`
  - `20/20` completed
  - mean WER `0.098195`
  - mean CER `0.071635`

Important user preferences:
- Keep this work in the personal workspace.
- Use T4x2-compatible hosted ASR benchmarking rather than blocked frontier-budget paths.
- Keep durable progress in project notes and handoff files.
- No report UI is needed right now.

Key local artifacts:
- `execution\benchmarks\audio_vimedcss\frontier_audio_vimedcss_bench.py`
- `execution\benchmarks\audio_meddies_small_test\frontier_audio_meddies_small_test_bench.py`
- `execution\benchmarks\smoke\frontier_bench_smoke.py`
- `execution\data\bundles\vimedcss_audio_bundle_20\benchmark_rows.json`
- `execution\data\bundles\vimedcss_audio_bundle_20\audio\clip_*.wav`
- `execution\results\root_runs\audio_vimedcss\...`
- `execution\results\task_downloads\frontier-audio-vimedcss-bench\...`
- `ideas\discussions\2026-06-30-frontier-audio-support-debugging.md`

Project structure summary:
- `execution\benchmarks\`
  - runnable Kaggle benchmark entrypoints
- `execution\data\`
  - local bundles and manifests
- `execution\fixtures\`
  - local test fixtures
- `execution\references\`
  - local reference material
- `execution\results\`
  - retained run files, downloads, and legacy stored task trees
- `execution\scratch\`
  - caches, temp kernels, and disposable audio scratch files

Core risks:
- `MODEL_PROXY_*` credentials still expire and may need refresh with `kaggle benchmarks auth`.
- Kaggle task push/run calls may also require exporting the current OAuth token into `KAGGLE_API_TOKEN` in the active shell:
  - PowerShell: `$env:KAGGLE_API_TOKEN=(kaggle auth print-access-token | Select-Object -First 1).Trim()`
- Kaggle CLI on Windows may need `PYTHONUTF8=1` to avoid console encoding failures.
- Future runs can still hit provider-side load issues, but the current benchmark task now retries transient `429` errors.

Recommended next session:
- Start from the task version `13` for Gemini 3.5 Flash-only reruns, or version `11` for the earlier comparison baseline.
- If testing more models, reuse the same task instead of rewriting the benchmark.
- If publishing later, confirm whether the attached private audio dataset should remain private or be published separately.

Standard process for this project:
- Refresh `kaggle benchmarks auth` before any hosted ASR run.
- Refresh `kaggle benchmarks auth` before local model-proxy audio runs too.
- Export `KAGGLE_API_TOKEN` from `kaggle auth print-access-token` before `kaggle benchmarks tasks push` or `run`.
- Use local probes first when debugging transport or model exposure issues.
- For Meddies diarization checks, start with `MEDDIES_SMALL_TEST_LIMIT=1` before full 20-row runs.
- Preserve dataset attachment `lehoangnam/vimedcss-audio-bundle-20` on every push.
- For targeted validation, run only the requested model instead of re-running the whole comparison set.
- Download new artifacts into `execution\results\task_downloads\frontier-audio-vimedcss-bench\...`.

HF duration-analysis status:
- Restricted HF dataset inspected without downloading repo payloads:
  - `https://huggingface.co/datasets/Meddies/Meddies-ASR-Raw-Audios/tree/main`
- Method that worked:
  - authenticated `HfFileSystem().glob(...)` to enumerate nested WAVs per source
  - authenticated HTTP range reads of the first ~512 bytes per WAV
  - parse RIFF/WAVE header to compute duration from `data_size / byte_rate`
  - use low concurrency plus retry/backoff to survive HF `429` limits
- Verified twice with matching results:
  - remote WAV files: `6633`
  - total seconds: `8520147.71775`
  - total hours: `2366.707699`
- Verified remote per-source counts/durations:
  - `CafeF`: `1`, `29.205313s`
  - `Duong_Hay_Xam`: `29`, `88588.266562s`
  - `HTV_Tin_Tuc`: `3427`, `3534094.189312s`
  - `Khanh_Vy_Official`: `22`, `27187.264s`
  - `Spiderum_Podcast`: `11`, `28777.258687s`
  - `The_First_Step`: `11`, `25101.33125s`
  - `The_Tri_Way`: `54`, `135386.258188s`
  - `VIETSUCCESS`: `408`, `1364364.020125s`
  - `VTV10`: `533`, `430836.373375s`
  - `VTV4`: `1122`, `600849.857438s`
  - `Vat_Vo_Studio_Podcasts`: `1`, `1644.778687s`
  - `Vietcetera`: `975`, `2156766.845438s`
  - `unlock_fm`: `39`, `126522.069375s`
- Important caveat for future work:
  - current HF remote counts do not match the user’s local manifest counts for several channels
  - if durations need to be inserted into an older local JSON, record that those durations come from current HF `main`, not necessarily from the same snapshot as the local counts
HF analysis report publication:
- Published HF analysis report paths:
  - `analysis/meddies_hf_duration_report.md`
  - `analysis/meddies_hf_duration_report.json`
- Upload commit refs:
  - `b794ee5dcdfae1dbbf46938ede22587c44d7397b`
  - `869af8f9c07c0e196fa59c93159458e5446f945d`
- Current quality status:
  - remote markdown and JSON analysis files downloaded back cleanly after upload
  - report quality in the HF repo looks fine; no further reconciliation work is needed unless the dataset changes
