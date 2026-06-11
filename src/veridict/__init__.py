"""Veridict — independently verify what your AI coding agent claims it did.

Veridict ignores what the transcript *says* and re-derives ground truth by
actually running the checks, then renders a verdict on each claim.
"""

from veridict.models import (
    CheckResult,
    Claim,
    ClaimResult,
    ClaimType,
    Evidence,
    Report,
    Verdict,
)

__version__ = "0.2.0"

__all__ = [
    "__version__",
    "Claim",
    "ClaimResult",
    "ClaimType",
    "CheckResult",
    "Evidence",
    "Report",
    "Verdict",
]
