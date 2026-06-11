"""Extract verifiable claims from an AI agent's natural-language summary.

This is deliberately transparent and pattern-based rather than a black box: you
can read every rule below, and add your own. The goal is high precision on the
claims agents *actually* make ("all tests pass", "created ``auth.py``") rather
than trying to understand arbitrary prose. Anything not matched here is simply
not claimed, and therefore never produces a false sense of verification.

For fully reliable input, an agent (or you) can also emit a structured config
instead of relying on extraction — see ``veridict run`` and ``.veridict.yaml``.
"""

from __future__ import annotations

import re

from veridict.models import Claim, ClaimType

# A filename token: optional path segments + a stem + an *alphabetic* extension.
# Requiring an alphabetic extension keeps version strings like "3.12" or "v0.1"
# from being mistaken for files.
_FILE = r"(?:[\w-]+[\\/])*[\w.-]*[A-Za-z0-9]\.[A-Za-z]{1,8}"
_WRAP = r"[`'\"(\[]?"  # optional opening quote/bracket around a filename

# Simple, target-less claims: (type, compiled pattern). Case-insensitive.
_SIMPLE_PATTERNS: list[tuple[ClaimType, re.Pattern[str]]] = [
    (
        ClaimType.TESTS_PASS,
        re.compile(
            r"\b(all\s+|the\s+)?(unit\s+|integration\s+|e2e\s+)?tests?\b[^.\n]{0,40}?"
            r"\b(pass(?:ed|es|ing)?|are\s+green|succeed(?:ed|s)?|are\s+passing|green)\b",
            re.IGNORECASE,
        ),
    ),
    (
        ClaimType.TESTS_PASS,
        re.compile(r"\btest\s+suite\b[^.\n]{0,40}?\b(pass(?:es|ed)?|green|succeeds?)\b", re.IGNORECASE),
    ),
    (
        ClaimType.BUILD_PASSES,
        re.compile(
            r"\b(build|compilation)\b[^.\n]{0,40}?"
            r"\b(succeed(?:ed|s)?|passes|is\s+green|works|successful|complete[ds]?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        ClaimType.BUILD_PASSES,
        re.compile(r"\b(builds?|compiles?)\b[^.\n]{0,20}?\b(successfully|cleanly|without\s+errors?)\b", re.IGNORECASE),
    ),
    (
        ClaimType.LINT_PASSES,
        re.compile(
            r"\b(lint(?:ing|er)?|ruff|eslint|flake8|pylint)\b[^.\n]{0,40}?"
            r"\b(pass(?:es|ed)?|clean|is\s+clean|happy|no\s+(?:issues|errors|warnings))\b",
            re.IGNORECASE,
        ),
    ),
    (
        ClaimType.LINT_PASSES,
        re.compile(r"\bno\s+lint(?:ing)?\s+(?:errors|issues|warnings)\b", re.IGNORECASE),
    ),
    (
        ClaimType.TYPECHECK_PASSES,
        re.compile(
            r"\b(type[\s-]?check(?:ing|s|ed)?|mypy|pyright|tsc)\b[^.\n]{0,40}?"
            r"\b(pass(?:es|ed)?|clean|happy|no\s+errors)\b",
            re.IGNORECASE,
        ),
    ),
    (
        ClaimType.TYPECHECK_PASSES,
        re.compile(r"\bno\s+type\s+errors?\b", re.IGNORECASE),
    ),
    (
        ClaimType.NO_NEW_TODOS,
        re.compile(
            r"\b(?:no\s+(?:new\s+|remaining\s+|outstanding\s+|leftover\s+)?(?:todos?|fixmes?)\b"
            r"|(?:removed|resolved|cleaned\s+up|addressed)\s+(?:all\s+)?(?:the\s+)?(?:remaining\s+)?(?:todos?|fixmes?)\b"
            r"|no\s+todos?\s+(?:left|remain(?:ing)?)\b)",
            re.IGNORECASE,
        ),
    ),
    (
        ClaimType.NO_SECRETS,
        re.compile(
            r"\b(?:no\s+(?:hard[-\s]?coded\s+)?(?:secrets?|credentials?|api[-\s]?keys?)\b"
            r"|no\s+(?:secrets?|credentials?|keys?|tokens?)\s+(?:were\s+|are\s+)?"
            r"(?:committed|exposed|leaked|hard[-\s]?coded|included|added)\b"
            r"|(?:didn't|did\s+not|haven't|have\s+not)\s+(?:commit|include|add|expose|leak|hard[-\s]?code)\w*\s"
            r"[^.\n]{0,30}?(?:secrets?|credentials?|api[-\s]?keys?|tokens?)\b)",
            re.IGNORECASE,
        ),
    ),
    (
        ClaimType.NO_ERRORS,
        re.compile(r"\b(no\s+errors?|error[-\s]free|without\s+(?:any\s+)?errors?|everything\s+works)\b", re.IGNORECASE),
    ),
]

# Filename-bearing claims.
_CREATED_VERBS = r"(?:creat(?:e|ed|ing)|add(?:ed|ing)?|wrote|writ(?:e|ten)|generat(?:e|ed)|introduc(?:e|ed)|new\s+file)"
_MODIFIED_VERBS = r"(?:updat(?:e|ed)|modif(?:y|ied)|edit(?:ed)?|chang(?:e|ed)|refactor(?:ed)?|patch(?:ed)?|fix(?:ed)?)"

_CREATED_PATTERN = re.compile(
    rf"\b{_CREATED_VERBS}\b[^\n]{{0,60}}?{_WRAP}(?P<target>{_FILE})", re.IGNORECASE
)
_MODIFIED_PATTERN = re.compile(
    rf"\b{_MODIFIED_VERBS}\b[^\n]{{0,60}}?{_WRAP}(?P<target>{_FILE})", re.IGNORECASE
)


def _normalize_target(raw: str) -> str | None:
    target = raw.strip().strip("`'\"()[]<>,.")
    target = target.replace("\\", "/")
    return target or None


def extract_claims(text: str) -> list[Claim]:
    """Parse ``text`` and return the verifiable claims found, de-duplicated."""
    claims: list[Claim] = []
    seen: set[tuple[ClaimType, str | None]] = set()

    def add(ctype: ClaimType, line_text: str, lineno: int, target: str | None = None) -> None:
        key = (ctype, target)
        if key in seen:
            return
        seen.add(key)
        claims.append(Claim(type=ctype, text=line_text.strip()[:200], target=target, line=lineno))

    for lineno, line in enumerate(text.splitlines(), start=1):
        for ctype, pattern in _SIMPLE_PATTERNS:
            if pattern.search(line):
                add(ctype, line, lineno)

        for match in _CREATED_PATTERN.finditer(line):
            target = _normalize_target(match.group("target"))
            if target:
                add(ClaimType.FILE_EXISTS, line, lineno, target)

        for match in _MODIFIED_PATTERN.finditer(line):
            target = _normalize_target(match.group("target"))
            # A "created" claim already implies the file should exist; don't
            # double-count the same path as merely "modified".
            if target and (ClaimType.FILE_EXISTS, target) not in seen:
                add(ClaimType.FILE_MODIFIED, line, lineno, target)

    return claims
