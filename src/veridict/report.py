"""Render a :class:`Report` as a terminal view, JSON, or Markdown."""

from __future__ import annotations

import json

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from veridict.models import Report, Verdict

# verdict -> (icon, rich style, label, markdown emoji)
_VERDICT = {
    Verdict.TRUE: ("✔", "green", "true", "✅"),
    Verdict.FALSE: ("✘", "bold red", "FALSE", "❌"),
    Verdict.UNVERIFIABLE: ("?", "yellow", "unverifiable", "⚠️"),
}


def _score_style(report: Report) -> str:
    if report.lies:
        return "bold red"
    score = report.trust_score
    if score is None:
        return "dim"
    if score >= 90:
        return "bold green"
    if score >= 60:
        return "yellow"
    return "bold red"


def _score_text(report: Report) -> str:
    score = report.trust_score
    return "n/a" if score is None else f"{score}/100"


def render_terminal(report: Report, console: Console | None = None, show_output: bool = False) -> None:
    """Pretty-print the report to the terminal."""
    # legacy_windows=False avoids the win32 console path, which chokes on
    # non-cp1252 glyphs when output is redirected.
    console = console or Console(legacy_windows=False)
    style = _score_style(report)

    header = Text()
    header.append("VERIDICT", style="bold white")
    header.append("  ·  ")
    header.append(report.headline, style=style)
    header.append("  ·  trust ")
    header.append(_score_text(report), style=style)
    console.print(Panel(header, border_style=style, expand=False))

    if report.claim_results:
        table = Table(title="Claims vs. reality", title_justify="left", header_style="bold", expand=True)
        table.add_column("Verdict", no_wrap=True)
        table.add_column("Claim", overflow="fold")
        table.add_column("Evidence", overflow="fold")
        for result in report.claim_results:
            icon, st, label, _ = _VERDICT[result.verdict]
            table.add_row(Text(f"{icon} {label}", style=st), result.claim.label(), result.evidence.detail)
        console.print(table)

    if report.check_results:
        table = Table(title="Ground-truth checks", title_justify="left", header_style="bold", expand=True)
        table.add_column("Result", no_wrap=True)
        table.add_column("Check", no_wrap=True)
        table.add_column("Evidence", overflow="fold")
        for check in report.check_results:
            if check.ok:
                result_cell = Text("✔ pass", style="green")
            else:
                result_cell = Text("✘ fail", style="bold red")
            name = check.name + ("  (required)" if check.required else "")
            table.add_row(result_cell, name, check.evidence.detail)
        console.print(table)

    # Optionally surface captured output for anything that went wrong.
    if show_output:
        flagged = [r for r in report.claim_results if r.verdict is Verdict.FALSE and r.evidence.output]
        flagged += [c for c in report.check_results if not c.ok and c.evidence.output]  # type: ignore[arg-type]
        for item in flagged:
            console.print(Panel(item.evidence.output, title=item.evidence.method, border_style="red", expand=False))

    summary = (
        f"{len(report.verified)} verified · {len(report.lies)} false · "
        f"{len(report.unverifiable)} unverifiable"
    )
    console.print(Text(summary, style="dim"))


def render_json(report: Report) -> str:
    return json.dumps(report.to_dict(), indent=2)


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render_markdown(report: Report) -> str:
    """Render a compact Markdown summary, suitable for a PR comment."""
    lines: list[str] = []
    score = report.trust_score
    badge = "❌" if report.lies else ("✅" if (score or 0) >= 90 else "⚠️")
    lines.append(f"### {badge} Veridict — {report.headline}  ·  trust **{_score_text(report)}**")
    lines.append("")

    if report.claim_results:
        lines.append("| Verdict | Claim | Evidence |")
        lines.append("| --- | --- | --- |")
        for result in report.claim_results:
            _, _, label, emoji = _VERDICT[result.verdict]
            lines.append(
                f"| {emoji} {label} | `{_md_escape(result.claim.label())}` | {_md_escape(result.evidence.detail)} |"
            )
        lines.append("")

    if report.check_results:
        lines.append("| Result | Check | Evidence |")
        lines.append("| --- | --- | --- |")
        for check in report.check_results:
            emoji = "✅" if check.ok else "❌"
            name = check.name + (" (required)" if check.required else "")
            lines.append(f"| {emoji} | `{name}` | {_md_escape(check.evidence.detail)} |")
        lines.append("")

    lines.append(
        f"_{len(report.verified)} verified · {len(report.lies)} false · "
        f"{len(report.unverifiable)} unverifiable_"
    )
    return "\n".join(lines)
