"""Ограниченная статическая проверка конфигурации контейнеров проекта."""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_SERVICES = {"nginx", "backend", "frontend", "db"}


def _positive_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def _root_user(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    parts = str(value).split(":", maxsplit=1)
    return parts[0].strip().lower() in {"root", "0", "00", "+0"}


def _uid_gid(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+:[0-9]+", value):
        return None
    uid, gid = (int(part) for part in value.split(":"))
    return uid, gid


def _is_command(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    return isinstance(value, list) and bool(value) and all(
        isinstance(part, (str, int, float)) and str(part).strip() for part in value
    )


def load_compose(root: Path = ROOT) -> dict[str, Any]:
    """Загрузить нормализованную конфигурацию Compose, не раскрывая её вывод."""
    try:
        result = subprocess.run(
            ["docker", "compose", "config", "--format", "json"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except (FileNotFoundError, OSError) as exc:
        raise ValueError("Не удалось запустить Docker Compose CLI") from exc
    if result.returncode:
        raise ValueError("Docker Compose config завершился с ошибкой")
    try:
        config = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("Docker Compose вернул некорректный JSON") from exc
    if not isinstance(config, dict) or not isinstance(config.get("services"), dict):
        raise ValueError("В конфигурации Compose отсутствует объект services")
    return config


def validate(config: dict[str, Any], root: Path = ROOT) -> list[str]:
    """Собрать независимые нарушения конфигурации и статические правил проекта."""
    errors: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    try:
        dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
        dockerignore = (root / ".dockerignore").read_text(encoding="utf-8").splitlines()
        nginx_path = root / "nginx" / "default.conf"
        if not nginx_path.is_file():
            errors.append("Nginx: отсутствует nginx/default.conf")
    except (OSError, UnicodeError) as exc:
        return [f"Не удалось прочитать необходимые файлы проекта ({type(exc).__name__})"]

    services = config["services"]
    missing = REQUIRED_SERVICES - services.keys()
    for name in sorted(missing):
        errors.append(f"Compose: отсутствует обязательный сервис {name}")

    for instruction in re.finditer(r"(?im)^\s*FROM\s+(\S+)", dockerfile):
        image = instruction.group(1)
        check(not image.lower().endswith(":latest"), f"Dockerfile: запрещён latest ({image})")

    for name, service in services.items():
        if not isinstance(service, dict):
            errors.append(f"{name}: описание сервиса должно быть объектом")
            continue
        image = service.get("image")
        if isinstance(image, str):
            check(not image.lower().endswith(":latest"), f"{name}: запрещён latest")
        user = service.get("user")
        check(not _root_user(user), f"{name}: переопределение запуска от root запрещено")
        if name == "db":
            check(user == "postgres", "db: требуется user: postgres")
        elif name in {"backend", "frontend"}:
            expected_user = "app" if name == "backend" else "node"
            check(
                user is None or not _root_user(user),
                f"{name}: Compose не должен переопределять конечного пользователя {expected_user}",
            )
        elif name == "nginx":
            check(
                image == "nginxinc/nginx-unprivileged:alpine",
                "nginx: требуется образ nginxinc/nginx-unprivileged:alpine",
            )
            identity = _uid_gid(user)
            check(
                identity is not None and identity[0] > 0 and identity[1] > 0,
                "nginx: требуется явный ненулевой числовой UID:GID",
            )

        check(service.get("network_mode") != "host", f"{name}: запрещён network_mode: host")

        healthcheck = service.get("healthcheck")
        health_valid = isinstance(healthcheck, dict) and not healthcheck.get("disable", False)
        test = healthcheck.get("test") if health_valid else None
        health_valid = health_valid and _is_command(test) and not (
            isinstance(test, list) and test and str(test[0]).upper() == "NONE"
        )
        check(bool(health_valid), f"{name}: отсутствует, пустой или отключён healthcheck")

        for resource in ("cpus", "mem_limit", "pids_limit"):
            check(
                _positive_number(service.get(resource)),
                f"{name}: требуется положительный конечный {resource}",
            )

        ports = service.get("ports", [])
        if not isinstance(ports, list):
            errors.append(f"{name}: ports должен быть списком")
            ports = []
        if name != "nginx":
            check(not ports, f"{name}: публикация портов запрещена")

    nginx = services.get("nginx")
    if isinstance(nginx, dict):
        ports = nginx.get("ports", [])
        valid_port = (
            isinstance(ports, list)
            and len(ports) == 1
            and isinstance(ports[0], dict)
            and str(ports[0].get("published")) == "8080"
            and ports[0].get("target") == 8080
            and str(ports[0].get("protocol", "tcp")).lower() == "tcp"
            and ports[0].get("mode", "ingress") == "ingress"
            and ports[0].get("host_ip") in (None, "", "0.0.0.0", "::")
        )
        check(valid_port, "nginx: разрешено только внешнее TCP-сопоставление 8080:8080")
        replicas = services.get("backend", {}).get("deploy", {}).get("replicas") if isinstance(services.get("backend"), dict) else None
        check(
            isinstance(replicas, int) and not isinstance(replicas, bool) and replicas >= 2,
            "backend: требуется deploy.replicas не менее 2",
        )
        if isinstance(services.get("backend"), dict):
            check("container_name" not in services["backend"], "backend: container_name мешает масштабированию")

        volumes = nginx.get("volumes", [])
        valid_mount = False
        if isinstance(volumes, list):
            for volume in volumes:
                if not isinstance(volume, dict):
                    continue
                source = Path(str(volume.get("source", "")))
                try:
                    source_matches = source.resolve() == (root / "nginx" / "default.conf").resolve()
                except OSError:
                    source_matches = False
                if (
                    source_matches
                    and volume.get("target") == "/etc/nginx/conf.d/default.conf"
                    and volume.get("read_only") is True
                ):
                    valid_mount = True
        check(valid_mount, "nginx: nginx/default.conf должен быть подключён read-only")

    for stage, user in (("backend", "app"), ("frontend", "node")):
        pattern = rf"(?ims)^FROM\s+\S+\s+AS\s+{stage}\s*$([\s\S]*?)(?=^FROM\s|\Z)"
        match = re.search(pattern, dockerfile)
        users = re.findall(r"(?im)^USER\s+(\S+)", match.group(1)) if match else []
        check(bool(users) and users[-1] == user, f"{stage}: конечная инструкция USER должна быть {user}")

    check(
        not re.search(r"(?im)^\s*(?:ARG|ENV)\s+\S*(?:PASSWORD|SECRET|TOKEN|API_KEY)\b", dockerfile),
        "Dockerfile: запрещено задавать секреты через ARG/ENV",
    )
    check(
        not re.search(r"(?im)^\s*(?:ADD|COPY)\s+.*(?:\.env|secrets/|\.pem|\.key)\b", dockerfile),
        "Dockerfile: запрещено копировать файлы с секретами",
    )
    for rule in ("**", "**/.env", "**/.env.*", "**/secrets", "**/*.key", "**/*.pem"):
        check(rule in dockerignore, f".dockerignore: отсутствует правило {rule}")
    return errors


def main(root: Path = ROOT) -> int:
    try:
        config = load_compose(root)
    except ValueError as exc:
        print(f"Ошибка подготовки статической проверки: {exc}", file=sys.stderr)
        return 1
    errors = validate(config, root)
    if errors:
        for error in errors:
            print(f"ОШИБКА: {error}", file=sys.stderr)
        print(f"Статическая проверка: найдено нарушений — {len(errors)}.", file=sys.stderr)
        return 1
    print("Статическая проверка конфигурации контейнеров пройдена.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
