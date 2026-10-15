"""Запуск рабочей среды разрешён только после всех проверок тех же image ID."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts import verify


def test_pin_services_removes_build_and_disables_pull() -> None:
    config = {"services": {"app": {"build": {"context": "."}, "image": "old:local"}}}
    verify.pin_services(config, {"app": "sha256:abc"})
    assert config["services"]["app"] == {"image": "sha256:abc", "pull_policy": "never"}


@pytest.mark.parametrize("severity", ["LOW", "MEDIUM", "HIGH", "CRITICAL"])
def test_any_secret_blocks_deployment(severity: str) -> None:
    with pytest.raises(RuntimeError, match="секреты"):
        verify.validate_scan(
            {"SchemaVersion": 2, "Results": [{"Secrets": [{"Severity": severity}]}]}
        )


@pytest.mark.parametrize("severity", ["HIGH", "CRITICAL"])
def test_high_vulnerability_blocks_deployment(severity: str) -> None:
    with pytest.raises(RuntimeError, match="уязвимость"):
        verify.validate_scan(
            {"SchemaVersion": 2, "Results": [{"Vulnerabilities": [{"Severity": severity}]}]}
        )


def test_scan_requires_valid_report_and_allows_low_vulnerability() -> None:
    with pytest.raises(RuntimeError):
        verify.validate_scan({})
    verify.validate_scan(
        {"SchemaVersion": 2, "Results": [{"Vulnerabilities": [{"Severity": "LOW"}]}]}
    )


def test_test_environment_excludes_working_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("ENV_FILE", "POSTGRES_PASSWORD", "DATABASE_URL", "TEST_DATABASE_URL"):
        monkeypatch.setenv(name, "private-value")
    monkeypatch.setattr(verify.policy, "identity", lambda: ("1000", "1000"))
    env = verify.test_environment()
    assert not {"ENV_FILE", "POSTGRES_PASSWORD", "DATABASE_URL", "TEST_DATABASE_URL"} & env.keys()


@pytest.mark.parametrize("failure", ["checks", "policy", "scans", "changed", None])
def test_deploy_is_gated_by_all_checks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failure: str | None
) -> None:
    (tmp_path / "reports").mkdir()
    monkeypatch.setattr(verify, "ROOT", tmp_path)
    monkeypatch.setattr(verify.policy, "prepare", lambda: None)
    monkeypatch.setattr(verify.policy, "validate_sources", lambda root: None)
    monkeypatch.setattr(verify.policy, "COMPOSE_FILES", ())
    monkeypatch.setattr(verify.policy, "EXPECTED_SERVICES", ())
    monkeypatch.setattr(verify, "test_environment", dict)
    fingerprints = iter(["before", "changed" if failure == "changed" else "before"])
    monkeypatch.setattr(verify, "source_digest", lambda: next(fingerprints))
    images = {"app": "sha256:abc", "tests": "sha256:def"}
    build = MagicMock(return_value=images)
    monkeypatch.setattr(verify, "build_images", build)
    for name in ("checks", "scans"):
        monkeypatch.setattr(
            verify, name, MagicMock(side_effect=RuntimeError(name) if failure == name else None)
        )
    monkeypatch.setattr(
        verify.policy,
        "main",
        MagicMock(side_effect=RuntimeError("policy") if failure == "policy" else None),
    )
    monkeypatch.setattr(verify.policy, "run", MagicMock(return_value="base"))
    monkeypatch.setattr(verify, "execute", MagicMock())
    deploy = MagicMock()
    monkeypatch.setattr(verify, "deploy", deploy)
    if failure:
        with pytest.raises(RuntimeError):
            verify.main()
        deploy.assert_not_called()
    else:
        verify.main()
        assert deploy.call_args.args[1] is images
        assert json.loads((tmp_path / "reports/verify.json").read_text())["status"] == "passed"
    build.assert_called_once()


def test_deploy_uses_external_path_as_single_argument(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env_file = tmp_path / "private settings.env"
    env_file.write_text("POSTGRES_PASSWORD=private-value")
    monkeypatch.setenv("ENV_FILE", str(env_file))
    command = MagicMock()
    monkeypatch.setattr(verify.policy, "run", command)
    verify.deploy(tmp_path, {"app": "sha256:abc", "tests": "sha256:def"})
    args = command.call_args.args
    assert args[args.index("--env-file") + 1] == str(env_file)
    assert "--no-build" in args and "never" in args
    manifest = (tmp_path / "deploy.json").read_text()
    assert "private" not in manifest and "tests" not in manifest


def test_check_failure_cleans_only_unique_project(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = MagicMock(return_value={"services": {"db": {}, "tests": {}}})
    monkeypatch.setattr(verify.policy, "compose_config", config)
    execute = MagicMock(side_effect=[RuntimeError("test failed"), None])
    monkeypatch.setattr(verify, "execute", execute)
    with pytest.raises(RuntimeError, match="test failed"):
        verify.checks(tmp_path, {"db": "sha256:db", "tests": "sha256:tests"}, {})
    project = config.call_args.args[1]["COMPOSE_PROJECT_NAME"]
    assert project.startswith("inventory-verify-")
    invocation = execute.call_args_list[0].args[0]
    assert "run" in invocation
    assert "--no-build" not in invocation
    assert "--build" not in invocation
    manifest = json.loads((tmp_path / "tests.json").read_text())
    for name, image in {"db": "sha256:db", "tests": "sha256:tests"}.items():
        assert manifest["services"][name]["image"] == image
        assert manifest["services"][name]["pull_policy"] == "never"
        assert "build" not in manifest["services"][name]
    cleanup = execute.call_args.args[0]
    assert cleanup[cleanup.index("-p") + 1] == project
    assert cleanup[-3:] == ["down", "--volumes", "--remove-orphans"]
