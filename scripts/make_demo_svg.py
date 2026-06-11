"""Regenerate docs/demo.svg — the README's hero image.

Stages a small project where an AI agent's summary overstates reality, runs
the real Veridict pipeline on it, and exports rich's terminal rendering as
SVG. Nothing is mocked: the verdicts in the image are produced by the same
code paths users run.

Usage: python scripts/make_demo_svg.py
"""

from __future__ import annotations

import io
import subprocess
import sys
import tempfile
from pathlib import Path

from rich.console import Console

from veridict.config import load_config
from veridict.engine import verify_transcript
from veridict.report import render_terminal

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "docs" / "demo.svg"

# Assembled at runtime so no key-shaped literal ever sits in this repo.
FAKE_AWS_KEY = "AKIA" + "IOSFODNN7DEMO0AB"

TRANSCRIPT = """\
Done! I created `calculator.py` with the core logic and added `utils.py`
with the new helpers. Also added `config.py` for the API settings.
All tests pass and no secrets were committed. No TODOs left.
"""

CALCULATOR = """\
def add(a, b):
    return a + b


def divide(a, b):
    return a / b
"""

# The agent "forgot" to handle division by zero — the suite fails.
TESTS = """\
from calculator import add, divide


def test_add():
    assert add(2, 3) == 5


def test_divide_by_zero_is_handled():
    assert divide(1, 0) is None
"""


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=demo@veridict", "-c", "user.name=demo", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def stage_project(root: Path) -> None:
    (root / "calculator.py").write_text(CALCULATOR, encoding="utf-8")
    (root / "test_calculator.py").write_text(TESTS, encoding="utf-8")
    py = Path(sys.executable).as_posix()
    (root / ".veridict.yaml").write_text(
        f"commands:\n  tests: '\"{py}\" -m pytest -q'\nrequired:\n  - tests\n",
        encoding="utf-8",
    )
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "baseline")
    # The agent's uncommitted work: a config file with a pasted credential.
    # utils.py only ever existed in the transcript.
    (root / "config.py").write_text(
        f'API_URL = "https://api.example.com"\nAWS_KEY = "{FAKE_AWS_KEY}"\n', encoding="utf-8"
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        stage_project(root)
        config, _ = load_config(root)
        report = verify_transcript(TRANSCRIPT, config, str(root))

        # file=StringIO keeps the recording off the real stdout, whose encoding
        # (cp1252 on Windows) can't take the report's glyphs.
        console = Console(record=True, width=100, legacy_windows=False, file=io.StringIO())
        console.print()
        console.print("[bold cyan]$[/bold cyan] [bold]veridict check[/bold] agent_summary.md")
        render_terminal(report, console=console)
        console.print()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    svg = console.export_svg(title="veridict — don't trust the transcript")
    OUT.write_text(svg, encoding="utf-8")
    print(f"wrote {OUT} (trust score: {report.trust_score}, false claims: {len(report.lies)})")


if __name__ == "__main__":
    main()
