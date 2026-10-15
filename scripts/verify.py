"""Однократная сборка, проверки неизменяемых образов и запуск рабочей среды."""

from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import tarfile
import tempfile
import uuid
from pathlib import Path
from typing import Any

from scripts import build_test_image as context
from scripts import container_check as policy

ROOT = policy.ROOT


def execute(args: list[str], env: dict[str, str] | None = None) -> None:
    subprocess.run(args, cwd=ROOT, env=env, check=True)


def test_environment() -> dict[str, str]:
    env = os.environ.copy()
    for key in list(env):
        if key.startswith(("COMPOSE_", "POSTGRES_")) or key in {
            "ENV_FILE",
            "DATABASE_URL",
            "TEST_DATABASE_URL",
        }:
            del env[key]
    uid, gid = policy.identity()
    env.update(LOCAL_UID=uid, LOCAL_GID=gid)
    return env


def source_digest() -> str:
    digest = hashlib.sha256()
    files = policy.run("git", "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    for name in sorted(files.split("\0")):
        path = ROOT / name
        if name and path.is_file():
            digest.update(name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def build_images(directory: Path, env: dict[str, str]) -> dict[str, str]:
    images: dict[str, str] = {}
    # Один снимок исходников, без node_modules, локальных env и секретов.
    with tempfile.TemporaryFile() as stream:
        with tarfile.open(fileobj=stream, mode="w:gz") as archive:
            for name in (*context.FILES, "Dockerfile", *context.DIRECTORIES):
                context.add_source(archive, ROOT / name)
        for name, dockerfile, target in (
            ("tests", "Dockerfile.tests", None),
            ("app", "Dockerfile", "runtime"),
            ("frontend", "Dockerfile", "frontend"),
        ):
            print("==> Однократная сборка: " + name, flush=True)
            stream.seek(0)
            iid = directory / (name + ".iid")
            command = [
                "docker",
                "build",
                "--iidfile",
                str(iid),
                "-f",
                dockerfile,
                "--build-arg",
                "LOCAL_UID=" + env["LOCAL_UID"],
                "--build-arg",
                "LOCAL_GID=" + env["LOCAL_GID"],
            ]
            if target:
                command += ["--target", target]
            subprocess.run(command + ["-"], stdin=stream, cwd=ROOT, env=env, check=True)
            images[name] = iid.read_text().strip()
    db = policy.compose_config("compose.test-runner.yaml", env)["services"]["db"]["image"]
    execute(["docker", "pull", db], env)
    images["db"] = policy.run("docker", "image", "inspect", "--format", "{{.Id}}", db)
    images["pg-tools"] = images["db"]
    images["migrate"] = images["app"]
    return images


def pin_services(config: dict[str, Any], images: dict[str, str]) -> None:
    for name, service in config["services"].items():
        service["image"] = images[name]
        service.pop("build", None)
        service["pull_policy"] = "never"


def checks(directory: Path, images: dict[str, str], env: dict[str, str]) -> None:
    project = "inventory-verify-" + uuid.uuid4().hex[:12]
    env = {**env, "COMPOSE_PROJECT_NAME": project}
    config = policy.compose_config("compose.test-runner.yaml", env)
    pin_services(config, images)
    config["services"]["tests"]["volumes"] = [
        {"type": "bind", "source": str(ROOT / "reports"), "target": "/app/reports"}
    ]
    filename = directory / "tests.json"
    filename.write_text(json.dumps(config), encoding="utf-8")
    command = [
        "docker",
        "compose",
        "--env-file",
        "compose.test.env",
        "-p",
        project,
        "-f",
        str(filename),
    ]
    try:
        execute(
            command
            + [
                "run",
                "--rm",
                "-e",
                "CI=true",
                "tests",
                "sh",
                "scripts/verify_checks.sh",
            ],
            env,
        )
    finally:
        execute(command + ["down", "--volumes", "--remove-orphans"], env)
    policy.require(
        not policy.run(
            "docker", "ps", "-aq", "--filter", "label=com.docker.compose.project=" + project
        ),
        "Остались тестовые контейнеры",
    )
    policy.require(
        not policy.run(
            "docker",
            "volume",
            "ls",
            "-q",
            "--filter",
            "label=com.docker.compose.project=" + project,
        ),
        "Остались тестовые тома",
    )


def validate_scan(report: dict[str, Any]) -> None:
    policy.require(report.get("SchemaVersion") == 2, "Некорректный отчёт Trivy")
    for result in report.get("Results") or []:
        policy.require(not result.get("Secrets"), "Trivy обнаружил секреты в образе")
        for vulnerability in result.get("Vulnerabilities") or []:
            policy.require(
                vulnerability.get("Severity") not in {"HIGH", "CRITICAL"},
                "Trivy обнаружил уязвимость High/Critical в образе",
            )


def scans(directory: Path, images: dict[str, str], env: dict[str, str]) -> None:
    runner = [
        "docker",
        "run",
        "--rm",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges:true",
        "--cpus=2",
        "--memory=2g",
        "--pids-limit=256",
        "-e",
        "TRIVY_CACHE_DIR=/cache",
        "-v",
        f"{directory}:/scan:ro",
        "-v",
        f"{directory / 'cache'}:/cache",
        "-v",
        f"{ROOT / 'reports'}:/reports",
    ]
    (directory / "cache").mkdir()
    execute(
        runner
        + [
            "-v",
            f"{ROOT}:/repo:ro",
            images["tests"],
            "gitleaks",
            "detect",
            "--source=/repo",
            "--report-format=json",
            "--redact",
            "--report-path=/reports/gitleaks.json",
            "--exit-code=1",
        ],
        env,
    )
    for index, image in enumerate(sorted(set(images.values()))):
        print("==> Уязвимости и секреты image ID: " + image, flush=True)
        archive = directory / "image.tar"
        execute(["docker", "save", "-o", str(archive), image], env)
        # Один export и один проход Trivy на уникальный ID, общий кэш базы.
        execute(
            runner
            + [
                images["tests"],
                "trivy",
                "image",
                "--input",
                "/scan/image.tar",
                "--scanners",
                "vuln,secret",
                "--ignore-unfixed",
                "--exit-code",
                "0",
                "--format",
                "json",
                "--output",
                f"/reports/trivy-{index}.json",
            ],
            env,
        )
        # Любой секрет блокирует запуск, независимо от его severity.
        # Порог уязвимостей остаётся High/Critical, как у прежнего image-scan.
        validate_scan(json.loads((ROOT / f"reports/trivy-{index}.json").read_text()))
        archive.unlink()


def deploy(directory: Path, images: dict[str, str]) -> None:
    project = os.environ.get("PROJECT_NAME", "inventory-compose")
    command = ["docker", "compose"]
    env_file = os.environ.get("ENV_FILE")
    if env_file:
        policy.require(Path(env_file).is_file(), "ENV_FILE должен быть доступным файлом")
        command += ["--env-file", env_file]
    command += ["-p", project, "-f", "docker-compose.yaml"]
    # Сохраняем лишь image ID; рабочие секреты не пишутся в JSON или логи.
    override = directory / "deploy.json"
    override.write_text(
        json.dumps(
            {
                "services": {
                    name: {"image": image, "pull_policy": "never"}
                    for name, image in images.items()
                    if name != "tests"
                }
            }
        ),
        encoding="utf-8",
    )
    policy.run(
        *command,
        "-f",
        str(override),
        "up",
        "--no-build",
        "--pull",
        "never",
        "-d",
        "--wait",
        "--wait-timeout",
        "120",
    )


def main() -> None:
    policy.prepare()
    env = test_environment()
    fingerprint = source_digest()
    policy.validate_sources(ROOT)
    for filename, expected in zip(policy.COMPOSE_FILES, policy.EXPECTED_SERVICES, strict=True):
        config = policy.compose_config(filename, env)
        policy.validate_compose(config)
        policy.require(set(config["services"]) == expected, "Потерян сервис Compose")
    report = ROOT / "reports/verify.json"
    report.write_text(json.dumps({"status": "running"}), encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="verify-", dir=ROOT / "reports") as temporary:
        directory = Path(temporary)
        images = build_images(directory, env)
        report.write_text(json.dumps({"status": "checking", "images": images}), encoding="utf-8")
        checks(directory, images, env)
        policy.main(images)
        scans(directory, images, env)
        execute(["git", "diff", "--check"])
        base = policy.run("git", "merge-base", "HEAD", os.environ.get("BASE_REF", "main"))
        execute(["git", "diff", "--check", base + "...HEAD"])
        policy.require(fingerprint == source_digest(), "Исходники изменились во время verify")
        print("==> Все проверки пройдены; запускаю проверенные рабочие образы", flush=True)
        deploy(directory, images)
        report.write_text(json.dumps({"status": "passed", "images": images}), encoding="utf-8")


if __name__ == "__main__":

    def interrupted(signum: int, frame: Any) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    try:
        main()
    except (RuntimeError, OSError, subprocess.CalledProcessError, KeyboardInterrupt) as error:
        report = ROOT / "reports/verify.json"
        if report.is_file():
            state = json.loads(report.read_text(encoding="utf-8"))
            state["status"] = "interrupted" if isinstance(error, KeyboardInterrupt) else "failed"
            report.write_text(json.dumps(state), encoding="utf-8")
        print("verify остановлен: " + str(error), flush=True)
        raise SystemExit(1) from error
