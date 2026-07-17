import json
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()


def resolve_project_root() -> Path:
    for candidate in (SCRIPT_DIR, *SCRIPT_DIR.parents):
        if (candidate / "ideas").exists() and (candidate / "execution").exists():
            return candidate
    return SCRIPT_DIR


PROJECT_ROOT = resolve_project_root()
ENV_PATH = PROJECT_ROOT / '.env'
OUTPUT_DIR = Path.cwd()
SUMMARY_PATH = OUTPUT_DIR / 'frontier_bench_samples_summary.json'
RESPONSE_LOG_PATH = OUTPUT_DIR / 'frontier_bench_sample_responses.jsonl'
AVAILABILITY_PATH = OUTPUT_DIR / 'frontier_bench_smoke_availability.json'


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip())


load_env_file(ENV_PATH)

import kaggle_benchmarks as kbench
import pandas as pd


MODEL_TARGETS = (
    {
        'target_name': 'gemini_3_5_flash',
        'display_name': 'Gemini 3.5 Flash',
        'candidate_slugs': (
            'google/gemini-3.5-flash',
            'google/gemini-3.5-flash-preview',
        ),
    },
    {
        'target_name': 'gemini_3_1_pro',
        'display_name': 'Gemini 3.1 Pro',
        'candidate_slugs': (
            'google/gemini-3.1-pro-preview',
            'google/gemini-3.1-pro',
        ),
    },
)


SAMPLES = [
    {
        'sample_id': 'json_status',
        'prompt_text': 'Reply with a compact JSON object with keys status and model_check. Set status to ok. Set model_check to a short phrase proving you answered.',
        'required_terms_json': json.dumps(['status', 'ok', 'model_check']),
        'forbidden_terms_json': json.dumps(['```']),
        'exact_response': '',
        'max_chars': 120,
    },
    {
        'sample_id': 'arithmetic_exact',
        'prompt_text': 'Compute 11 + 6. Reply with only the final answer and no extra words.',
        'required_terms_json': json.dumps(['17']),
        'forbidden_terms_json': json.dumps(['18', 'answer', '```']),
        'exact_response': '17',
        'max_chars': 8,
    },
    {
        'sample_id': 'code_only',
        'prompt_text': 'Return exactly this code and nothing else: VT-2049',
        'required_terms_json': json.dumps(['VT-2049']),
        'forbidden_terms_json': json.dumps(['vt-2049', 'code', '```']),
        'exact_response': 'VT-2049',
        'max_chars': 16,
    },
    {
        'sample_id': 'sentiment_label',
        'prompt_text': 'Classify the sentiment of this review as exactly one label, POSITIVE or NEGATIVE, with no extra text: The onboarding was confusing and the support team never replied.',
        'required_terms_json': json.dumps(['NEGATIVE']),
        'forbidden_terms_json': json.dumps(['POSITIVE', '.', '```']),
        'exact_response': 'NEGATIVE',
        'max_chars': 16,
    },
    {
        'sample_id': 'json_extraction',
        'prompt_text': 'Extract the fields into JSON only. Note: Patient Lan, age 29, city Da Nang. Use keys name, age, city.',
        'required_terms_json': json.dumps(['name', 'Lan', '29', 'Da Nang', 'city']),
        'forbidden_terms_json': json.dumps(['```']),
        'exact_response': '',
        'max_chars': 160,
    },
]


def parse_terms(value: str) -> list[str]:
    return [str(item) for item in json.loads(value)]


def append_response_log(payload: dict) -> None:
    with RESPONSE_LOG_PATH.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + '\n')


@kbench.task(
    name='Frontier Bench Smoke',
    description='Deterministic multi-sample frontier model check for exactness and instruction following.',
    version=2,
)
def frontier_bench_smoke(
    llm,
    sample_id: str,
    prompt_text: str,
    required_terms_json: str,
    forbidden_terms_json: str,
    exact_response: str,
    max_chars: int,
) -> None:
    with kbench.chats.new(sample_id) as chat:
        model_hint = getattr(llm, 'name', None) or getattr(llm, 'model', None) or type(llm).__name__
        try:
            response = llm.prompt(prompt_text)
        except Exception as exc:
            append_response_log(
                {
                    'sample_id': sample_id,
                    'model_hint': model_hint,
                    'error_type': type(exc).__name__,
                    'error': str(exc),
                }
            )
            kbench.assertions.assert_fail(
                expectation=f'{sample_id}: model request failed for {model_hint}: {type(exc).__name__}: {exc}',
            )
            return

        stripped = response.strip()
        append_response_log(
            {
                'sample_id': sample_id,
                'model_hint': model_hint,
                'response': response,
                'response_length': len(stripped),
                'input_tokens': getattr(chat.usage, 'input_tokens', None),
                'output_tokens': getattr(chat.usage, 'output_tokens', None),
            }
        )

        for term in parse_terms(required_terms_json):
            kbench.assertions.assert_in(
                term,
                response,
                expectation=f'{sample_id}: response should include {term!r}.',
            )

        for term in parse_terms(forbidden_terms_json):
            kbench.assertions.assert_not_in(
                term,
                response,
                expectation=f'{sample_id}: response should not include {term!r}.',
            )

        if exact_response:
            kbench.assertions.assert_equal(
                exact_response,
                stripped,
                expectation=f'{sample_id}: response should match the exact required output.',
            )

        if max_chars > 0:
            kbench.assertions.assert_true(
                len(stripped) <= max_chars,
                expectation=f'{sample_id}: response should stay within {max_chars} characters.',
            )


def resolve_models() -> tuple[list, list[dict[str, object]]]:
    available_models = []
    availability_report: list[dict[str, object]] = []
    exposed_slugs = set(kbench.llms.keys())
    for target in MODEL_TARGETS:
        resolved_slug = None
        for slug in target['candidate_slugs']:
            if slug in exposed_slugs:
                resolved_slug = slug
                available_models.append(kbench.llms[slug])
                break
        availability_report.append(
            {
                'target_name': target['target_name'],
                'display_name': target['display_name'],
                'candidate_slugs': list(target['candidate_slugs']),
                'resolved_slug': resolved_slug,
                'available': resolved_slug is not None,
            }
        )
    return available_models, availability_report


if __name__ == '__main__':
    if RESPONSE_LOG_PATH.exists():
        RESPONSE_LOG_PATH.unlink()

    models, availability_report = resolve_models()
    availability_payload = {
        'requested_targets': availability_report,
        'exposed_slugs': sorted(kbench.llms.keys()),
    }
    AVAILABILITY_PATH.write_text(json.dumps(availability_payload, indent=2, ensure_ascii=False), encoding='utf-8')

    if not models:
        raise SystemExit(
            'None of the requested smoke-test models are exposed in the current Kaggle Benchmarks session. '
            f'See {AVAILABILITY_PATH}.'
        )

    frame = pd.DataFrame(SAMPLES)
    runs = frontier_bench_smoke.evaluate(
        llm=models,
        evaluation_data=frame,
        n_jobs=1,
        timeout=180,
        max_attempts=1,
        retry_delay=0,
    )
    results_df = runs.as_dataframe()
    payload = {
        'availability': availability_payload,
        'runs': results_df.to_dict(orient='records'),
    }
    SUMMARY_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    print(results_df.to_string(index=False))
    print(f'\nSaved summary to {SUMMARY_PATH}')
    print(f'Saved response log to {RESPONSE_LOG_PATH}')
    print(f'Saved availability report to {AVAILABILITY_PATH}')

