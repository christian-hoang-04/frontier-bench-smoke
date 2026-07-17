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


@kbench.task(
    name="Frontier Text Direct Probe",
    description="Minimal parameterized text prompt probe for task-creation control.",
    version=1,
)
def frontier_text_direct_probe(
    llm,
    prompt_text: str,
    expected_text: str,
) -> None:
    response = llm.prompt(prompt_text)
    text = response.strip()
    kbench.assertions.assert_equal(
        expected_text,
        text,
        expectation="LLM should return the exact expected response.",
    )


if __name__ == "__main__":
    frontier_text_direct_probe.run(
        kbench.llm,
        prompt_text="Reply with exactly OK.",
        expected_text="OK",
    )
