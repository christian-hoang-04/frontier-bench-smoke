# Frontier Bench Smoke Progress

Audience: internal personal project notes.

## Summary

Moved the benchmark work into `D:\projects\personal\frontier-bench-smoke` and converted the original one-prompt smoke task into a real 5-sample deterministic benchmark sweep over the configured hosted frontier models.

The benchmark now checks:
- compact JSON formatting
- exact arithmetic output
- exact code echo
- one-label sentiment classification
- JSON field extraction

## Decisions

- Keep this as a personal project, not a Meedies project.
- Use `.env` in the project root as the source of benchmark proxy credentials and available model list.
- Refresh expired proxy credentials with `python -m kaggle benchmarks auth -y --env-file D:\projects\personal\frontier-bench-smoke\.env`.
- Keep the benchmark resilient to per-model API failures so one model under load does not abort the full sweep.
- Treat JSON code fences as a real formatting failure for the current benchmark, even when the semantic content is correct.
- Distinguish between the Kaggle benchmark page and the current proxy session model list.

## Results

Artifacts created by the run:
- `frontier_bench_sample_responses.jsonl`
- `frontier_bench_samples_summary.json`
- per-sample `.run.json` files

Observed model behavior from the completed sweep:
- `openai/gpt-oss-120b`: passed all 5 samples
- `qwen/qwen3-next-80b-a3b-instruct`: passed all 5 samples
- `google/gemini-3-flash-preview`: passed exact-answer tasks, failed JSON extraction formatting due to code fences
- `google/gemini-3.1-flash-lite-preview`: passed exact-answer tasks, failed JSON extraction formatting due to code fences
- `anthropic/claude-haiku-4-5@20251001`: failed both JSON-formatting samples due to code fences, passed the exact-answer tasks
- `zai/glm-5`: failed both JSON-formatting samples due to code fences, passed the exact-answer tasks
- `deepseek-ai/deepseek-v3.2`: returned `429` heavy-load errors on all 5 samples in this run

## Operational Lessons

- `kaggle-benchmarks` depends on fresh `MODEL_PROXY_*` credentials and does not auto-refresh them from Kaggle auth.
- The installed package explicitly points to `kaggle benchmarks auth` as the refresh path.
- Windows console output needs UTF-8 for the benchmark UI to print cleanly.
  Use `PYTHONIOENCODING=utf-8` when running locally.
- The local summary writer originally failed because the dataframe contained non-JSON-serializable model objects. Converting the dataframe to strings before JSON export avoids that crash.
- The local `LLMS_AVAILABLE` list is the real source of truth for which models can be benchmarked in the current session.
- The Kaggle task page shows models that already have recorded task runs attached to that task version. It does not necessarily show every model currently callable through the latest proxy session.
- Historical page visibility and current runtime availability are separate concepts and should not be conflated.

## Open Questions

- Whether to keep exact JSON-without-fences as a hard requirement or split format correctness from content correctness.
- Whether to add a stronger sample set with multi-step extraction or longer structured outputs.
- Whether to explicitly include `google/gemini-3.1-pro-preview` in the refreshed `.env` model list when available.

## Next Actions

- If a stronger Gemini model is wanted, refresh the benchmark session and update `LLMS_AVAILABLE` to include the exact Gemini Pro slug exposed by Kaggle for that session.
- Rerun the benchmark after any sample-set change and compare against `frontier_bench_samples_summary.json`.
- Consider adding a markdown report generator over the JSON outputs for quicker review.
- When checking support for a model, inspect both the Kaggle page history and the current `.env` model list before concluding anything.

## Important User Preferences

- This benchmark work belongs under `D:\projects\personal`.
- The user wants actual sample-based testing on frontier models, not a pure smoke check.
