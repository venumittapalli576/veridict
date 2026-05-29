"""Establish ground truth: actually run the checks and inspect the filesystem.

Nothing here trusts the agent's words. A claim of "tests pass" is verified by
*running the tests*; a claim of "created foo.py" is verified by *looking for
foo.py*. Each verifier returns a :class:`Verdict` plus the :class:`Evidence`
that produced it, so every conclusion is auditable.
"""

from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path

from veridict.config import Config
from veridict.models import (
    CheckResult,
    Claim,
    ClaimResult,
    ClaimType,
    Evidence,
    Verdict,
)

_MAX_OUTPUT = 2000  # characters of command output kept as evidence


def _trim(text: str) -> str:
    text = (text or "").strip()
    if len(text) <= _MAX_OUTPUT:
        return text
    return "…(trimmed)…\n" + text[-_MAX_OUTPUT:]


def run_command(command: str, cwd: str, timeout: int) -> tuple[int | None, str]:
    """Run ``command`` in a shell and return ``(exit_code, output)``.

    ``exit_code`` is ``None`` when the command timed out (i.e. we could not
    determine an outcome).
    """
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, _trim(proc.stdout)
    except subprocess.TimeoutExpired:
        return None, f"timed out after {timeout}s"


@lru_cache(maxsize=64)
def _is_git_repo(cwd: str) -> bool:
    code, _ = run_command("git rev-parse --is-inside-work-tree", cwd, timeout=15)
    return code == 0


def _git_shows_change(target: str, cwd: str) -> bool | None:
    """True/False if git can decide whether ``target`` has pending changes.

    Returns ``None`` when git cannot help (not a repo). A return of ``False``
    means git sees no working-tree change for the file (it may still exist).
    """
    if not _is_git_repo(cwd):
        return None
    code, out = run_command(f'git status --porcelain -- "{target}"', cwd, timeout=30)
    if code != 0:
        return None
    return bool(out.strip())


def _verify_command_slot(claim: Claim, slot: str, config: Config, cwd: str) -> ClaimResult:
    command = config.command_for(slot)
    if not command:
        return ClaimResult(
            claim,
            Verdict.UNVERIFIABLE,
            Evidence(method=f"no `{slot}` command configured", detail=f"set commands.{slot} in .veridict.yaml"),
        )
    code, out = run_command(command, cwd, config.timeout)
    if code is None:
        return ClaimResult(
            claim,
            Verdict.UNVERIFIABLE,
            Evidence(method=f"ran `{command}`", exit_code=None, detail="command timed out", output=out),
        )
    verdict = Verdict.TRUE if code == 0 else Verdict.FALSE
    detail = "passed" if code == 0 else f"exited {code}"
    return ClaimResult(claim, verdict, Evidence(method=f"ran `{command}`", exit_code=code, detail=detail, output=out))


def _verify_file_exists(claim: Claim, cwd: str) -> ClaimResult:
    target = claim.target or ""
    exists = (Path(cwd) / target).exists()
    return ClaimResult(
        claim,
        Verdict.TRUE if exists else Verdict.FALSE,
        Evidence(
            method="checked filesystem",
            detail="file exists" if exists else "file does not exist",
        ),
    )


def _verify_file_modified(claim: Claim, cwd: str) -> ClaimResult:
    target = claim.target or ""
    exists = (Path(cwd) / target).exists()
    if not exists:
        return ClaimResult(
            claim,
            Verdict.FALSE,
            Evidence(method="checked filesystem", detail="file does not exist, so it cannot have been modified"),
        )
    changed = _git_shows_change(target, cwd)
    if changed is True:
        return ClaimResult(
            claim,
            Verdict.TRUE,
            Evidence(method="checked `git status`", detail="file has pending changes"),
        )
    if changed is False:
        return ClaimResult(
            claim,
            Verdict.UNVERIFIABLE,
            Evidence(
                method="checked `git status`",
                detail="no pending changes (already committed, or not modified) — run before committing to confirm",
            ),
        )
    # Not a git repo: existence is all we can prove.
    return ClaimResult(
        claim,
        Verdict.UNVERIFIABLE,
        Evidence(method="checked filesystem", detail="file exists, but no VCS available to confirm a modification"),
    )


def _verify_command_succeeds(claim: Claim, config: Config, cwd: str) -> ClaimResult:
    command = claim.target
    if not command:
        return ClaimResult(claim, Verdict.UNVERIFIABLE, Evidence(method="no command captured"))
    code, out = run_command(command, cwd, config.timeout)
    if code is None:
        return ClaimResult(
            claim,
            Verdict.UNVERIFIABLE,
            Evidence(method=f"ran `{command}`", detail="timed out", output=out),
        )
    verdict = Verdict.TRUE if code == 0 else Verdict.FALSE
    return ClaimResult(
        claim,
        verdict,
        Evidence(
            method=f"ran `{command}`",
            exit_code=code,
            detail="passed" if code == 0 else f"exited {code}",
            output=out,
        ),
    )


_SLOT_FOR_CLAIM = {
    ClaimType.TESTS_PASS: "tests",
    ClaimType.BUILD_PASSES: "build",
    ClaimType.LINT_PASSES: "lint",
    ClaimType.TYPECHECK_PASSES: "typecheck",
}


def verify_claim(claim: Claim, config: Config, cwd: str) -> ClaimResult:
    """Independently verify a single :class:`Claim`."""
    if claim.type in _SLOT_FOR_CLAIM:
        return _verify_command_slot(claim, _SLOT_FOR_CLAIM[claim.type], config, cwd)
    if claim.type is ClaimType.FILE_EXISTS:
        return _verify_file_exists(claim, cwd)
    if claim.type is ClaimType.FILE_MODIFIED:
        return _verify_file_modified(claim, cwd)
    if claim.type is ClaimType.COMMAND_SUCCEEDS:
        return _verify_command_succeeds(claim, config, cwd)
    # NO_ERRORS and UNKNOWN are too vague to check without guessing.
    return ClaimResult(
        claim,
        Verdict.UNVERIFIABLE,
        Evidence(method="no precise check", detail="claim is too vague to verify without guessing"),
    )


def run_checks(config: Config, cwd: str) -> list[CheckResult]:
    """Run every configured command and report whether each passed."""
    results: list[CheckResult] = []
    for slot in ("tests", "build", "lint", "typecheck"):
        command = config.command_for(slot)
        if not command:
            continue
        code, out = run_command(command, cwd, config.timeout)
        ok = code == 0
        if code is None:
            detail = "timed out"
        elif ok:
            detail = "passed"
        else:
            detail = f"exited {code}"
        results.append(
            CheckResult(
                name=slot,
                ok=ok,
                required=slot in config.required,
                evidence=Evidence(method=f"ran `{command}`", exit_code=code, detail=detail, output=out),
            )
        )
    return results
