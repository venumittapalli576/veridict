"""The ``veridict`` command-line interface."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from veridict import __version__
from veridict.config import init_scaffold, load_config
from veridict.engine import run_project, verify_transcript
from veridict.models import Report
from veridict.report import render_json, render_markdown, render_terminal

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Veridict — independently verify what your AI coding agent claims it did.",
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"veridict {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Show version and exit."
    ),
) -> None:
    """Don't trust your AI agent's summary — verify it."""


def _emit(report: Report, json_out: bool, markdown: bool, verbose: bool, json_file: Path | None = None) -> None:
    if json_out:
        typer.echo(render_json(report))
    elif markdown:
        typer.echo(render_markdown(report))
    else:
        render_terminal(report, show_output=verbose)
    if json_file is not None:
        json_file.write_text(render_json(report) + "\n", encoding="utf-8")


def _finish(report: Report, strict: bool) -> None:
    code = report.exit_code
    if strict and code == 0 and report.unverifiable:
        code = 1
    raise typer.Exit(code)


@app.command()
def check(
    transcript: Path | None = typer.Argument(
        None, help="File with the agent's summary. Omit to read from stdin."
    ),
    path: Path = typer.Option(Path("."), "--path", "-p", help="Project directory to verify against."),
    json_out: bool = typer.Option(False, "--json", help="Emit the report as JSON."),
    markdown: bool = typer.Option(
        False, "--md", "--markdown", help="Emit the report as Markdown (good for PR comments)."
    ),
    strict: bool = typer.Option(False, "--strict", help="Exit non-zero if any claim is unverifiable, too."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show captured output for false claims."),
    diff_base: str | None = typer.Option(
        None, "--diff-base", help="Git ref to diff against (e.g. origin/main) — scanners check everything added since."
    ),
    json_file: Path | None = typer.Option(
        None, "--json-file", help="Also write the JSON report to this file (regardless of stdout format)."
    ),
) -> None:
    """Verify the claims in an AI agent's summary against reality.

    Pipe an agent's final message in and Veridict will re-run the checks it
    bragged about — catching "all tests pass" when they don't.
    """
    if transcript is not None:
        text = transcript.read_text(encoding="utf-8")
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        typer.echo("No transcript provided. Pass a file path or pipe text via stdin.", err=True)
        raise typer.Exit(2)

    config, _ = load_config(path)
    if diff_base:
        config.diff_base = diff_base
    report = verify_transcript(text, config, str(path))
    _emit(report, json_out, markdown, verbose, json_file)
    _finish(report, strict)


@app.command()
def run(
    path: Path = typer.Option(Path("."), "--path", "-p", help="Project directory to verify."),
    json_out: bool = typer.Option(False, "--json", help="Emit the report as JSON."),
    markdown: bool = typer.Option(False, "--md", "--markdown", help="Emit the report as Markdown."),
    strict: bool = typer.Option(False, "--strict", help="Treat unconfigured/unverifiable as failure."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show captured output for failed checks."),
    diff_base: str | None = typer.Option(
        None, "--diff-base", help="Git ref to diff against (e.g. origin/main) — scanners check everything added since."
    ),
    json_file: Path | None = typer.Option(
        None, "--json-file", help="Also write the JSON report to this file (regardless of stdout format)."
    ),
) -> None:
    """Run every configured ground-truth check (a CI / pre-commit gate).

    Reads ``.veridict.yaml`` if present, otherwise auto-detects how to test and
    build the project.
    """
    config, _ = load_config(path)
    if diff_base:
        config.diff_base = diff_base
    report = run_project(config, str(path))
    _emit(report, json_out, markdown, verbose, json_file)
    _finish(report, strict)


@app.command()
def init(
    path: Path = typer.Option(Path("."), "--path", "-p", help="Where to write .veridict.yaml."),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing config."),
) -> None:
    """Scaffold a ``.veridict.yaml`` (pre-filled with auto-detected commands)."""
    try:
        target = init_scaffold(path, force=force)
    except FileExistsError as exc:
        typer.echo(f"{exc} already exists — use --force to overwrite.", err=True)
        raise typer.Exit(1) from None
    typer.echo(f"Wrote {target}")


@app.command()
def version() -> None:
    """Print the Veridict version."""
    typer.echo(f"veridict {__version__}")


def _enable_utf8_output() -> None:
    """Make stdout/stderr UTF-8.

    On Windows, redirected output defaults to cp1252, which cannot encode the
    box-drawing and check glyphs Veridict prints — so without this the tool
    crashes when its output is piped. Best-effort: a no-op where unsupported.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="backslashreplace")
            except (ValueError, OSError):
                pass


def main() -> None:
    """Console-script entry point."""
    _enable_utf8_output()
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
