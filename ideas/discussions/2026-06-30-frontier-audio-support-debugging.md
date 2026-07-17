## Summary

This note records the current state of debugging frontier-model audio benchmarking in `personal/frontier-bench-smoke`.

We confirmed that Kaggle Benchmarks SDK has first-class audio input support via `audio=` and that this support was merged upstream in April 2026. Despite that, our custom frontier audio tasks are still failing in practice in two distinct ways:

- task creation notebooks for custom probe benchmarks fail on Kaggle even when reduced to minimal examples
- local direct `audio=` prompting against the model proxy reaches the send boundary but returns `APIConnectionError: Connection error.`

The current working benchmark path is ASR-only on T4x2, not frontier-model audio.

## Decisions

- Treat frontier-model audio support as unresolved infrastructure/runtime behavior, not a missing SDK feature.
- Do not rely on the "audio as video" workaround as a primary benchmark path. It may drop soundtrack audio if the provider path is effectively frame-only.
- Keep the T4x2 ASR benchmark as the reliable path for current ViMedCSS testing.

## Evidence

- Public task created successfully:
  - `https://www.kaggle.com/benchmarks/tasks/lehoangnam/frontier-bench-smoke/1`
- Public audio task slugs exist but creation failed:
  - `https://www.kaggle.com/benchmarks/tasks/lehoangnam/frontier-audio-vimedcss-bench/4`
  - `https://www.kaggle.com/benchmarks/tasks/lehoangnam/frontier-audio-probe-benchmark/3`
  - `https://www.kaggle.com/benchmarks/tasks/lehoangnam/frontier-text-probe-benchmark/1`
- Local probe behavior:
  - `frontier_audio_probe_benchmark.py` reaches `llm.prompt(..., audio=audios.from_path(...))`
  - returned error: `APIConnectionError: Connection error.`
- Upstream roadmap signal:
  - Kaggle `kaggle-benchmarks` PR `#121` "Add audio modality input support" was merged on 2026-04-10
  - PR body states: "The changes on modelproxy side are already merged to support this."

## Open Questions

- Why do minimal custom task creation notebooks fail on Kaggle even when stripped down to simple direct `.run(...)` patterns?
- Why does local model-proxy execution fail on `audio=` if upstream SDK and model-proxy support are claimed merged?
- Is there a provider-specific restriction for frontier models, even if generic audio transport exists in the SDK?

## Next Actions

- Build one last minimal quick-start-style control pair:
  - text-only single-task direct `.run(...)`
  - audio single-task direct `.run(...)`
- If text creates and audio fails, treat it as isolated audio benchmark support gap.
- If both fail, inspect Kaggle task-creation environment assumptions rather than modality handling.
- Contact Kaggle support or open a public GitHub issue with:
  - failing task URLs
  - minimal local repro
  - exact `APIConnectionError`
  - note that upstream PR `#121` says audio and model-proxy support were merged

## Important User Preferences

- Prefer making the benchmark runnable without relying on personal API keys.
- Skip frontier budget path if it blocks progress; use T4x2 compute for reliable ASR evaluation.
- Save durable progress in project notes so future agents can restart without reconstructing the debugging history.

## 2026-06-30 Patch Follow-Up

- Replaced `frontier_audio_probe_benchmark.py` with a minimal direct `.run(...)` smoke task modeled after Kaggle PR `#121`.
- The new probe uses Kaggle's public `speech.mp3` fixture and the same `"Transcribe this audio exactly."` pattern used in upstream tests.
- Added an env override `FRONTIER_AUDIO_FIXTURE_B64` so the probe can later be switched to self-contained inline audio without changing code.
- Updated `frontier_audio_vimedcss_bench.py` so audio inputs can be either HTTP URLs or local mounted paths, matching the upstream `from_url` and `from_path` support surface more closely.
- Vendored the PR `#121` speech fixture into `fixtures/pr121_speech.mp3.b64` and updated the probe to prefer the local fixture over external fetches.

## 2026-06-30 Test Result

- Local test outcome:
  - with the PR `#121` speech fixture injected inline and model-proxy socket access allowed, `frontier_audio_probe_benchmark.py` succeeded
  - model used: `google/gemini-3-flash-preview`
  - transcription returned: `The quick brown fox jumps over the lazy dog.`
- Local non-escalated runs can still fail with `APIConnectionError: Connection error.` due this environment's socket restrictions, which is separate from benchmark logic.
- Remote Kaggle task creation outcome after vendoring the fixture:
  - `frontier-audio-probe-benchmark/4` failed creation
  - `frontier-audio-probe-benchmark/5` also failed creation
- Interpretation:
  - the patched `audio=` path itself is valid and can work end-to-end locally
  - the remaining blocker is Kaggle custom task creation, not the basic PR `#121` audio prompt shape

## 2026-06-30 Later Root Cause and Status

- We later confirmed the broader task-creation failure was caused by benchmark entrypoints assuming `__file__` exists.
- Kaggle converts pushed `.py` files into notebooks for task creation, and notebook execution does not define `__file__`.
- Fix applied across the benchmark entrypoints:
  - use `Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()`
  - guard `.env` loading when the file is absent
- Verified task-creation recovery:
  - `frontier-text-direct-probe/3` created successfully
  - `frontier-audio-probe-benchmark/8` created successfully
- Full ViMedCSS task status:
  - `frontier-audio-vimedcss-bench/5` first failed with `KERNEL_WITHOUT_RUN` because the file ended before any `.run()` / `.evaluate()` entrypoint
  - after adding a self-contained evaluation entrypoint, `frontier-audio-vimedcss-bench/6` now fails during notebook execution instead of at startup
  - local reproduction showed the embedded Hugging Face cached audio URLs are stale and fail fetches, so the remaining ViMedCSS blocker is durable audio sourcing rather than Kaggle task bootstrapping itself

## 2026-06-30 Final Working State

- Durable audio sourcing was fixed by extracting the 20 target ViMedCSS clips into a local bundle and uploading them as a Kaggle dataset:
  - dataset slug: `lehoangnam/vimedcss-audio-bundle-20`
  - local bundle path: `D:\projects\personal\frontier-bench-smoke\vimedcss_audio_bundle_20`
- `frontier_audio_vimedcss_bench.py` was rewritten to:
  - mount audio from the Kaggle dataset instead of using expiring Hugging Face cached URLs
  - use a non-persisted inner row task and a persisted top-level benchmark task
  - write only JSON-serializable summary content
  - retry transient `429` / rate-limit failures with exponential backoff
  - force low-reasoning, deterministic prompting for token efficiency
- Working task version:
  - `https://www.kaggle.com/benchmarks/tasks/lehoangnam/frontier-audio-vimedcss-bench/11`
- Final benchmark results on the 20-sample ViMedCSS task:
  - `gemini-3.1-pro-preview` run `323456`
    - completed: `20/20`
    - mean WER: `0.08936`
    - mean CER: `0.06116`
  - `gemini-3.5-flash` run `323457`
    - completed: `20/20`
    - mean WER: `0.098195`
    - mean CER: `0.071635`
- Conclusion from the clean run:
  - `gemini-3.1-pro-preview` outperformed `gemini-3.5-flash` on both WER and CER for this 20-sample set

## 2026-06-30 HF Remote Duration Analysis

- User asked for duration analysis of the restricted HF dataset repo without downloading the repo payload:
  - `https://huggingface.co/datasets/Meddies/Meddies-ASR-Raw-Audios/tree/main`
- Important finding:
  - top-level tree inspection was misleading because some channel folders required deeper source-level recursive listing
  - authenticated `HfFileSystem().glob("datasets/.../**/*.wav")` was needed to enumerate nested WAVs correctly
- Duration method used:
  - do not clone or pull the repo
  - authenticate with the already-available local HF login
  - enumerate WAV paths remotely
  - fetch only the first ~512 bytes of each WAV via authenticated HTTP range requests
  - parse RIFF/WAVE header fields (`byte_rate`, `data_size`) to derive duration
  - add retry/backoff for HF `429` rate limits
- A full first pass and a second independent verification pass both matched exactly.
- Verified current HF remote totals:
  - remote WAV files: `6633`
  - total duration seconds: `8520147.71775`
  - total duration hours: `2366.707699`
  - zero-duration files: `0`
  - duration-parse errors: `0`
- Verified current HF remote per-source durations:
  - `CafeF`: `1` file, `29.205313` seconds, `0.008113` hours
  - `Duong_Hay_Xam`: `29` files, `88588.266562` seconds, `24.607852` hours
  - `HTV_Tin_Tuc`: `3427` files, `3534094.189312` seconds, `981.69283` hours
  - `Khanh_Vy_Official`: `22` files, `27187.264` seconds, `7.552018` hours
  - `Spiderum_Podcast`: `11` files, `28777.258687` seconds, `7.993683` hours
  - `The_First_Step`: `11` files, `25101.33125` seconds, `6.972592` hours
  - `The_Tri_Way`: `54` files, `135386.258188` seconds, `37.607294` hours
  - `VIETSUCCESS`: `408` files, `1364364.020125` seconds, `378.990006` hours
  - `VTV10`: `533` files, `430836.373375` seconds, `119.67677` hours
  - `VTV4`: `1122` files, `600849.857438` seconds, `166.902738` hours
  - `Vat_Vo_Studio_Podcasts`: `1` file, `1644.778687` seconds, `0.456883` hours
  - `Vietcetera`: `975` files, `2156766.845438` seconds, `599.101902` hours
  - `unlock_fm`: `39` files, `126522.069375` seconds, `35.145019` hours
- Important caveat:
  - these verified numbers describe the current HF repo state
  - they do not exactly match the user’s larger local JSON counts for several sources
  - example mismatches observed:
    - `HTV_Tin_Tuc`: local `4416` vs current HF remote `3427`
    - `VIETSUCCESS`: local `675` vs current HF remote `408`
    - `Vietcetera`: local `945` vs current HF remote `975`
  - so the remote duration values are trustworthy for current HF `main`, but should not be blindly joined onto an older or different local manifest without noting the count mismatch
## 2026-07-01 HF Analysis Report Published

- The duration results were published into the HF dataset repo under:
  - `analysis/meddies_hf_duration_report.md`
  - `analysis/meddies_hf_duration_report.json`
- Upload commit refs:
  - `b794ee5dcdfae1dbbf46938ede22587c44d7397b`
  - `869af8f9c07c0e196fa59c93159458e5446f945d`
- Remote quality check passed:
  - both uploaded files downloaded back cleanly from the HF repo
  - markdown report and JSON payload were readable as expected
- User preference captured:
  - do not spend more time reconciling HF-vs-local count mismatches if the HF repo report itself looks correct

## 2026-07-01 Project Folder Reorganization

- Reorganized the project in place without moving the project root itself.
- New stable layout:
  - `execution/benchmarks/`
  - `execution/data/`
  - `execution/fixtures/`
  - `execution/references/`
  - `execution/results/`
  - `execution/scratch/`
  - `execution/analysis/`
- Benchmark scripts were moved out of the project root and patched to:
  - resolve project root automatically from nested locations
  - keep using project-root `.env`
  - keep writing generated run outputs to the current working directory
- The local ViMedCSS bundle was normalized so the canonical audio files now live under:
  - `execution/data/bundles/vimedcss_audio_bundle_20/audio/`
- The project root now only holds durable project-level files plus `ideas/` and `execution/`.
