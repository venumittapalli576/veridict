"""Smoke tests for the command-line interface."""

from typer.testing import CliRunner

from veridict import __version__
from veridict.cli import app

runner = CliRunner()


def test_version_command():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_init_creates_config_and_refuses_overwrite(tmp_path):
    first = runner.invoke(app, ["init", "--path", str(tmp_path)])
    assert first.exit_code == 0
    assert (tmp_path / ".veridict.yaml").exists()

    second = runner.invoke(app, ["init", "--path", str(tmp_path)])
    assert second.exit_code == 1  # already exists, no --force


def test_check_file_claim_false_exits_nonzero(tmp_path):
    transcript = tmp_path / "summary.md"
    transcript.write_text("I created `ghost.py`.")
    result = runner.invoke(app, ["check", str(transcript), "--path", str(tmp_path), "--json"])
    assert result.exit_code == 1
    assert '"verdict": "false"' in result.output


def test_check_file_claim_true_markdown(tmp_path):
    (tmp_path / "real.py").write_text("x = 1")
    transcript = tmp_path / "summary.md"
    transcript.write_text("Created `real.py`.")
    result = runner.invoke(app, ["check", str(transcript), "--path", str(tmp_path), "--md"])
    assert result.exit_code == 0
    assert "Veridict" in result.output


def test_check_reads_stdin(tmp_path):
    result = runner.invoke(app, ["check", "--path", str(tmp_path)], input="I created `ghost.py`.\n")
    assert result.exit_code == 1


def test_run_empty_project_is_clean(tmp_path):
    result = runner.invoke(app, ["run", "--path", str(tmp_path), "--json"])
    assert result.exit_code == 0
    assert '"trust_score": null' in result.output
