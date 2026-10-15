"""Проверка политики и реального запуска контейнеров в одноразовом проекте."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILES = ("docker-compose.yaml", "compose.test.yaml", "compose.test-runner.yaml")
EXPECTED_SERVICES = (
    {"db", "app", "frontend", "migrate", "pg-tools"},
    {"db", "app", "frontend", "pg-tools"},
    {"db", "tests"},
)
DAEMONS = {"db", "app", "frontend"}
JOBS = {"migrate", "pg-tools", "tests"}
PORTS = {"app": 8000, "frontend": 5173}
SECRET_NAME = re.compile(
    r"password|passwd|secret|token|(?:private|api|access).?key|credentials|database.?url",
    re.IGNORECASE,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def nonroot(user: str) -> bool:
    uid = user.split(":")[0]
    return bool(uid) and uid.lower() != "root" and not (uid.isdigit() and int(uid) == 0)


def pinned(image: str) -> bool:
    reference = image.split("@", 1)[0]
    tag = reference.rsplit("/", 1)[-1].partition(":")[2]
    if tag.lower() == "latest":
        return False
    return bool(tag) or bool(re.search(r"@sha256:[0-9a-f]{64}$", image))


def validate_compose(config: dict[str, Any]) -> None:
    services = config.get("services", {})
    require(bool(services), "В Compose нет сервисов")
    for name, service in services.items():
        prefix = f"Сервис {name}: "
        require(name in DAEMONS | JOBS, prefix + "не определена роль в политике")
        require(pinned(service.get("image", "")), prefix + "нужен явный тег, кроме latest")
        require(nonroot(str(service.get("user", ""))), prefix + "нужен явный non-root user")
        require(not service.get("privileged"), prefix + "privileged запрещён")
        require(not service.get("network_mode"), prefix + "network_mode запрещён")
        require(not service.get("cap_add"), prefix + "добавление capabilities запрещено")
        health = service.get("healthcheck", {})
        require(not health.get("disable"), prefix + "healthcheck отключён")
        require(health.get("test", [""])[0] != "NONE", prefix + "HEALTHCHECK NONE запрещён")
        if name in DAEMONS:
            require(bool(health.get("test")), prefix + "нет healthcheck")
        ports = service.get("ports", [])
        require(len(ports) <= (1 if name in PORTS else 0), prefix + "лишние порты")
        for port in ports:
            require(
                port.get("host_ip") == "127.0.0.1"
                and int(port["target"]) == PORTS[name]
                and port.get("protocol", "tcp") == "tcp",
                prefix + "порт вне разрешённого списка",
            )
        build = service.get("build", {})
        if isinstance(build, dict):
            require(
                not any(SECRET_NAME.search(key) for key in build.get("args", {})),
                prefix + "секретный build arg запрещён",
            )


def validate_sources(root: Path) -> None:
    for filename in ("Dockerfile", "Dockerfile.tests"):
        source = (root / filename).read_text(encoding="utf-8")
        stages: set[str] = set()
        for line in source.replace("\\\n", " ").splitlines():
            words = line.strip().split()
            if not words:
                continue
            instruction = words[0].upper()
            if instruction == "FROM":
                require(words[1] in stages or pinned(words[1]), filename + ": незакреплённый FROM")
                if len(words) > 3:
                    stages.add(words[3])
            if instruction in {"ARG", "ENV"}:
                require(not SECRET_NAME.search(line), filename + ": секрет в ARG/ENV")
            if instruction == "HEALTHCHECK":
                require(words[1].upper() != "NONE", filename + ": HEALTHCHECK NONE")
            if instruction in {"COPY", "ADD"}:
                require(instruction != "ADD", filename + ": используйте явный COPY")
                require(
                    not any(part in {".", "./"} for part in words[1:-1]),
                    filename + ": нельзя копировать весь build context",
                )
                require(
                    not any(SECRET_NAME.search(part) or ".env" in part for part in words[1:-1]),
                    filename + ": секретный источник COPY",
                )
    ignored = set((root / ".dockerignore").read_text(encoding="utf-8").splitlines())
    require(
        {"**/.env", "**/.env.*", "**/secrets", "**/*.key", "**/*.pem"} <= ignored,
        "В .dockerignore отсутствуют обязательные исключения секретов",
    )
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    require(not re.search(r"--user[ =]+(?:root|0)(?:\s|:|$)", makefile), "Make запускает root")


def identity() -> tuple[str, str]:
    uid = os.environ.get("LOCAL_UID", str(os.getuid()) if hasattr(os, "getuid") else "1000")
    gid = os.environ.get("LOCAL_GID", str(os.getgid()) if hasattr(os, "getgid") else "1000")
    require(uid.isdecimal() and int(uid) > 0, "LOCAL_UID должен быть положительным, не root")
    require(gid.isdecimal() and int(gid) > 0, "LOCAL_GID должен быть положительным")
    return uid, gid


def prepare() -> None:
    identity()
    for name in ("reports", "reports/unix-tests", "backups"):
        directory = ROOT / name
        directory.mkdir(parents=True, exist_ok=True)
        require(not directory.is_symlink(), f"{name}: символьная ссылка не разрешена")
        try:
            with tempfile.TemporaryFile(dir=directory):
                pass
        except OSError as error:
            raise RuntimeError(
                f"{name}: исправьте права на хосте; root-контейнер запрещён"
            ) from error


def run(*args: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    # Для изолированного up сохраняем диагностику сборки. Config не логируется.
    if len(args) > 1 and args[:2] == ("docker", "compose") and "up" in args:
        (ROOT / "reports/container-check-build.log").write_text(
            result.stdout + result.stderr, encoding="utf-8"
        )
    if "/scripts/backup_restore_check.sh" in args:
        (ROOT / "reports/container-check-backup.log").write_text(
            result.stdout + result.stderr, encoding="utf-8"
        )
    # Не печатаем argv/config/stderr: они могут содержать рабочие настройки.
    require(result.returncode == 0, f"Команда {args[0]} завершилась с кодом {result.returncode}")
    return result.stdout.strip()


def compose_config(filename: str, env: dict[str, str]) -> dict[str, Any]:
    return dict(
        json.loads(
            run(
                "docker",
                "compose",
                "--env-file",
                "compose.test.env",
                "--profile",
                "*",
                "-f",
                filename,
                "config",
                "--format",
                "json",
                env=env,
            )
        )
    )


def scan_image(directory: Path, image_id: str, uid: str, gid: str) -> None:
    archive = directory / "image.tar"
    run("docker", "save", "-o", str(archive), image_id)
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--user",
            f"{uid}:{gid}",
            "-v",
            f"{directory}:/scan:ro",
            "-e",
            "TRIVY_CACHE_DIR=/tmp/trivy",
            "aquasec/trivy:0.56.2",
            "image",
            "--input",
            "/scan/image.tar",
            "--scanners",
            "secret",
            "--format",
            "json",
            "--exit-code",
            "1",
            "--quiet",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    archive.unlink()
    require(result.returncode == 0, "Secret scan не прошёл для " + image_id)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--static-only", action="store_true")
    options = parser.parse_args()
    prepare()
    if options.prepare_only:
        return
    report = ROOT / "reports/container-check.json"
    report.write_text(json.dumps({"status": "running"}), encoding="utf-8")
    validate_sources(ROOT)
    uid, gid = identity()
    env = os.environ.copy()
    for key in list(env):
        if key.startswith(("COMPOSE_", "POSTGRES_")) or key in {"ENV_FILE", "DATABASE_URL"}:
            del env[key]
    project = "inventory-policy-" + uuid.uuid4().hex[:12]
    env.update(
        LOCAL_UID=uid,
        LOCAL_GID=gid,
        COMPOSE_PROJECT_NAME=project,
        POSTGRES_USER="inventory_test_app",
        POSTGRES_PASSWORD="inventory_test_password",
        POSTGRES_DB="inventory_test",
    )
    configs = {name: compose_config(name, env) for name in COMPOSE_FILES}
    for config, expected in zip(configs.values(), EXPECTED_SERVICES, strict=True):
        validate_compose(config)
        require(set(config["services"]) == expected, "Потерян сервис или профиль Compose")
    print("Политика Dockerfile и трёх Compose-конфигураций: OK", flush=True)
    if options.static_only:
        report.write_text(json.dumps({"status": "static-only"}), encoding="utf-8")
        return
    # Никаких рабочих env-файлов, контейнеров или томов. Пути разрешены Compose
    # относительно исходного файла до записи временного JSON.
    config = configs["docker-compose.yaml"]
    with tempfile.TemporaryDirectory(prefix="container-check-", dir=ROOT / "reports") as temp:
        directory = Path(temp)
        backup_dir = directory / "backups"
        backup_dir.mkdir()
        for name, service in config["services"].items():
            if name in PORTS:
                service["ports"][0]["published"] = "0"
            if name == "pg-tools":
                service["environment"]["APP_ENV"] = "test"
                service["volumes"][0]["source"] = str(backup_dir)
        config_path = directory / "compose.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        command = (
            "docker",
            "compose",
            "--env-file",
            "compose.test.env",
            "-p",
            project,
            "-f",
            str(config_path),
        )
        checked: list[dict[str, str]] = []
        try:
            print("Сборка и запуск изолированного проекта…", flush=True)
            run(*command, "up", "--build", "-d", "--wait", "--wait-timeout", "120", env=env)
            for name in sorted(DAEMONS):
                print("Проверка UID и healthcheck: " + name, flush=True)
                container = run(*command, "ps", "-q", name, env=env)
                state = json.loads(run("docker", "inspect", container))[0]
                require(state["State"]["Health"]["Status"] == "healthy", name + ": unhealthy")
                require(nonroot(state["Config"]["User"]), name + ": root в конфигурации")
                actual_uid = run(*command, "exec", "-T", name, "id", "-u", env=env)
                require(nonroot(actual_uid), name + ": фактический UID root")
                processes = run(
                    *command,
                    "exec",
                    "-T",
                    name,
                    "sh",
                    "-c",
                    "for p in /proc/[0-9]*/status; do "
                    "awk '/^Uid:/{if ($2 == 0 || $3 == 0) exit 1}' \"$p\" || exit 1; done",
                    env=env,
                )
                del processes
                checked.append({"service": name, "image_id": state["Image"], "uid": actual_uid})
                if name != "db":
                    image_user = run(
                        "docker", "image", "inspect", "--format", "{{.Config.User}}", state["Image"]
                    )
                    require(nonroot(image_user), name + ": root в проектном образе")
            print("Проверка backup/restore…", flush=True)
            run(
                *command,
                "run",
                "--rm",
                "pg-tools",
                "sh",
                "/scripts/backup_restore_check.sh",
                "/backups",
                env=env,
            )
            run(*command, "run", "--rm", "migrate", "sh", "-c", "test $(id -u) -ne 0", env=env)
            migration = run(*command, "ps", "--all", "-q", "migrate", env=env)
            migration_state = json.loads(run("docker", "inspect", migration))[0]
            require(migration_state["State"]["ExitCode"] == 0, "Миграции не завершились успешно")
            migration_user = run(
                "docker",
                "image",
                "inspect",
                "--format",
                "{{.Config.User}}",
                migration_state["Image"],
            )
            require(nonroot(migration_user), "Миграции: root в проектном образе")
            checked.append(
                {
                    "service": "migrate",
                    "image_id": migration_state["Image"],
                    "uid": migration_state["Config"]["User"],
                }
            )
            tools_uid = run(*command, "run", "--rm", "pg-tools", "id", "-u", env=env)
            require(nonroot(tools_uid), "pg-tools: root")
            sql = (
                "exec",
                "-T",
                "db",
                "psql",
                "-U",
                "inventory_test_app",
                "-d",
                "inventory_test",
                "-tAc",
                "SELECT version_num FROM alembic_version",
            )
            revision = run(*command, *sql, env=env)
            run(
                *command,
                "up",
                "-d",
                "--force-recreate",
                "--wait",
                "--wait-timeout",
                "120",
                "db",
                env=env,
            )
            require(
                bool(revision) and run(*command, *sql, env=env) == revision,
                "Схема БД потеряна после пересоздания контейнера",
            )
            for target in ("test", "frontend-test"):
                image = f"{project}-{target}:local"
                run(
                    "docker",
                    "build",
                    "--build-arg",
                    f"LOCAL_UID={uid}",
                    "--build-arg",
                    f"LOCAL_GID={gid}",
                    "--target",
                    target,
                    "-t",
                    image,
                    ".",
                )
                actual_uid = run("docker", "run", "--rm", image, "id", "-u")
                require(nonroot(actual_uid), target + ": root")
                writable = "/app/reports" if target == "test" else "/app/frontend"
                run("docker", "run", "--rm", image, "test", "-w", writable)
                checked.append(
                    {
                        "service": target,
                        "image_id": run("docker", "image", "inspect", "--format", "{{.Id}}", image),
                        "uid": actual_uid,
                    }
                )
            print("Проверка отдельного Linux test-образа…", flush=True)
            run(sys.executable, "scripts/build_test_image.py", env=env)
            test_uid = run("docker", "run", "--rm", "inventory-accountment-tests:local", "id", "-u")
            require(nonroot(test_uid), "Linux test-образ: root")
            checked.append(
                {
                    "service": "tests",
                    "image_id": run(
                        "docker",
                        "image",
                        "inspect",
                        "--format",
                        "{{.Id}}",
                        "inventory-accountment-tests:local",
                    ),
                    "uid": test_uid,
                }
            )
            # Secret scan собранного образа по image ID без доступа к Docker socket.
            scanned: set[str] = set()
            for item in checked:
                if item["image_id"] in scanned:
                    continue
                print("Проверка секретов образа: " + item["service"], flush=True)
                scan_image(directory, item["image_id"], uid, gid)
                scanned.add(item["image_id"])
            (ROOT / "reports/container-check.json").write_text(
                json.dumps({"status": "passed", "images": checked}, indent=2), encoding="utf-8"
            )
            print("Контейнеры, UID, healthcheck, backup/restore и secret scan: OK", flush=True)
        finally:
            run(*command, "down", "--volumes", "--remove-orphans", env=env)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError) as error:
        if not ("--prepare-only" in sys.argv):
            report = ROOT / "reports/container-check.json"
            if report.parent.is_dir():
                report.write_text(
                    json.dumps({"status": "failed", "error": str(error)}), encoding="utf-8"
                )
        raise SystemExit(str(error)) from error
