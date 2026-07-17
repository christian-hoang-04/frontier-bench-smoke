import json
import os
import re
import time
import unicodedata
import wave
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()


def resolve_project_root() -> Path:
    for candidate in (SCRIPT_DIR, *SCRIPT_DIR.parents):
        if (candidate / "ideas").exists() and (candidate / "execution").exists():
            return candidate
    return SCRIPT_DIR


PROJECT_ROOT = resolve_project_root()
ENV_PATH = PROJECT_ROOT / ".env"
OUTPUT_DIR = Path.cwd()
SUMMARY_PATH = OUTPUT_DIR / "frontier_audio_vimedcss_summary.json"
RESPONSE_LOG_PATH = OUTPUT_DIR / "frontier_audio_vimedcss_responses.jsonl"

BUNDLE_ENV_VAR = "VIMEDCSS_AUDIO_BUNDLE_DIR"
BUNDLE_SLUG = "vimedcss-audio-bundle-20"
LOCAL_BUNDLE_DIR = PROJECT_ROOT / "execution" / "data" / "bundles" / "vimedcss_audio_bundle_20"
KAGGLE_BUNDLE_DIR = Path("/kaggle/input") / BUNDLE_SLUG


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

import kaggle_benchmarks as kbench
import pandas as pd
from kaggle_benchmarks.content_types import audios
from kaggle_benchmarks.kaggle.models import load_model


PROMPT = (
    "Transcribe this audio into plain text only. "
    "Do not add markdown, labels, or explanation. "
    "Preserve Vietnamese-English medical code-switching terms as spoken."
)
PROMPT_REASONING = "low"
PROMPT_TEMPERATURE = 0
RATE_LIMIT_MAX_ATTEMPTS = 4
RATE_LIMIT_BASE_DELAY_SECONDS = 20
PRICING_SOURCE_URL = "https://ai.google.dev/gemini-api/docs/pricing"
PRICING_RETRIEVED_ON = "2026-07-05"
PRICING_TIERS = {
    "standard": {
        "input_price_per_million_tokens_usd": 1.50,
        "output_price_per_million_tokens_usd": 9.00,
    },
    "batch": {
        "input_price_per_million_tokens_usd": 0.75,
        "output_price_per_million_tokens_usd": 4.50,
    },
    "priority": {
        "input_price_per_million_tokens_usd": 2.70,
        "output_price_per_million_tokens_usd": 16.20,
    },
}
SCALING_TARGET_AUDIO_HOURS = 5000


def resolve_bundle_dir() -> Path:
    override = os.environ.get(BUNDLE_ENV_VAR)
    if override:
        path = Path(override)
        if path.exists():
            return path

    for candidate in (KAGGLE_BUNDLE_DIR, LOCAL_BUNDLE_DIR):
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "ViMedCSS audio bundle not found. "
        f"Set {BUNDLE_ENV_VAR} or attach Kaggle dataset {BUNDLE_SLUG}."
    )


def load_rows(bundle_dir: Path) -> list[dict]:
    manifest_path = bundle_dir / "benchmark_rows.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def resolve_audio_path(bundle_dir: Path, audio_file: str) -> Path:
    candidates = (
        bundle_dir / "audio" / audio_file,
        bundle_dir / audio_file,
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Audio file {audio_file} not found under {bundle_dir}")


def audio_duration_seconds(audio_path: Path) -> float:
    with wave.open(str(audio_path), "rb") as handle:
        return handle.getnframes() / handle.getframerate()


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text).lower()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text, flags=re.UNICODE)
    return text.strip()


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
    ref_chars = list(normalize_text(reference))
    hyp_chars = list(normalize_text(hypothesis))
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
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def summarize_usage_rows(rows: list[dict]) -> dict | None:
    usage_rows = [
        row
        for row in rows
        if row.get("audio_seconds") is not None
        and row.get("input_tokens") is not None
        and row.get("output_tokens") is not None
    ]
    if not usage_rows:
        return None

    total_audio_seconds = float(sum(float(row["audio_seconds"]) for row in usage_rows))
    total_audio_hours = total_audio_seconds / 3600 if total_audio_seconds else 0.0
    total_input_tokens = int(sum(int(row["input_tokens"]) for row in usage_rows))
    total_output_tokens = int(sum(int(row["output_tokens"]) for row in usage_rows))
    total_tokens = total_input_tokens + total_output_tokens

    def per_audio_hour(value: float) -> float | None:
        if total_audio_hours <= 0:
            return None
        return value / total_audio_hours

    pricing = {}
    for tier_name, tier_prices in PRICING_TIERS.items():
        input_cost_per_audio_hour = (
            per_audio_hour(total_input_tokens) or 0.0
        ) / 1_000_000 * tier_prices["input_price_per_million_tokens_usd"]
        output_cost_per_audio_hour = (
            per_audio_hour(total_output_tokens) or 0.0
        ) / 1_000_000 * tier_prices["output_price_per_million_tokens_usd"]
        total_cost_per_audio_hour = input_cost_per_audio_hour + output_cost_per_audio_hour
        pricing[tier_name] = {
            **tier_prices,
            "input_cost_per_audio_hour_usd": input_cost_per_audio_hour,
            "output_cost_per_audio_hour_usd": output_cost_per_audio_hour,
            "total_cost_per_audio_hour_usd": total_cost_per_audio_hour,
            "estimated_cost_for_5000_audio_hours_usd": total_cost_per_audio_hour * SCALING_TARGET_AUDIO_HOURS,
        }

    return {
        "pricing_source_url": PRICING_SOURCE_URL,
        "pricing_retrieved_on": PRICING_RETRIEVED_ON,
        "scaling_target_audio_hours": SCALING_TARGET_AUDIO_HOURS,
        "rows_with_usage": len(usage_rows),
        "audio_seconds_total": total_audio_seconds,
        "audio_hours_total": total_audio_hours,
        "input_tokens_total": total_input_tokens,
        "output_tokens_total": total_output_tokens,
        "combined_tokens_total": total_tokens,
        "input_tokens_per_audio_hour": per_audio_hour(total_input_tokens),
        "output_tokens_per_audio_hour": per_audio_hour(total_output_tokens),
        "combined_tokens_per_audio_hour": per_audio_hour(total_tokens),
        "pricing": pricing,
        "assumption": (
            "Scaling assumes future transcription uses a similar prompt shape, "
            "audio chunking strategy, and model behavior as this benchmark run."
        ),
    }


def is_rate_limit_error(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return "ratelimiterror" in text or "rate_limit_error" in text or "error code: 429" in text


@kbench.task(name="frontier_audio_vimedcss_row", store_task=False, store_run=False)
def frontier_audio_vimedcss_row(
    llm,
    clip_id: str,
    split: str,
    segment_id: str,
    audio_file: str,
    segment_text: str,
    cs_terms_list: str,
    topic: str,
) -> dict:
    bundle_dir = resolve_bundle_dir()
    audio_path = resolve_audio_path(bundle_dir, audio_file)
    clip_audio_seconds = audio_duration_seconds(audio_path)

    with kbench.chats.new(clip_id) as chat:
        model_hint = getattr(llm, "name", None) or getattr(llm, "model", None) or type(llm).__name__
        response = None
        last_error = None
        for attempt in range(1, RATE_LIMIT_MAX_ATTEMPTS + 1):
            try:
                # Keep ASR runs deterministic and minimize extra reasoning-token usage.
                response = llm.prompt(
                    PROMPT,
                    audio=audios.from_path(str(audio_path)),
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
                        "split": split,
                        "segment_id": segment_id,
                        "audio_file": audio_file,
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
                    "split": split,
                    "segment_id": segment_id,
                    "audio_file": audio_file,
                    "model_hint": model_hint,
                    "attempts_used": RATE_LIMIT_MAX_ATTEMPTS if is_rate_limit_error(exc) else 1,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            return {
                "error": f"{type(exc).__name__}: {exc}",
                "wer": None,
                "cer": None,
            }

        transcript = response.strip()
        wer, cer = error_rates(segment_text, transcript)
        payload = {
            "clip_id": clip_id,
            "split": split,
            "segment_id": segment_id,
            "topic": topic,
            "audio_file": audio_file,
            "audio_seconds": round(clip_audio_seconds, 4),
            "model_hint": model_hint,
            "reference_text": segment_text,
            "transcript": transcript,
            "cs_terms_list": cs_terms_list,
            "wer": round(wer, 4),
            "cer": round(cer, 4),
            "input_tokens": getattr(chat.usage, "input_tokens", None),
            "output_tokens": getattr(chat.usage, "output_tokens", None),
        }
        append_response_log(payload)
        return {"error": None, "wer": round(wer, 4), "cer": round(cer, 4)}


@kbench.task(
    name="Frontier Audio ViMedCSS Bench",
    description="20-sample ViMedCSS audio transcription benchmark using a mounted audio bundle.",
)
def frontier_audio_vimedcss_bench(llm, evaluation_data) -> float:
    runs = frontier_audio_vimedcss_row.evaluate(
        llm=[llm],
        evaluation_data=evaluation_data,
        n_jobs=1,
        remove_run_files=False,
    )
    results_df = runs.as_dataframe()
    result_series = results_df["result"]
    error_series = result_series.str.get("error")
    wer_series = pd.to_numeric(result_series.str.get("wer"), errors="coerce")
    cer_series = pd.to_numeric(result_series.str.get("cer"), errors="coerce")

    aggregate = {
        "row_count": int(len(results_df)),
        "completed_count": int(error_series.isna().sum()),
        "error_count": int(error_series.notna().sum()),
        "mean_wer": None if wer_series.dropna().empty else float(wer_series.dropna().mean()),
        "mean_cer": None if cer_series.dropna().empty else float(cer_series.dropna().mean()),
        "bundle_dir": str(resolve_bundle_dir()),
    }
    usage = summarize_usage_rows(load_response_log_rows())
    serializable_results_df = results_df.drop(columns=["llm"], errors="ignore")
    payload = {
        "aggregate": aggregate,
        "usage": usage,
        "runs": serializable_results_df.to_dict(orient="records"),
    }
    SUMMARY_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(aggregate, ensure_ascii=False, indent=2))
    if usage is not None:
        print(json.dumps({"usage": usage}, ensure_ascii=False, indent=2))
    print(f"Saved summary to {SUMMARY_PATH}")
    return 0.0 if wer_series.dropna().empty else float(wer_series.dropna().mean())


if __name__ == "__main__":
    if RESPONSE_LOG_PATH.exists():
        RESPONSE_LOG_PATH.unlink()

    bundle_dir = resolve_bundle_dir()
    rows = load_rows(bundle_dir)
    frame = pd.DataFrame(rows)
    run_model_slug = os.environ.get("FRONTIER_AUDIO_VIMEDCSS_MODEL", "google/gemini-3.5-flash")
    run = frontier_audio_vimedcss_bench.run(
        load_model(run_model_slug),
        evaluation_data=frame,
    )
    print(json.dumps({"result": run.result, "passed": run.passed}, ensure_ascii=False, indent=2))
