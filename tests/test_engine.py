"""End-to-end tests: transcript in, verdict out."""

import sys

from veridict.config import Config
from veridict.engine import run_project, verify_transcript

PY = f'"{sys.executable}"'
FAIL = f'{PY} -c "import sys; sys.exit(1)"'
OK = f'{PY} -c "import sys; sys.exit(0)"'


def test_catches_the_lie(tmp_path):
    (tmp_path / "app.py").write_text("print('hi')")
    transcript = "I created `app.py` and all tests pass."
    cfg = Config(commands={"tests": FAIL})

    report = verify_transcript(transcript, cfg, str(tmp_path))

    assert len(report.lies) == 1  # tests claim contradicted
    assert len(report.verified) == 1  # the file really does exist
    assert report.trust_score == 50
    assert report.exit_code == 1


def test_all_claims_hold_up(tmp_path):
    (tmp_path / "app.py").write_text("x = 1")
    transcript = "Created app.py; tests pass."
    cfg = Config(commands={"tests": OK})

    report = verify_transcript(transcript, cfg, str(tmp_path))

    assert report.lies == []
    assert report.trust_score == 100
    assert report.exit_code == 0


def test_run_project_with_no_config_scores_nothing(tmp_path):
    report = run_project(Config(), str(tmp_path))
    assert report.check_results == []
    assert report.trust_score is None
    assert report.exit_code == 0
