import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()


def resolve_project_root() -> Path:
    for candidate in (SCRIPT_DIR, *SCRIPT_DIR.parents):
        if (candidate / "ideas").exists() and (candidate / "execution").exists():
            return candidate
    return SCRIPT_DIR


PROJECT_ROOT = resolve_project_root()
ENV_PATH = PROJECT_ROOT / ".env"


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


@kbench.task(name="frontier_text_probe_row", store_task=False, store_run=False)
def frontier_text_probe_row(llm, probe_id: str, prompt: str) -> dict:
    try:
        response = llm.prompt(prompt)
        text = response.strip()
        return {
            "probe_id": probe_id,
            "model_name": getattr(llm, "name", None) or getattr(llm, "model", None) or type(llm).__name__,
            "response": text,
            "response_nonempty": bool(text),
            "error": None,
        }
    except Exception as exc:
        return {
            "probe_id": probe_id,
            "model_name": getattr(llm, "name", None) or getattr(llm, "model", None) or type(llm).__name__,
            "response": "",
            "response_nonempty": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


@kbench.task(name="frontier_text_probe_benchmark")
def frontier_text_probe_benchmark(llm, evaluation_data) -> float:
    runs = frontier_text_probe_row.evaluate(
        llm=[llm],
        evaluation_data=evaluation_data,
        n_jobs=1,
        remove_run_files=False,
    )
    results_df = runs.as_dataframe()
    nonempty = results_df.result.str.get("response_nonempty").fillna(False)
    return float(nonempty.mean()) if len(results_df) else 0.0


PROBE_ROWS = pd.DataFrame(
    [
        {
            "probe_id": "text_only_ok",
            "prompt": "Reply with exactly OK.",
        }
    ]
)


frontier_text_probe_benchmark.run(kbench.llm, evaluation_data=PROBE_ROWS)
