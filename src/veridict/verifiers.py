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
from veridict.scanners import DiffScan, collect_added_lines, find_new_todos, find_secrets

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

# Built-in diff scanners shared by claims and `veridict run` checks:
# name -> (finder, what a finding means, what a clean scan means)
_SCANNERS = {
    "no_new_todos": (find_new_todos, "added TODO/FIXME markers", "no new TODO/FIXME markers in added lines"),
    "no_secrets": (find_secrets, "secret-shaped values in added lines", "no secrets detected in added lines"),
}

_SCANNER_FOR_CLAIM = {
    ClaimType.NO_NEW_TODOS: "no_new_todos",
    ClaimType.NO_SECRETS: "no_secrets",
}


def _verify_scanner_claim(claim: Claim, scanner: str, config: Config, cwd: str) -> ClaimResult:
    find, found_means, clean_means = _SCANNERS[scanner]
    scan = collect_added_lines(cwd, config.diff_base, config.timeout)
    if scan.error:
        return ClaimResult(
            claim,
            Verdict.UNVERIFIABLE,
            Evidence(method="scanned git diff", detail=scan.error),
        )
    if not scan.saw_changes:
        return ClaimResult(
            claim,
            Verdict.UNVERIFIABLE,
            Evidence(
                method="scanned git diff",
                detail="working tree clean (changes may already be committed) — "
                "run before committing, or pass --diff-base",
            ),
        )
    findings = find(scan)
    if findings:
        return ClaimResult(
            claim,
            Verdict.FALSE,
            Evidence(
                method="scanned added lines",
                detail=f"found {found_means}: {findings[0]}",
                output="\n".join(findings),
            ),
        )
    return ClaimResult(
        claim,
        Verdict.TRUE,
        Evidence(method="scanned added lines", detail=clean_means),
    )


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
    if claim.type in _SCANNER_FOR_CLAIM:
        return _verify_scanner_claim(claim, _SCANNER_FOR_CLAIM[claim.type], config, cwd)
    # NO_ERRORS and UNKNOWN are too vague to check without guessing.
    return ClaimResult(
        claim,
        Verdict.UNVERIFIABLE,
        Evidence(method="no precise check", detail="claim is too vague to verify without guessing"),
    )


def run_checks(config: Config, cwd: str) -> list[CheckResult]:
    """Run every configured command and built-in scanner, reporting each outcome."""
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
    results.extend(_run_scanner_checks(config, cwd))
    return results


def _run_scanner_checks(config: Config, cwd: str) -> list[CheckResult]:
    enabled = [name for name in _SCANNERS if config.checks.get(name)]
    if not enabled:
        return []
    scan: DiffScan = collect_added_lines(cwd, config.diff_base, config.timeout)
    if scan.error:
        # Can't diff here (e.g. not a git repo) — same treatment as an
        # unconfigured command slot: skip rather than invent a verdict.
        return []
    results: list[CheckResult] = []
    for name in enabled:
        find, found_means, clean_means = _SCANNERS[name]
        if not scan.saw_changes:
            evidence = Evidence(method="scanned git diff", detail="working tree clean — nothing new to scan")
            results.append(CheckResult(name=name, ok=True, required=name in config.required, evidence=evidence))
            continue
        findings = find(scan)
        ok = not findings
        evidence = Evidence(
            method="scanned added lines",
            detail=clean_means if ok else f"found {found_means}: {findings[0]}",
            output="" if ok else "\n".join(findings),
        )
        results.append(CheckResult(name=name, ok=ok, required=name in config.required, evidence=evidence))
    return results
