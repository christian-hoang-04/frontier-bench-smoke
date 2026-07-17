import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

import pyarrow.parquet as pq

SCRIPT_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()


def resolve_project_root() -> Path:
    for candidate in (SCRIPT_DIR, *SCRIPT_DIR.parents):
        if (candidate / "ideas").exists() and (candidate / "execution").exists():
            return candidate
    return SCRIPT_DIR


PROJECT_ROOT = resolve_project_root()
ENV_PATH = PROJECT_ROOT / ".env"
OUTPUT_DIR = Path.cwd()
AUDIO_DIR = OUTPUT_DIR / "audio"
SUMMARY_PATH = OUTPUT_DIR / "frontier_audio_meddies_small_test_summary.json"
ROWS_PATH = OUTPUT_DIR / "frontier_audio_meddies_small_test_rows.json"
RESPONSE_LOG_PATH = OUTPUT_DIR / "frontier_audio_meddies_small_test_responses.jsonl"

DEFAULT_PARQUET_PATH = Path(
    r"D:\projects\meddies\asr\tmp\hf_staging\meddies-asr-small-test\data\vi-faptv-human-gold\test-00000.parquet"
)
PARQUET_ENV_VAR = "MEDDIES_SMALL_TEST_PARQUET_PATH"
MODEL_ENV_VAR = "FRONTIER_AUDIO_MEDDIES_SMALL_TEST_MODEL"
LIMIT_ENV_VAR = "MEDDIES_SMALL_TEST_LIMIT"
DEFAULT_MODEL = "google/gemini-3.5-flash"
PROMPT = """Please transcribe the provided audio accurately with speaker diarization.
Requirements:
* Identify speakers only as `Speaker 1`, `Speaker 2`, `Speaker 3`, etc.
* Do not use or guess real speaker names.
* Do not include any timestamps in the transcript.
* Preserve the original language and wording as much as possible.
* Transcribe only what is actually heard in the audio.
* Do not infer, complete, or create sentences based on context.
* Do not correct unclear or incomplete speech into a "better" sentence.
* Do not summarize, translate, or rewrite the content.
* Remove filler only if it is clearly non-meaningful, such as repeated stutters or accidental noises.
* Mark unclear words as [inaudible].
* Keep each speaker turn on a separate line.

Output format:
Speaker 1: ...
Speaker 2: ...
Speaker 1: ..."""
PROMPT_REASONING = "low"
PROMPT_TEMPERATURE = 0
RATE_LIMIT_MAX_ATTEMPTS = 4
RATE_LIMIT_BASE_DELAY_SECONDS = 20


def configure_stdio() -> None:
    # Kaggle benchmark task logs can emit Vietnamese text directly to stdout on Windows.
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8")
            except Exception:
                pass


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
configure_stdio()

import kaggle_benchmarks as kbench
import pandas as pd
from kaggle_benchmarks.content_types import audios
from kaggle_benchmarks.kaggle.models import load_model


def resolve_parquet_path() -> Path:
    override = os.environ.get(PARQUET_ENV_VAR)
    if override:
        path = Path(override)
        if path.exists():
            return path
    if DEFAULT_PARQUET_PATH.exists():
        return DEFAULT_PARQUET_PATH
    raise FileNotFoundError(
        f"Meddies small-test parquet not found. Set {PARQUET_ENV_VAR} or restore {DEFAULT_PARQUET_PATH}."
    )


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", str(text)).lower()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text, flags=re.UNICODE)
    return text.strip()


def strip_speaker_labels(text: str) -> str:
    lines = []
    for raw_line in str(text).splitlines():
        line = re.sub(r"^\s*speaker\s+\d+\s*:\s*", "", raw_line, flags=re.IGNORECASE)
        line = line.strip()
        if line:
            lines.append(line)
    return "\n".join(lines).strip()


def levenshtein(seq1: list[str], seq2: list[str]) -> int:
    if not seq1:
        return len(seq2)
    if not seq2:
        return len(seq1)
    prev = list(range(len(seq2) + 1))
    for i, left in enumerate(seq1, start=1):
        curr = [i]
        for j, right in enumerate(seq2, start=1):
            cost = 0 if left == right else 1
            curr.append(min(curr[-1] + 1, prev[j] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


def error_rates(reference: str, hypothesis: str) -> tuple[float, float]:
    ref_words = normalize_text(reference).split()
    hyp_words = normalize_text(hypothesis).split()
    ref_chars = list(normalize_text(reference).replace(" ", ""))
    hyp_chars = list(normalize_text(hypothesis).replace(" ", ""))
    wer = levenshtein(ref_words, hyp_words) / max(1, len(ref_words))
    cer = levenshtein(ref_chars, hyp_chars) / max(1, len(ref_chars))
    return wer, cer


def append_response_log(payload: dict) -> None:
    with RESPONSE_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def load_response_log_rows() -> list[dict]:
    if not RESPONSE_LOG_PATH.exists():
        return []
    rows = []
    for raw_line in RESPONSE_LOG_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def is_rate_limit_error(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return "ratelimiterror" in text or "rate_limit_error" in text or "error code: 429" in text


def extract_rows() -> list[dict]:
    parquet_path = resolve_parquet_path()
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    table = pq.read_table(parquet_path)
    limit_raw = os.environ.get(LIMIT_ENV_VAR)
    limit = int(limit_raw) if limit_raw else None
    for idx, row in enumerate(table.to_pylist(), start=1):
        if limit is not None and len(rows) >= limit:
            break
        audio = row["audio"]
        audio_path = AUDIO_DIR / f"{idx:02d}_{row['selection_rank']}_clip.wav"
        if not audio_path.exists():
            audio_path.write_bytes(audio["bytes"])
        rows.append(
            {
                "clip_id": f"clip_{idx:02d}",
                "example_id": row["example_id"],
                "selection_rank": int(row["selection_rank"]),
                "title": row["title"],
                "youtube_video_id": row["youtube_video_id"],
                "youtube_url": row["youtube_url"],
                "reference_text": row["reference_text"],
                "duration_s": float(row["duration_s"]),
                "clip_start_s": float(row["clip_start_s"]),
                "clip_end_s": float(row["clip_end_s"]),
                "audio_path": str(audio_path),
            }
        )
    return rows


@kbench.task(name="frontier_audio_meddies_small_test_row", store_task=False, store_run=False)
def frontier_audio_meddies_small_test_row(
    llm,
    clip_id: str,
    example_id: str,
    selection_rank: int,
    title: str,
    youtube_video_id: str,
    youtube_url: str,
    reference_text: str,
    duration_s: float,
    clip_start_s: float,
    clip_end_s: float,
    audio_path: str,
) -> dict:
    with kbench.chats.new(clip_id) as chat:
        model_hint = getattr(llm, "name", None) or getattr(llm, "model", None) or type(llm).__name__
        response = None
        last_error = None
        for attempt in range(1, RATE_LIMIT_MAX_ATTEMPTS + 1):
            try:
                response = llm.prompt(
                    PROMPT,
                    audio=audios.from_path(audio_path),
                    reasoning=PROMPT_REASONING,
                    temperature=PROMPT_TEMPERATURE,
                )
                break
            except Exception as exc:
                last_error = exc
                if not is_rate_limit_error(exc) or attempt >= RATE_LIMIT_MAX_ATTEMPTS:
                    break
                delay_seconds = RATE_LIMIT_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
                append_response_log(
                    {
                        "clip_id": clip_id,
                        "example_id": example_id,
                        "model_hint": model_hint,
                        "warning_type": type(exc).__name__,
                        "warning": str(exc),
                        "attempt": attempt,
                        "next_retry_delay_seconds": delay_seconds,
                    }
                )
                time.sleep(delay_seconds)

        if response is None:
            exc = last_error if last_error is not None else RuntimeError("ASR prompt returned no response.")
            append_response_log(
                {
                    "clip_id": clip_id,
                    "example_id": example_id,
                    "model_hint": model_hint,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            return {"error": f"{type(exc).__name__}: {exc}"}

        transcript = str(response).strip()
        stripped_transcript = strip_speaker_labels(transcript)
        raw_wer, raw_cer = error_rates(reference_text, transcript)
        stripped_wer, stripped_cer = error_rates(reference_text, stripped_transcript)
        payload = {
            "clip_id": clip_id,
            "example_id": example_id,
            "selection_rank": selection_rank,
            "title": title,
            "youtube_video_id": youtube_video_id,
            "youtube_url": youtube_url,
            "duration_s": round(float(duration_s), 3),
            "clip_start_s": round(float(clip_start_s), 3),
            "clip_end_s": round(float(clip_end_s), 3),
            "model_hint": model_hint,
            "reference_text": reference_text,
            "transcript": transcript,
            "transcript_without_speaker_labels": stripped_transcript,
            "raw_wer": round(raw_wer, 4),
            "raw_cer": round(raw_cer, 4),
            "stripped_wer": round(stripped_wer, 4),
            "stripped_cer": round(stripped_cer, 4),
            "input_tokens": getattr(chat.usage, "input_tokens", None),
            "output_tokens": getattr(chat.usage, "output_tokens", None),
        }
        append_response_log(payload)
        return {"error": None, "raw_wer": payload["raw_wer"], "raw_cer": payload["raw_cer"], "stripped_wer": payload["stripped_wer"], "stripped_cer": payload["stripped_cer"]}


@kbench.task(
    name="Frontier Audio Meddies Small Test Bench",
    description="20-sample Meddies ASR small-test audio transcription benchmark with diarization prompt.",
)
def frontier_audio_meddies_small_test_bench(llm, evaluation_data) -> float:
    runs = frontier_audio_meddies_small_test_row.evaluate(
        llm=[llm],
        evaluation_data=evaluation_data,
        n_jobs=1,
        remove_run_files=False,
    )
    results_df = runs.as_dataframe()
    result_series = results_df["result"]
    error_series = result_series.str.get("error")
    raw_wer_series = pd.to_numeric(result_series.str.get("raw_wer"), errors="coerce")
    raw_cer_series = pd.to_numeric(result_series.str.get("raw_cer"), errors="coerce")
    stripped_wer_series = pd.to_numeric(result_series.str.get("stripped_wer"), errors="coerce")
    stripped_cer_series = pd.to_numeric(result_series.str.get("stripped_cer"), errors="coerce")

    aggregate = {
        "row_count": int(len(results_df)),
        "completed_count": int(error_series.isna().sum()),
        "error_count": int(error_series.notna().sum()),
        "mean_raw_wer": None if raw_wer_series.dropna().empty else float(raw_wer_series.dropna().mean()),
        "mean_raw_cer": None if raw_cer_series.dropna().empty else float(raw_cer_series.dropna().mean()),
        "mean_stripped_wer": None if stripped_wer_series.dropna().empty else float(stripped_wer_series.dropna().mean()),
        "mean_stripped_cer": None if stripped_cer_series.dropna().empty else float(stripped_cer_series.dropna().mean()),
        "parquet_path": str(resolve_parquet_path()),
    }
    payload = {
        "aggregate": aggregate,
        "runs": results_df.drop(columns=["llm"], errors="ignore").to_dict(orient="records"),
        "response_rows": load_response_log_rows(),
    }
    SUMMARY_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    ROWS_PATH.write_text(json.dumps(payload["response_rows"], ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(aggregate, ensure_ascii=False, indent=2))
    print(f"Saved summary to {SUMMARY_PATH}")
    return 0.0 if stripped_wer_series.dropna().empty else float(stripped_wer_series.dropna().mean())


if __name__ == "__main__":
    if RESPONSE_LOG_PATH.exists():
        RESPONSE_LOG_PATH.unlink()
    rows = extract_rows()
    frame = pd.DataFrame(rows)
    run_model_slug = os.environ.get(MODEL_ENV_VAR, DEFAULT_MODEL)
    run = frontier_audio_meddies_small_test_bench.run(
        load_model(run_model_slug),
        evaluation_data=frame,
    )
    print(json.dumps({"result": run.result, "passed": run.passed}, ensure_ascii=False, indent=2))
