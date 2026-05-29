"""Tests for the ground-truth verifiers."""

import sys

from veridict.config import Config
from veridict.models import Claim, ClaimType, Verdict
from veridict.verifiers import run_checks, run_command, verify_claim

PY = f'"{sys.executable}"'
FAIL = f'{PY} -c "import sys; sys.exit(1)"'
OK = f'{PY} -c "import sys; sys.exit(0)"'


def test_run_command_captures_exit_and_output(tmp_path):
    code, out = run_command(f'{PY} -c "print(\'hello\')"', str(tmp_path), 30)
    assert code == 0
    assert "hello" in out


def test_file_exists_true(tmp_path):
    (tmp_path / "a.py").write_text("x = 1")
    claim = Claim(ClaimType.FILE_EXISTS, "created a.py", target="a.py")
    assert verify_claim(claim, Config(), str(tmp_path)).verdict is Verdict.TRUE


def test_file_exists_false(tmp_path):
    claim = Claim(ClaimType.FILE_EXISTS, "created ghost.py", target="ghost.py")
    assert verify_claim(claim, Config(), str(tmp_path)).verdict is Verdict.FALSE


def test_tests_claim_false_when_command_fails(tmp_path):
    cfg = Config(commands={"tests": FAIL})
    claim = Claim(ClaimType.TESTS_PASS, "all tests pass")
    assert verify_claim(claim, cfg, str(tmp_path)).verdict is Verdict.FALSE


def test_tests_claim_true_when_command_passes(tmp_path):
    cfg = Config(commands={"tests": OK})
    claim = Claim(ClaimType.TESTS_PASS, "all tests pass")
    assert verify_claim(claim, cfg, str(tmp_path)).verdict is Verdict.TRUE


def test_tests_claim_unverifiable_without_command(tmp_path):
    claim = Claim(ClaimType.TESTS_PASS, "all tests pass")
    assert verify_claim(claim, Config(), str(tmp_path)).verdict is Verdict.UNVERIFIABLE


def test_modified_missing_file_is_false(tmp_path):
    claim = Claim(ClaimType.FILE_MODIFIED, "updated ghost.py", target="ghost.py")
    assert verify_claim(claim, Config(), str(tmp_path)).verdict is Verdict.FALSE


def test_run_checks_reports_required(tmp_path):
    cfg = Config(commands={"tests": OK}, required=["tests"])
    checks = run_checks(cfg, str(tmp_path))
    assert len(checks) == 1
    assert checks[0].ok is True
    assert checks[0].required is True
