"""Tests for claim extraction from agent transcripts."""

from veridict.claims import extract_claims
from veridict.models import ClaimType


def _types(text):
    return {c.type for c in extract_claims(text)}


def test_detects_tests_pass():
    assert ClaimType.TESTS_PASS in _types("Great news — all tests pass now.")
    assert ClaimType.TESTS_PASS in _types("The test suite is green.")
    assert ClaimType.TESTS_PASS in _types("✅ tests passing")


def test_detects_build_lint_typecheck():
    assert ClaimType.BUILD_PASSES in _types("The build succeeds.")
    assert ClaimType.BUILD_PASSES in _types("Project compiles cleanly.")
    assert ClaimType.LINT_PASSES in _types("ruff is clean, no warnings.")
    assert ClaimType.TYPECHECK_PASSES in _types("mypy passes with no errors.")


def test_detects_created_file_with_path_and_backticks():
    claims = extract_claims("I created `src/auth.py` with the login handler.")
    targets = [c.target for c in claims if c.type is ClaimType.FILE_EXISTS]
    assert "src/auth.py" in targets


def test_modified_file_detected():
    claims = extract_claims("Updated config/settings.py to add the new flag.")
    targets = [c.target for c in claims if c.type is ClaimType.FILE_MODIFIED]
    assert "config/settings.py" in targets


def test_created_file_not_double_counted_as_modified():
    text = "Created foo.py first. Then I updated foo.py again."
    keys = {(c.type, c.target) for c in extract_claims(text)}
    assert (ClaimType.FILE_EXISTS, "foo.py") in keys
    assert (ClaimType.FILE_MODIFIED, "foo.py") not in keys


def test_method_calls_are_not_files():
    # Found by the benchmark: an agent describing a code edit must not have
    # `x.split` extracted as a filename claim.
    text = "Changed `x.split('=')[0]` and `x.split('=')[1]` to a single `pair.split('=', 1)` call."
    file_claims = [c for c in extract_claims(text) if c.type in (ClaimType.FILE_EXISTS, ClaimType.FILE_MODIFIED)]
    assert file_claims == []


def test_version_strings_are_not_files():
    # Numeric "extensions" must not be mistaken for filenames.
    claims = extract_claims("Updated the dependency to 3.12.1 and bumped to v0.2 today.")
    file_claims = [c for c in claims if c.type in (ClaimType.FILE_EXISTS, ClaimType.FILE_MODIFIED)]
    assert file_claims == []


def test_detects_no_new_todos():
    assert ClaimType.NO_NEW_TODOS in _types("There are no TODOs left in the code.")
    assert ClaimType.NO_NEW_TODOS in _types("Removed all the TODOs.")
    assert ClaimType.NO_NEW_TODOS in _types("Resolved all remaining FIXMEs.")


def test_detects_no_secrets():
    assert ClaimType.NO_SECRETS in _types("No secrets were committed.")
    assert ClaimType.NO_SECRETS in _types("There are no hardcoded credentials.")
    assert ClaimType.NO_SECRETS in _types("I didn't include any API keys in the code.")


def test_plain_prose_has_no_scanner_claims():
    text = "I refactored the parser and tightened the validation logic."
    assert ClaimType.NO_NEW_TODOS not in _types(text)
    assert ClaimType.NO_SECRETS not in _types(text)


def test_simple_claims_are_deduplicated():
    text = "tests pass\nall tests are passing\nthe tests are green"
    n = sum(1 for c in extract_claims(text) if c.type is ClaimType.TESTS_PASS)
    assert n == 1


def test_line_numbers_recorded():
    claims = extract_claims("intro line\nall tests pass")
    test_claim = next(c for c in claims if c.type is ClaimType.TESTS_PASS)
    assert test_claim.line == 2
