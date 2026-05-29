"""Tests for report scoring and rendering."""

from veridict.models import (
    Claim,
    ClaimResult,
    ClaimType,
    Evidence,
    Report,
    Verdict,
)
from veridict.report import render_json, render_markdown, render_terminal


def _false_file_report():
    claim = Claim(ClaimType.FILE_EXISTS, "created x.py", target="x.py")
    result = ClaimResult(claim, Verdict.FALSE, Evidence("checked filesystem", detail="file does not exist"))
    return Report(claim_results=[result])


def test_trust_score_all_false_is_zero():
    assert _false_file_report().trust_score == 0


def test_render_json_contains_verdict():
    assert '"verdict": "false"' in render_json(_false_file_report())


def test_render_markdown_has_header_and_emoji():
    md = render_markdown(_false_file_report())
    assert "Veridict" in md
    assert "❌" in md


def test_render_terminal_does_not_raise():
    # Smoke test — rendering should never blow up.
    render_terminal(_false_file_report())


def test_unverifiable_excluded_from_score():
    verified = ClaimResult(
        Claim(ClaimType.FILE_EXISTS, "created a.py", target="a.py"),
        Verdict.TRUE,
        Evidence("checked filesystem", detail="file exists"),
    )
    unknown = ClaimResult(
        Claim(ClaimType.NO_ERRORS, "no errors"),
        Verdict.UNVERIFIABLE,
        Evidence("no precise check"),
    )
    report = Report(claim_results=[verified, unknown])
    # 1 verified / 1 decided == 100; the unverifiable claim is not counted.
    assert report.trust_score == 100
