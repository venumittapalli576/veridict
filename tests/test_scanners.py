"""Tests for the diff scanners (new TODOs, leaked secrets)."""

import subprocess

import pytest

from veridict.config import Config
from veridict.models import Claim, ClaimType, Verdict
from veridict.scanners import collect_added_lines, find_new_todos, find_secrets
from veridict.verifiers import run_checks, verify_claim

# Obviously fake fixtures, shaped like the real thing, assembled at runtime so
# the literals never appear in this repo's own diffs. The AWS key is Amazon's
# own documentation example.
FAKE_AWS_KEY = "AKIA" + "IOSFODNN7EXAMPLE"
FAKE_GH_TOKEN = "ghp_" + "a1B2" * 9  # 36 chars after the prefix


def _git(repo, *args):
    subprocess.run(
        ["git", "-c", "user.email=t@t.t", "-c", "user.name=t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-b", "main")
    (tmp_path / "base.py").write_text("x = 1\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "base")
    return tmp_path


def test_not_a_repo_reports_error(tmp_path):
    scan = collect_added_lines(str(tmp_path))
    assert scan.error == "not a git repository"


def test_clean_tree_saw_no_changes(repo):
    scan = collect_added_lines(str(repo))
    assert scan.error is None
    assert scan.saw_changes is False
    assert scan.lines == []


def test_untracked_file_lines_are_added_lines(repo):
    (repo / "new.py").write_text("a = 1\n# TODO: finish this\n")
    scan = collect_added_lines(str(repo))
    assert scan.saw_changes is True
    findings = find_new_todos(scan)
    assert len(findings) == 1
    assert findings[0].startswith("new.py:2")
    assert "TODO" in findings[0]


def test_pending_modification_is_scanned(repo):
    (repo / "base.py").write_text("x = 1\ny = 2  # FIXME: wrong\n")
    scan = collect_added_lines(str(repo))
    findings = find_new_todos(scan)
    assert len(findings) == 1
    assert findings[0].startswith("base.py:2")


def test_diff_base_covers_committed_changes(repo):
    base_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    (repo / "feature.py").write_text(f'token = "{FAKE_AWS_KEY}"\n')
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "feature")

    # Without a base, the clean tree hides the committed secret.
    assert collect_added_lines(str(repo)).saw_changes is False
    # With a base, the committed lines are scanned.
    scan = collect_added_lines(str(repo), base=base_sha)
    findings = find_secrets(scan)
    assert len(findings) == 1
    assert "AWS access key ID" in findings[0]


def test_diff_base_falls_back_when_merge_base_missing(repo):
    # An orphan branch shares no history with main, so `main...HEAD` has no
    # merge-base (like a shallow CI clone) and the two-dot fallback must kick in.
    _git(repo, "checkout", "--orphan", "detached-history")
    _git(repo, "rm", "-rf", "--cached", ".")
    (repo / "base.py").unlink()
    (repo / "orphan.py").write_text("# TODO: orphan work\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "orphan")

    scan = collect_added_lines(str(repo), base="main")
    assert scan.error is None
    assert any("orphan.py" in f for f in find_new_todos(scan))


def test_secret_is_masked_in_findings(repo):
    (repo / "cfg.py").write_text(f'gh = "{FAKE_GH_TOKEN}"\n')
    findings = find_secrets(collect_added_lines(str(repo)))
    assert len(findings) == 1
    assert FAKE_GH_TOKEN not in findings[0]
    assert "GitHub token" in findings[0]


def test_placeholder_credentials_are_ignored(repo):
    (repo / "cfg.py").write_text('password = "your-password-here"\napi_key = "<API_KEY_PLACEHOLDER>"\n')
    assert find_secrets(collect_added_lines(str(repo))) == []


def test_hardcoded_credential_detected(repo):
    fake = "hunter2" * 3  # assembled so the literal never sits in this repo
    (repo / "cfg.py").write_text(f'db_password = "{fake}"\n')
    findings = find_secrets(collect_added_lines(str(repo)))
    assert len(findings) == 1
    assert "hardcoded credential" in findings[0]


# -- claim-level integration ------------------------------------------------


def test_no_secrets_claim_false_when_secret_added(repo):
    (repo / "cfg.py").write_text(f'key = "{FAKE_AWS_KEY}"\n')
    claim = Claim(ClaimType.NO_SECRETS, "no secrets committed")
    result = verify_claim(claim, Config(), str(repo))
    assert result.verdict is Verdict.FALSE
    assert FAKE_AWS_KEY not in result.evidence.output  # masked


def test_no_new_todos_claim_true_when_diff_clean(repo):
    (repo / "ok.py").write_text("done = True\n")
    claim = Claim(ClaimType.NO_NEW_TODOS, "no TODOs left")
    assert verify_claim(claim, Config(), str(repo)).verdict is Verdict.TRUE


def test_scanner_claims_unverifiable_on_clean_tree(repo):
    claim = Claim(ClaimType.NO_SECRETS, "no secrets committed")
    assert verify_claim(claim, Config(), str(repo)).verdict is Verdict.UNVERIFIABLE


def test_scanner_claims_unverifiable_outside_git(tmp_path):
    claim = Claim(ClaimType.NO_NEW_TODOS, "no TODOs left")
    assert verify_claim(claim, Config(), str(tmp_path)).verdict is Verdict.UNVERIFIABLE


# -- `veridict run` integration ----------------------------------------------


def test_run_checks_includes_enabled_scanners(repo):
    (repo / "leak.py").write_text(f'key = "{FAKE_AWS_KEY}"\n# TODO: remove\n')
    cfg = Config(checks={"no_secrets": True, "no_new_todos": True}, required=["no_secrets"])
    results = {c.name: c for c in run_checks(cfg, str(repo))}
    assert results["no_secrets"].ok is False
    assert results["no_secrets"].required is True
    assert results["no_new_todos"].ok is False


def test_run_checks_scanners_pass_on_clean_tree(repo):
    cfg = Config(checks={"no_secrets": True, "no_new_todos": True})
    results = {c.name: c for c in run_checks(cfg, str(repo))}
    assert results["no_secrets"].ok is True
    assert results["no_new_todos"].ok is True


def test_run_checks_skips_scanners_outside_git(tmp_path):
    cfg = Config(checks={"no_secrets": True, "no_new_todos": True})
    assert run_checks(cfg, str(tmp_path)) == []


def test_run_checks_respects_disabled_scanners(repo):
    (repo / "leak.py").write_text(f'key = "{FAKE_AWS_KEY}"\n')
    cfg = Config(checks={"no_secrets": False, "no_new_todos": False})
    assert run_checks(cfg, str(repo)) == []
