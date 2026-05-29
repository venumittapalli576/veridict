"""Orchestration: turn input + config into a :class:`Report`."""

from __future__ import annotations

from veridict.claims import extract_claims
from veridict.config import Config
from veridict.models import Report
from veridict.verifiers import run_checks, verify_claim


def verify_transcript(text: str, config: Config, cwd: str = ".") -> Report:
    """Extract claims from an agent transcript and verify each against reality."""
    results = [verify_claim(claim, config, cwd) for claim in extract_claims(text)]
    return Report(claim_results=results, target=cwd)


def run_project(config: Config, cwd: str = ".") -> Report:
    """Run all configured ground-truth checks for a project."""
    return Report(check_results=run_checks(config, cwd), target=cwd)
