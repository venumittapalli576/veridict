"""Scan what an agent *added* — newly introduced TODOs and leaked secrets.

These scanners look only at added lines (the git diff plus untracked files),
never the whole tree: the question they answer is "did the agent's changes
introduce this?", not "does the project contain it somewhere?". Secrets are
reported by kind and location with the matched value masked, so the report
itself never re-leaks a credential.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

_MAX_UNTRACKED_BYTES = 512 * 1024  # ignore huge untracked files (vendored blobs etc.)

# Markers that flag unfinished work when *introduced* by a change.
_TODO_PATTERN = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")

# Values that look secret-shaped but are clearly samples, not credentials.
_PLACEHOLDER = re.compile(r"(?i)example|placeholder|your[_-]|changeme|dummy|redacted|[<{$*]|x{4,}")

# (kind, pattern). Specific, well-known token shapes first; the generic
# assignment rule last because it is the only one that needs the placeholder
# filter to stay precise.
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("AWS access key ID", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}\b")),
    ("Anthropic API key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{32,}\b")),
    ("OpenAI API key", re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9]{32,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("Stripe live key", re.compile(r"\b[sr]k_live_[A-Za-z0-9]{24,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY( BLOCK)?-----")),
    (
        "hardcoded credential",
        re.compile(
            r"(?i)\b[\w.-]*(?:password|passwd|secret|api[_-]?key|auth[_-]?token|access[_-]?token)\b"
            r"\s*[:=]\s*['\"](?P<value>[^'\"\s]{12,})['\"]"
        ),
    ),
]


@dataclass
class AddedLine:
    """One line of content a change introduced."""

    path: str
    line: int  # 1-based line number in the new file
    text: str


@dataclass
class DiffScan:
    """Every line the pending change (and optional ref range) added."""

    lines: list[AddedLine] = field(default_factory=list)
    tree_dirty: bool = False  # any pending working-tree change (incl. untracked)
    base: str | None = None  # ref the committed range was diffed against
    error: str | None = None  # set when git could not be used at all

    @property
    def saw_changes(self) -> bool:
        """Whether there was any change to inspect (added lines may still be 0)."""
        return self.tree_dirty or self.base is not None


def _git(args: list[str], cwd: str, timeout: int) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return proc.returncode, proc.stdout or ""
    except (subprocess.TimeoutExpired, OSError):
        return 1, "git unavailable or timed out"


def _parse_added(diff_text: str) -> list[AddedLine]:
    """Pull (path, line, text) for every ``+`` line out of unified diff output."""
    added: list[AddedLine] = []
    path: str | None = None
    lineno = 0
    for raw in diff_text.splitlines():
        if raw.startswith("+++ "):
            target = raw[4:].strip()
            path = None if target == "/dev/null" else target.removeprefix("b/")
        elif raw.startswith("@@"):
            match = re.search(r"\+(\d+)", raw)
            lineno = int(match.group(1)) if match else 1
        elif raw.startswith("+") and not raw.startswith("+++"):
            if path is not None:
                added.append(AddedLine(path=path, line=lineno, text=raw[1:]))
            lineno += 1
    return added


def collect_added_lines(cwd: str, base: str | None = None, timeout: int = 300) -> DiffScan:
    """Gather every added line: pending changes, untracked files, and (when
    ``base`` is given) everything committed since ``base``."""
    code, _ = _git(["rev-parse", "--is-inside-work-tree"], cwd, timeout)
    if code != 0:
        return DiffScan(error="not a git repository")

    scan = DiffScan(base=base)

    if base:
        code, out = _git(["diff", f"{base}...HEAD", "--unified=0", "--no-color"], cwd, timeout)
        if code != 0:
            return DiffScan(error=f"git diff against `{base}` failed: {out.strip()[:200]}")
        scan.lines.extend(_parse_added(out))

    # Pending (staged + unstaged) changes against HEAD.
    code, out = _git(["diff", "HEAD", "--unified=0", "--no-color"], cwd, timeout)
    if code == 0 and out.strip():
        scan.tree_dirty = True
        scan.lines.extend(_parse_added(out))

    # Untracked files: every line in them is an added line.
    code, out = _git(["ls-files", "--others", "--exclude-standard"], cwd, timeout)
    if code == 0:
        for name in out.splitlines():
            name = name.strip()
            if not name:
                continue
            scan.tree_dirty = True
            file_path = Path(cwd) / name
            try:
                if file_path.stat().st_size > _MAX_UNTRACKED_BYTES:
                    continue
                text = file_path.read_text(encoding="utf-8", errors="strict")
            except (OSError, UnicodeDecodeError):
                continue  # unreadable or binary — nothing line-based to scan
            for lineno, line in enumerate(text.splitlines(), start=1):
                scan.lines.append(AddedLine(path=name, line=lineno, text=line))

    return scan


def _mask(value: str) -> str:
    if len(value) <= 8:
        return "********"
    return f"{value[:4]}…{value[-2:]}"


def find_new_todos(scan: DiffScan, limit: int = 20) -> list[str]:
    """``path:line — marker: excerpt`` for each added TODO/FIXME/HACK/XXX."""
    findings: list[str] = []
    for added in scan.lines:
        match = _TODO_PATTERN.search(added.text)
        if not match:
            continue
        findings.append(f"{added.path}:{added.line} — {match.group(1)}: {added.text.strip()[:120]}")
        if len(findings) >= limit:
            break
    return findings


def find_secrets(scan: DiffScan, limit: int = 20) -> list[str]:
    """``path:line — kind (masked)`` for each secret-shaped added line."""
    findings: list[str] = []
    for added in scan.lines:
        for kind, pattern in _SECRET_PATTERNS:
            match = pattern.search(added.text)
            if not match:
                continue
            value = match.groupdict().get("value") or match.group(0)
            if kind == "hardcoded credential" and _PLACEHOLDER.search(value):
                continue
            findings.append(f"{added.path}:{added.line} — {kind} ({_mask(value)})")
            break  # one finding per line is enough
        if len(findings) >= limit:
            break
    return findings
