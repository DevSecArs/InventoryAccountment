"""Статическая проверка безопасности контейнеров проекта."""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
errors = []


def check(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


dockerfile = (ROOT / "Dockerfile").read_text()
dockerignore = (ROOT / ".dockerignore").read_text().splitlines()

# Проверяем итоговую конфигурацию Compose, а не только исходный YAML.
result = subprocess.run(
    ["docker", "compose", "config", "--format", "json"],
    cwd=ROOT,
    capture_output=True,
    text=True,
    check=False,
)
if result.returncode:
    sys.exit(f"Ошибка Docker Compose: {result.stderr.strip()}")

services = json.loads(result.stdout)["services"]

# Запрет latest и обязательный запуск без root.
for instruction in re.finditer(r"(?im)^\s*FROM\s+(\S+)", dockerfile):
    image = instruction.group(1)
    check(not image.lower().endswith(":latest"), f"Запрещён latest: {image}")

for name, service in services.items():
    image = service.get("image", "")
    check(not image.lower().endswith(":latest"), f"{name}: запрещён latest")
    check(
        service.get("user") not in ("root", "0", "0:0"),
        f"{name}: запуск от root запрещён",
    )
    if name == "db":
        check(service.get("user") == "postgres", "db: требуется user: postgres")

    # Healthcheck нельзя отключать или удалять.
    healthcheck = service.get("healthcheck") or {}
    test = healthcheck.get("test")
    check(bool(test) and test != ["NONE"] and not healthcheck.get("disable", False), f"{name}: отсутствует или отключён healthcheck")

    # Только frontend разрешено публиковать порт 5173.
    ports = service.get("ports") or []
    if name == "frontend":
        check(
            len(ports) == 1
            and str(ports[0].get("published")) == "5173"
            and ports[0].get("target") == 5173,
            "frontend: разрешён только порт 5173:5173",
        )
    else:
        check(not ports, f"{name}: публикация портов запрещена")

# Проверяем пользователей в конечных стадиях Dockerfile.
for stage, user in (("backend", "app"), ("frontend", "node")):
    pattern = rf"(?ims)^FROM\s+\S+\s+AS\s+{stage}\s*$([\s\S]*?)(?=^FROM\s|\Z)"
    match = re.search(pattern, dockerfile)
    users = re.findall(r"(?im)^USER\s+(\S+)", match.group(1)) if match else []
    check(
        bool(users) and users[-1] == user,
        f"{stage}: последняя инструкция USER должна быть {user}",
    )

# Секреты нельзя помещать в образ.
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

if errors:
    for error in errors:
        print(f"ОШИБКА: {error}", file=sys.stderr)
    sys.exit(1)

print("Проверка безопасности контейнеров пройдена.")
