"""Tests for configuration loading, focused on the no_secrets gate."""

from veridict.config import load_config


def test_autodetect_gates_no_secrets(tmp_path):
    config, source = load_config(tmp_path)
    assert source is None
    assert config.checks["no_secrets"] is True
    assert "no_secrets" in config.required


def test_yaml_config_gates_no_secrets_even_when_not_listed(tmp_path):
    (tmp_path / ".veridict.yaml").write_text(
        "commands:\n  tests: 'true'\nrequired:\n  - tests\n", encoding="utf-8"
    )
    config, _ = load_config(tmp_path)
    assert config.required == ["tests", "no_secrets"]


def test_disabling_no_secrets_removes_the_gate(tmp_path):
    (tmp_path / ".veridict.yaml").write_text(
        "checks:\n  no_secrets: false\n", encoding="utf-8"
    )
    config, _ = load_config(tmp_path)
    assert config.checks["no_secrets"] is False
    assert "no_secrets" not in config.required


def test_no_secrets_not_double_listed(tmp_path):
    (tmp_path / ".veridict.yaml").write_text(
        "checks:\n  no_secrets: true\nrequired:\n  - no_secrets\n", encoding="utf-8"
    )
    config, _ = load_config(tmp_path)
    assert config.required.count("no_secrets") == 1
