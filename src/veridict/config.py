"""Loading, auto-detecting and scaffolding Veridict configuration.

Configuration lives in ``.veridict.yaml``. When it is absent, Veridict makes a
best effort to auto-detect how to build and test the project so it is useful
with zero setup. Anything it cannot infer is simply left unconfigured (and the
corresponding claims come back ``unverifiable`` rather than guessed at).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

CONFIG_NAMES = (".veridict.yaml", ".veridict.yml")

# Command slots Veridict understands. Order matters for display.
COMMAND_SLOTS = ("tests", "build", "lint", "typecheck")

# Built-in diff scanners (no command needed) and their default enablement.
BUILTIN_CHECKS = {"no_secrets": True, "no_new_todos": False}


def _default_checks() -> dict[str, bool]:
    return dict(BUILTIN_CHECKS)


@dataclass
class Config:
    """How Veridict establishes ground truth for a project."""

    commands: dict[str, str] = field(default_factory=dict)
    required: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=_default_checks)
    diff_base: str | None = None
    timeout: int = 300

    def command_for(self, slot: str) -> str | None:
        return self.commands.get(slot)


def find_config(path: Path) -> Path | None:
    """Return the nearest config file at or above ``path``, if any."""
    path = path.resolve()
    candidates = [path] + list(path.parents) if path.is_dir() else [path.parent]
    for directory in candidates:
        for name in CONFIG_NAMES:
            candidate = directory / name
            if candidate.is_file():
                return candidate
    return None


def load_config(path: Path) -> tuple[Config, Path | None]:
    """Load config for ``path``; fall back to auto-detection.

    Returns the resolved :class:`Config` and the file it came from (or ``None``
    when the configuration was auto-detected).
    """
    source = find_config(Path(path))
    if source is None:
        commands = autodetect_commands(Path(path))
        required = ["tests"] if "tests" in commands else []
        return Config(commands=commands, required=_gate_secrets(required, _default_checks())), None

    raw = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    commands = {
        slot: value
        for slot, value in (raw.get("commands") or {}).items()
        if value  # drop null/empty slots
    }
    checks = _default_checks()
    for name, enabled in (raw.get("checks") or {}).items():
        if name in checks:
            checks[name] = bool(enabled)
    required = [
        name
        for name in (raw.get("required") or [])
        if name in commands or (name in checks and checks[name])
    ]
    diff_base = raw.get("diff_base") or None
    timeout = int(raw.get("timeout", 300))
    return Config(
        commands=commands,
        required=_gate_secrets(required, checks),
        checks=checks,
        diff_base=diff_base,
        timeout=timeout,
    ), source


def _gate_secrets(required: list[str], checks: dict[str, bool]) -> list[str]:
    """A leaked credential must never exit 0: an enabled ``no_secrets`` check
    always gates. Opting out is disabling the check — a deliberate choice —
    not forgetting to list it under ``required``."""
    if checks.get("no_secrets") and "no_secrets" not in required:
        return [*required, "no_secrets"]
    return required


def autodetect_commands(root: Path) -> dict[str, str]:
    """Infer test/build commands from the files present in ``root``."""
    root = Path(root)
    commands: dict[str, str] = {}

    # Python
    if _is_python_project(root) and _has_python_tests(root):
        commands["tests"] = "pytest -q"

    # Node / JavaScript / TypeScript
    pkg = _read_package_json(root)
    if pkg is not None:
        scripts = pkg.get("scripts", {}) if isinstance(pkg, dict) else {}
        if "test" in scripts:
            commands.setdefault("tests", "npm test")
        if "build" in scripts:
            commands.setdefault("build", "npm run build")
        if "lint" in scripts:
            commands.setdefault("lint", "npm run lint")

    # Rust
    if (root / "Cargo.toml").is_file():
        commands.setdefault("tests", "cargo test")
        commands.setdefault("build", "cargo build")

    # Go
    if (root / "go.mod").is_file():
        commands.setdefault("tests", "go test ./...")
        commands.setdefault("build", "go build ./...")

    return commands


def _is_python_project(root: Path) -> bool:
    return any(
        (root / name).exists()
        for name in ("pyproject.toml", "setup.py", "setup.cfg", "pytest.ini", "tox.ini")
    )


def _has_python_tests(root: Path) -> bool:
    if (root / "tests").is_dir():
        return True
    for pattern in ("test_*.py", "*_test.py"):
        if any(root.glob(pattern)):
            return True
    # A configured pytest section is also a strong signal.
    pyproject = root / "pyproject.toml"
    if pyproject.is_file() and "[tool.pytest" in pyproject.read_text(encoding="utf-8", errors="ignore"):
        return True
    return False


def _read_package_json(root: Path) -> dict | None:
    pkg = root / "package.json"
    if not pkg.is_file():
        return None
    try:
        return json.loads(pkg.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


SCAFFOLD = """\
# Veridict configuration — https://github.com/venumittapalli576/veridict
#
# `commands` are how Veridict establishes GROUND TRUTH. Each value is a shell
# command run in this directory; exit code 0 means the check passed. Set a slot
# to null (or delete it) to leave it unconfigured — related claims will then be
# reported as "unverifiable" rather than guessed at.
commands:
  tests: {tests}
  build: {build}
  lint: {lint}
  typecheck: {typecheck}

# Built-in scanners that need no command. They inspect what a change ADDED
# (git diff + untracked files) — not the whole tree. An enabled no_secrets
# always gates (fails `veridict run`) — disable it to opt out.
checks:
  no_secrets: true       # added lines must not contain API keys / tokens / private keys
  no_new_todos: false    # added lines must not introduce TODO / FIXME / HACK markers

# Checks that MUST pass for `veridict run` to exit 0 (use it as a CI / commit gate).
required:
{required}

# Per-command timeout, in seconds.
timeout: 300
"""


def init_scaffold(path: Path, force: bool = False) -> Path:
    """Write a starter ``.veridict.yaml`` into ``path``.

    Auto-detected commands are pre-filled so the file is useful immediately.
    Raises :class:`FileExistsError` if a config already exists and ``force`` is
    not set.
    """
    path = Path(path)
    target = path / CONFIG_NAMES[0]
    if target.exists() and not force:
        raise FileExistsError(target)

    detected = autodetect_commands(path)

    def render(slot: str) -> str:
        value = detected.get(slot)
        return f'"{value}"' if value else "null"

    required_lines = "\n".join(f"  - {slot}" for slot in COMMAND_SLOTS if slot in detected) or "  []"
    if "tests" in detected:
        required_lines = "  - tests"

    target.write_text(
        SCAFFOLD.format(
            tests=render("tests"),
            build=render("build"),
            lint=render("lint"),
            typecheck=render("typecheck"),
            required=required_lines,
        ),
        encoding="utf-8",
    )
    return target
