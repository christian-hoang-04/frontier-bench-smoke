## Audience

Kaggle Benchmarks support / maintainers

## Subject

Question about frontier-model audio support in Kaggle Benchmarks

## Message

Hello Kaggle team,

I am testing custom Kaggle Benchmarks tasks for audio transcription and I am trying to understand the current support status for frontier-model audio inputs.

From the public `kaggle-benchmarks` repo, I saw PR `#121` ("Add audio modality input support"), merged on April 10, 2026. The PR body says that audio input support was added in the SDK and that model-proxy-side support was already merged as well.

However, I am still seeing failures in practice:

1. Custom benchmark task creation is failing for minimal audio-related probe tasks:
- `https://www.kaggle.com/benchmarks/tasks/lehoangnam/frontier-audio-vimedcss-bench/4`
- `https://www.kaggle.com/benchmarks/tasks/lehoangnam/frontier-audio-probe-benchmark/3`
- `https://www.kaggle.com/benchmarks/tasks/lehoangnam/frontier-text-probe-benchmark/1`

2. In local validation, a minimal direct call using:

```python
response = llm.prompt(prompt, audio=audios.from_path(wav_path))
```

reaches the send boundary but fails with:

```text
APIConnectionError: Connection error.
```

Based on the SDK code, audio appears to be a first-class content type (`audios.from_path`, `audios.from_url`, `audios.from_base64`) and is serialized for both GenAI and OpenAI-style backends, so this looks like a runtime or environment gap rather than a missing client feature.

Could you clarify:

- Is frontier-model audio input currently expected to work in Kaggle Benchmarks custom tasks?
- Is support limited to specific providers or model families?
- Are there known limitations in task creation notebooks or model-proxy routing for `audio=`?
- Is there an active plan to extend or stabilize audio support for custom benchmark tasks?

If helpful, I can provide the minimal repro task file and the exact local run output.

Thanks.

