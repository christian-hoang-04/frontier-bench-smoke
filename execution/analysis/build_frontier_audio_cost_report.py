import argparse
import json
import wave
from datetime import datetime
from pathlib import Path


PRICING_SOURCE_URL = "https://ai.google.dev/gemini-api/docs/pricing"
PRICING_RETRIEVED_ON = "2026-07-05"
SCALING_TARGET_AUDIO_HOURS = 5000
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


def audio_duration_seconds(audio_path: Path) -> float:
    with wave.open(str(audio_path), "rb") as handle:
        return handle.getnframes() / handle.getframerate()


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def parse_utc_timestamp(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")


def build_report(run_dir: Path, bundle_dir: Path) -> dict:
    response_log_path = run_dir / "frontier_audio_vimedcss_responses.jsonl"
    summary_path = run_dir / "frontier_audio_vimedcss_summary.json"
    run_json_candidates = sorted(run_dir.glob("*.run.json"))
    if not response_log_path.exists():
        raise FileNotFoundError(f"Missing response log: {response_log_path}")
    if not summary_path.exists():
        raise FileNotFoundError(f"Missing summary json: {summary_path}")
    if not run_json_candidates:
        raise FileNotFoundError(f"Missing run json under {run_dir}")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    run_payload = json.loads(run_json_candidates[0].read_text(encoding="utf-8"))
    usage_rows = []
    for row in load_jsonl(response_log_path):
        if row.get("input_tokens") is None or row.get("output_tokens") is None:
            continue
        audio_file = row.get("audio_file")
        if not audio_file:
            continue
        row["audio_seconds"] = row.get("audio_seconds") or audio_duration_seconds(bundle_dir / "audio" / audio_file)
        usage_rows.append(row)

    total_audio_seconds = float(sum(float(row["audio_seconds"]) for row in usage_rows))
    total_audio_hours = total_audio_seconds / 3600 if total_audio_seconds else 0.0
    input_tokens_total = int(sum(int(row["input_tokens"]) for row in usage_rows))
    output_tokens_total = int(sum(int(row["output_tokens"]) for row in usage_rows))
    combined_tokens_total = input_tokens_total + output_tokens_total

    started_at = parse_utc_timestamp(run_payload["startTime"])
    ended_at = parse_utc_timestamp(run_payload["endTime"])
    wall_clock_seconds = (ended_at - started_at).total_seconds()
    wall_clock_hours = wall_clock_seconds / 3600 if wall_clock_seconds else 0.0

    def per_audio_hour(value: float) -> float | None:
        if total_audio_hours <= 0:
            return None
        return value / total_audio_hours

    def per_wall_clock_hour(value: float) -> float | None:
        if wall_clock_hours <= 0:
            return None
        return value / wall_clock_hours

    pricing = {}
    for tier_name, tier_prices in PRICING_TIERS.items():
        input_cost_per_audio_hour = (per_audio_hour(input_tokens_total) or 0.0) / 1_000_000 * tier_prices["input_price_per_million_tokens_usd"]
        output_cost_per_audio_hour = (per_audio_hour(output_tokens_total) or 0.0) / 1_000_000 * tier_prices["output_price_per_million_tokens_usd"]
        total_cost_per_audio_hour = input_cost_per_audio_hour + output_cost_per_audio_hour
        pricing[tier_name] = {
            **tier_prices,
            "input_cost_per_audio_hour_usd": input_cost_per_audio_hour,
            "output_cost_per_audio_hour_usd": output_cost_per_audio_hour,
            "total_cost_per_audio_hour_usd": total_cost_per_audio_hour,
            "estimated_cost_for_5000_audio_hours_usd": total_cost_per_audio_hour * SCALING_TARGET_AUDIO_HOURS,
        }

    return {
        "run_dir": str(run_dir),
        "bundle_dir": str(bundle_dir),
        "model_slug": run_payload.get("modelVersion", {}).get("slug"),
        "task_state": run_payload.get("state"),
        "pricing_source_url": PRICING_SOURCE_URL,
        "pricing_retrieved_on": PRICING_RETRIEVED_ON,
        "scaling_target_audio_hours": SCALING_TARGET_AUDIO_HOURS,
        "benchmark_quality": summary.get("aggregate", {}),
        "usage": {
            "rows_with_usage": len(usage_rows),
            "audio_seconds_total": total_audio_seconds,
            "audio_hours_total": total_audio_hours,
            "wall_clock_seconds": wall_clock_seconds,
            "wall_clock_hours": wall_clock_hours,
            "audio_hours_per_wall_clock_hour": None if wall_clock_hours <= 0 else total_audio_hours / wall_clock_hours,
            "real_time_factor": None if wall_clock_seconds <= 0 else total_audio_seconds / wall_clock_seconds,
            "input_tokens_total": input_tokens_total,
            "output_tokens_total": output_tokens_total,
            "combined_tokens_total": combined_tokens_total,
            "input_tokens_per_audio_hour": per_audio_hour(input_tokens_total),
            "output_tokens_per_audio_hour": per_audio_hour(output_tokens_total),
            "combined_tokens_per_audio_hour": per_audio_hour(combined_tokens_total),
            "input_tokens_per_wall_clock_hour": per_wall_clock_hour(input_tokens_total),
            "output_tokens_per_wall_clock_hour": per_wall_clock_hour(output_tokens_total),
            "combined_tokens_per_wall_clock_hour": per_wall_clock_hour(combined_tokens_total),
        },
        "pricing": pricing,
        "assumption": (
            "Scaling assumes future transcription uses a similar prompt shape, "
            "audio chunking strategy, and model behavior as this 20-clip benchmark run."
        ),
    }


def markdown_report(report: dict) -> str:
    quality = report["benchmark_quality"]
    usage = report["usage"]
    standard = report["pricing"]["standard"]
    batch = report["pricing"]["batch"]
    priority = report["pricing"]["priority"]
    return "\n".join(
        [
            "# Frontier Audio ViMedCSS Cost Report",
            "",
            f"- Model: `{report['model_slug']}`",
            f"- Pricing source: {report['pricing_source_url']} (retrieved {report['pricing_retrieved_on']})",
            f"- Run dir: `{report['run_dir']}`",
            "",
            "## Benchmark quality",
            "",
            f"- Rows completed: {quality.get('completed_count')} / {quality.get('row_count')}",
            f"- Mean WER: {quality.get('mean_wer')}",
            f"- Mean CER: {quality.get('mean_cer')}",
            "",
            "## Usage",
            "",
            f"- Audio covered: {usage['audio_seconds_total']:.2f}s ({usage['audio_hours_total']:.6f}h)",
            f"- Wall clock runtime: {usage['wall_clock_seconds']:.2f}s ({usage['wall_clock_hours']:.6f}h)",
            f"- Real-time factor: {usage['real_time_factor']:.3f}x",
            f"- Input tokens total: {usage['input_tokens_total']}",
            f"- Output tokens total: {usage['output_tokens_total']}",
            f"- Combined tokens total: {usage['combined_tokens_total']}",
            f"- Input tokens per audio hour: {usage['input_tokens_per_audio_hour']:.2f}",
            f"- Output tokens per audio hour: {usage['output_tokens_per_audio_hour']:.2f}",
            f"- Combined tokens per audio hour: {usage['combined_tokens_per_audio_hour']:.2f}",
            "",
            "## Cost estimates",
            "",
            f"- Standard cost per audio hour: ${standard['total_cost_per_audio_hour_usd']:.6f}",
            f"- Standard cost for 5000 audio hours: ${standard['estimated_cost_for_5000_audio_hours_usd']:.2f}",
            f"- Batch cost per audio hour: ${batch['total_cost_per_audio_hour_usd']:.6f}",
            f"- Batch cost for 5000 audio hours: ${batch['estimated_cost_for_5000_audio_hours_usd']:.2f}",
            f"- Priority cost per audio hour: ${priority['total_cost_per_audio_hour_usd']:.6f}",
            f"- Priority cost for 5000 audio hours: ${priority['estimated_cost_for_5000_audio_hours_usd']:.2f}",
            "",
            "## Assumption",
            "",
            f"- {report['assumption']}",
        ]
    ) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--bundle-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    report = build_report(args.run_dir, args.bundle_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    slug = (report.get("model_slug") or "unknown-model").replace("/", "_").replace(".", "_")
    json_path = args.output_dir / f"{slug}_cost_report.json"
    md_path = args.output_dir / f"{slug}_cost_report.md"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(markdown_report(report), encoding="utf-8")

    print(json.dumps({"json": str(json_path), "markdown": str(md_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
