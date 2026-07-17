# %%
import json
import os
from pathlib import Path

import kaggle_benchmarks as kbench
from kaggle_benchmarks.kaggle.models import load_model

# %%
SCRIPT_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()


def resolve_project_root() -> Path:
    for candidate in (SCRIPT_DIR, *SCRIPT_DIR.parents):
        if (candidate / "ideas").exists() and (candidate / "execution").exists():
            return candidate
    return SCRIPT_DIR


PROJECT_ROOT = resolve_project_root()
ENV_PATH = PROJECT_ROOT / ".env"
OUTPUT_DIR = Path.cwd()
SUMMARY_PATH = OUTPUT_DIR / "frontier_prompt_token_probe_summary.json"
PROMPT = """Please transcribe the provided audio accurately with speaker diarization and timestamps.

Requirements:

* Identify speakers only as `Speaker 1`, `Speaker 2`, `Speaker 3`, etc.
* Do not use or guess real speaker names.
* Include timestamps for each speaker turn in the format `[HH:MM:SS - HH:MM:SS]`.
* Preserve the original language and wording as much as possible.
* Transcribe only what is actually heard in the audio.
* Do not infer, complete, or create sentences based on context.
* Do not correct unclear or incomplete speech into a “better” sentence.
* Do not summarize, translate, or rewrite the content.
* Remove filler only if it is clearly non-meaningful, such as repeated stutters or accidental noises.
* Mark unclear words as `[inaudible]` with the timestamp.
* Keep each speaker turn on a separate line.

Output format:

[00:00:00 - 00:00:05] Speaker 1: ...
[00:00:05 - 00:00:12] Speaker 2: ...
[00:00:12 - 00:00:20] Speaker 1: ..."""


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


load_env_file(ENV_PATH)


# %%
@kbench.task(
    name="Frontier Prompt Token Probe",
    description="Measure Gemini token usage for a fixed diarization+timestamps transcription prompt.",
)
def frontier_prompt_token_probe(llm) -> dict:
    with kbench.chats.new("frontier_prompt_token_probe") as chat:
        response = llm.prompt(PROMPT, reasoning="low", temperature=0)
        payload = {
            "model_hint": getattr(llm, "name", None) or getattr(llm, "model", None) or type(llm).__name__,
            "prompt": PROMPT,
            "prompt_length_chars": len(PROMPT),
            "input_tokens": getattr(chat.usage, "input_tokens", None),
            "output_tokens": getattr(chat.usage, "output_tokens", None),
            "input_tokens_cost_nanodollars": getattr(chat.usage, "input_tokens_cost_nanodollars", None),
            "output_tokens_cost_nanodollars": getattr(chat.usage, "output_tokens_cost_nanodollars", None),
            "response_preview": response[:500] if isinstance(response, str) else str(response)[:500],
        }
        SUMMARY_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return payload


# %%
if __name__ == "__main__":
    run_model_slug = os.environ.get("FRONTIER_PROMPT_TOKEN_PROBE_MODEL", "google/gemini-3.5-flash")
    run = frontier_prompt_token_probe.run(load_model(run_model_slug))
    print(json.dumps({"result": run.result, "passed": run.passed}, ensure_ascii=False, indent=2))
