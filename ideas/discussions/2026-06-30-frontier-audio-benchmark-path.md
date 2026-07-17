# Frontier Audio Benchmark Path

## Summary

Created a clearer no-direct-API benchmark path for ViMedCSS audio evaluation inside `personal/frontier-bench-smoke`.

The benchmark file is:

```text
D:\projects\personal\frontier-bench-smoke\frontier_audio_vimedcss_bench.py
```

It now targets the exact requested Gemini models by logical target:

- `Gemini 3.5 Flash`
- `Gemini 3.1 Pro`

## Decision

Do not route this particular benchmark through direct Google API keys when the goal is to use Kaggle Benchmarks hosted frontier models.

Instead:

1. ask Kaggle Benchmarks which model slugs are currently exposed
2. resolve the requested logical targets against possible proxy slugs
3. run only when the slugs are actually present
4. emit an availability report when they are absent

## Current Limitation

After refreshing the Kaggle Benchmarks proxy session on `2026-06-30`, the exposed slugs were still:

- `anthropic/claude-haiku-4-5@20251001`
- `deepseek-ai/deepseek-v3.2`
- `google/gemini-3-flash-preview`
- `google/gemini-3.1-flash-lite-preview`
- `openai/gpt-oss-120b`
- `qwen/qwen3-next-80b-a3b-instruct`
- `zai/glm-5`

That means:

- `Gemini 3.5 Flash` is not currently exposed through this Kaggle Benchmarks session
- `Gemini 3.1 Pro` is not currently exposed through this Kaggle Benchmarks session

This is a proxy availability problem, not a benchmark-code problem.

## Outputs

The benchmark now writes:

- `frontier_audio_vimedcss_summary.json`
- `frontier_audio_vimedcss_responses.jsonl`
- `frontier_audio_vimedcss_availability.json`
- `frontier_bench_samples_summary.json`
- `frontier_bench_sample_responses.jsonl`
- `frontier_bench_smoke_availability.json`

The availability JSON is the source of truth for whether the requested frontier models can be run in the current session.

## Follow-up Change

The generic smoke task in `frontier_bench_smoke.py` was aligned with the same model-target resolution strategy.

It no longer sweeps every model listed in `LLMS_AVAILABLE`.

Instead it now:

1. targets only `Gemini 3.5 Flash`
2. targets only `Gemini 3.1 Pro`
3. writes `frontier_bench_smoke_availability.json`
4. exits cleanly when Kaggle Benchmarks does not expose those slugs

This removes the old accidental fallback to `google/gemini-3-flash-preview` and `google/gemini-3.1-flash-lite-preview` for the smoke benchmark path.

## Next Step

When Kaggle Benchmarks eventually exposes `Gemini 3.5 Flash` or `Gemini 3.1 Pro`, the current benchmark should pick them up without another code change.
