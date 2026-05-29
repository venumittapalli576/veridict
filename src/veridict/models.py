"""Core data models shared across Veridict.

The design separates three ideas deliberately:

* A :class:`Claim` is *something an AI agent said it did* ("all tests pass",
  "created ``auth.py``"). Claims are untrusted by definition.
* A :class:`CheckResult` / :class:`ClaimResult` is *ground truth* that Veridict
  established by actually doing the work (running the suite, hitting the disk).
* A :class:`Verdict` is the reconciliation of the two: did reality back up the
  claim, contradict it, or was it impossible to check?
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ClaimType(str, Enum):
    """The kinds of claims Veridict knows how to verify."""

    TESTS_PASS = "tests_pass"
    BUILD_PASSES = "build_passes"
    LINT_PASSES = "lint_passes"
    TYPECHECK_PASSES = "typecheck_passes"
    FILE_EXISTS = "file_exists"
    FILE_MODIFIED = "file_modified"
    COMMAND_SUCCEEDS = "command_succeeds"
    NO_ERRORS = "no_errors"
    UNKNOWN = "unknown"


class Verdict(str, Enum):
    """The outcome of reconciling a claim against ground truth."""

    TRUE = "true"  # the agent told the truth
    FALSE = "false"  # the agent's claim is contradicted by reality
    UNVERIFIABLE = "unverifiable"  # Veridict has no way to check this claim


@dataclass
class Claim:
    """Something an AI agent asserted it accomplished."""

    type: ClaimType
    text: str
    target: str | None = None  # filename, command, etc. (claim-type dependent)
    line: int | None = None  # 1-based line in the source transcript

    def label(self) -> str:
        if self.target:
            return f"{self.type.value} → {self.target}"
        return self.type.value


@dataclass
class Evidence:
    """How Veridict reached a conclusion, kept for the audit trail."""

    method: str  # e.g. "ran `pytest -q`" or "checked filesystem"
    exit_code: int | None = None
    detail: str = ""  # one-line human explanation
    output: str = ""  # captured (trimmed) command output, if any

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class ClaimResult:
    """A claim plus the verdict Veridict reached on it."""

    claim: Claim
    verdict: Verdict
    evidence: Evidence

    @property
    def is_lie(self) -> bool:
        return self.verdict is Verdict.FALSE


@dataclass
class CheckResult:
    """The result of a configured ground-truth check (used by ``veridict run``)."""

    name: str
    ok: bool
    required: bool
    evidence: Evidence


@dataclass
class Report:
    """Everything Veridict learned during a run, ready to be rendered."""

    claim_results: list[ClaimResult] = field(default_factory=list)
    check_results: list[CheckResult] = field(default_factory=list)
    target: str = "."

    # -- claim tallies ---------------------------------------------------
    @property
    def verified(self) -> list[ClaimResult]:
        return [r for r in self.claim_results if r.verdict is Verdict.TRUE]

    @property
    def lies(self) -> list[ClaimResult]:
        return [r for r in self.claim_results if r.verdict is Verdict.FALSE]

    @property
    def unverifiable(self) -> list[ClaimResult]:
        return [r for r in self.claim_results if r.verdict is Verdict.UNVERIFIABLE]

    # -- check tallies ---------------------------------------------------
    @property
    def failed_checks(self) -> list[CheckResult]:
        return [c for c in self.check_results if not c.ok]

    @property
    def failed_required_checks(self) -> list[CheckResult]:
        return [c for c in self.check_results if c.required and not c.ok]

    # -- scoring ---------------------------------------------------------
    @property
    def trust_score(self) -> int | None:
        """A 0–100 trust score, or ``None`` when there is nothing to score.

        Claims drive the score when present (this is the headline number for
        ``veridict check``); otherwise configured checks do (for ``veridict
        run``). Unverifiable claims are intentionally excluded — we score what
        we could actually prove, not what we couldn't.
        """
        decided = self.verified + self.lies
        if decided:
            return round(100 * len(self.verified) / len(decided))
        if self.check_results:
            passed = sum(1 for c in self.check_results if c.ok)
            return round(100 * passed / len(self.check_results))
        return None

    @property
    def headline(self) -> str:
        """A short, human verdict suitable for a header line."""
        if self.lies:
            n = len(self.lies)
            return f"Caught {n} false claim{'s' if n != 1 else ''}"
        score = self.trust_score
        if score is None:
            return "Nothing to verify"
        if self.failed_required_checks:
            return "Required checks failed"
        if score == 100:
            return "Verified — claims hold up"
        return "Mostly verified"

    @property
    def exit_code(self) -> int:
        """Process exit code: non-zero means a human should look."""
        if self.lies or self.failed_required_checks:
            return 1
        return 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "trust_score": self.trust_score,
            "headline": self.headline,
            "summary": {
                "verified": len(self.verified),
                "false": len(self.lies),
                "unverifiable": len(self.unverifiable),
                "checks_passed": sum(1 for c in self.check_results if c.ok),
                "checks_failed": len(self.failed_checks),
            },
            "claims": [
                {
                    "type": r.claim.type.value,
                    "target": r.claim.target,
                    "text": r.claim.text,
                    "line": r.claim.line,
                    "verdict": r.verdict.value,
                    "evidence": r.evidence.as_dict(),
                }
                for r in self.claim_results
            ],
            "checks": [
                {
                    "name": c.name,
                    "ok": c.ok,
                    "required": c.required,
                    "evidence": c.evidence.as_dict(),
                }
                for c in self.check_results
            ],
        }
