#!/bin/sh
set -eu

# Подготавливаем отдельный каталог отчётов и временное рабочее пространство.
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
run_id="$(date -u +%Y%m%dt%H%M%Sz)-$$"
report="$root/reports/$run_id/security"
mkdir -p "$report"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT HUP INT TERM
mkdir "$work/source"

# Проверяем полноту истории и создаём отдельную bare-копию без рабочего дерева.
status=0
if [ "$(git rev-parse --is-shallow-repository)" != false ]; then
  echo 'Ошибка: история Git неполная.' >&2
  status=1
fi
history_ok=1
if ! git clone --bare --no-local "$root" "$work/history.git" > "$report/history-clone.log" 2>&1; then
  echo 'Ошибка копирования истории Git.' >&2; status=1; history_ok=0
elif ! git --git-dir="$work/history.git" fsck --connectivity-only > "$report/history-fsck.log" 2>&1; then
  echo 'Ошибка целостности копии истории.' >&2; status=1
fi
# Фиксируем отслеживаемые env-файлы по именам, не читая их содержимое.
if git ls-files | grep -E '(^|/)\.env($|\.)' | grep -vE '(^|/)\.env\.example$' > "$report/tracked-env.txt"; then
  echo 'Ошибка: в Git отслеживается env-файл; проверьте список путей в отчёте.' >&2
  status=1
fi
# Копируем текущие исходники, исключая локальные конфигурации и рабочие данные.
git -c core.quotepath=false ls-files --cached --others --exclude-standard > "$work/files"
while IFS= read -r file; do
  case "$file" in '"'*) echo 'Ошибка: неподдерживаемое имя исходного файла.' >&2; exit 1;; esac
  case "/$file/" in
    */.env/|*/.env.*/)
      case "$file" in */.env.example|.env.example) ;; *) echo "Пропущен env-файл: $file" >&2; continue;; esac;;
    */credentials/*|*/secrets/*) echo "Ошибка: credentials в исходниках: $file" >&2; status=1; continue;;
    */node_modules/*|*/.venv/*|/reports/*|*/backups/*|*/dumps/*|*/volumes/*) continue;;
  esac
  [ -f "$file" ] || continue
  [ ! -L "$file" ] || { echo "Ошибка: символическая ссылка: $file" >&2; exit 1; }
  mkdir -p "$work/source/$(dirname "$file")"
  cp -p "$file" "$work/source/$file"
done < "$work/files"

# Проверяем историю и текущую копию исходников, скрывая значения находок в отчётах.
if [ "$history_ok" -eq 1 ]; then
  docker run --rm -v "$work/history.git:/repo:ro" -v "$report:/report" \
    zricethezav/gitleaks:v8.24.2 git /repo --log-opts=--all --redact=100 \
    --report-format json --report-path /report/gitleaks-history.json --no-banner || status=1
fi
docker run --rm -v "$work/source:/source:ro" -v "$report:/report" \
  zricethezav/gitleaks:v8.24.2 dir /source --redact=100 \
  --report-format json --report-path /report/gitleaks-source.json --no-banner || status=1

# Экспортируем зафиксированные backend-зависимости, включая dev, и проверяем их.
if ! docker run --rm -v "$work/source/backend:/project:ro" -v "$work:/output" \
  -w /project python:3.12.12-slim sh -c \
  'pip install --disable-pip-version-check uv==0.9.5 && uv export --locked --extra dev --no-emit-project --no-hashes -o /output/requirements.txt' > "$report/uv.log" 2>&1; then
  echo 'Ошибка экспорта backend lock-файла.' >&2; status=1
elif ! docker run --rm -v "$work/requirements.txt:/requirements.txt:ro" -v "$report:/report" \
  --entrypoint sh python:3.12.12-slim -c \
  'pip install --disable-pip-version-check pip-audit==2.9.0 && pip-audit -r /requirements.txt --format json --output /report/pip-audit.json' \
  > "$report/pip-audit.log" 2>&1; then
  echo 'pip-audit обнаружил уязвимость или завершился с ошибкой.' >&2; status=1
fi

# Проверяем frontend lock-файл и применяем политику severity к JSON-отчёту.
if ! docker run --rm -v "$work/source/frontend:/project:ro" -w /project \
  --entrypoint sh node:24.21.0-bookworm-slim -c \
  'npm install --global pnpm@11.19.0 >&2 && pnpm audit --json --audit-level high' \
  > "$report/pnpm-audit.json" 2> "$report/pnpm-audit.log"; then
  echo 'pnpm audit обнаружил уязвимость или завершился с ошибкой.' >&2; status=1
fi
if ! docker run --rm -v "$report/pnpm-audit.json:/audit.json:ro" \
  -v "$work/source/scripts/security_policy.py:/policy.py:ro" python:3.12.12-slim \
  python /policy.py pnpm /audit.json; then
  echo 'pnpm audit: блокирующая или неопределённая severity либо некорректный отчёт.' >&2; status=1
fi

# Задаём фиктивный env и отдельное имя Compose-проекта для сборки образов.
printf '%s\n' 'POSTGRES_PASSWORD=synthetic-test-password' > "$work/test.env"
mkdir "$work/trivy-cache"
project="inventory-security-$run_id"
compose() {
  env -i PATH="$PATH" HOME="${HOME:-/tmp}" DOCKER_HOST="${DOCKER_HOST:-}" docker compose --project-directory "$work/source" --env-file "$work/test.env" \
    -f "$work/source/docker-compose.yml" -p "$project" "$@"
}
# Собираем рабочие образы и получаем внешние образы, указанные в Compose.
build_ok=1
if ! compose build backend frontend > "$report/build.log" 2>&1; then
  echo 'Ошибка сборки рабочих образов; см. build.log.' >&2; status=1
  build_ok=0
fi
pull_ok=1
if ! compose pull db nginx > "$report/pull.log" 2>&1; then
  echo 'Ошибка получения образов db/nginx; см. pull.log.' >&2; status=1
  pull_ok=0
fi
if ! compose config --format json > "$work/compose.json" 2> "$report/compose.log"; then
  echo 'Ошибка чтения конфигурации Compose.' >&2; status=1; build_ok=0; pull_ok=0
fi
# Определяем точные образы, сохраняем их идентификаторы и передаём архивы Trivy.
for service in backend frontend db nginx; do
  case "$service" in backend|frontend) [ "$build_ok" -eq 1 ] || continue;; db|nginx) [ "$pull_ok" -eq 1 ] || continue;; esac
  image=$(docker run --rm -v "$work/compose.json:/compose.json:ro" python:3.12.12-slim \
    python -c 'import json,sys; s=json.load(open("/compose.json"))["services"][sys.argv[1]]; print(s.get("image") or sys.argv[2]+"-"+sys.argv[1])' "$service" "$project") || { status=1; continue; }
  if ! image_id=$(docker image inspect "$image" --format '{{.Id}}'); then
    echo "Образ $service недоступен." >&2; status=1; continue
  fi
  if ! docker image inspect "$image_id" --format '{{.Id}} {{json .RepoDigests}}' > "$report/$service-image.txt"; then
    echo "Ошибка получения digest образа $service." >&2; status=1; continue
  fi
  if ! docker save "$image_id" -o "$work/$service.tar"; then
    echo "Ошибка экспорта образа $service." >&2; status=1; continue
  fi
  if ! docker run --rm -v "$work/$service.tar:/image.tar:ro" -v "$report:/report" -v "$work/trivy-cache:/root/.cache/" \
    aquasec/trivy:0.59.1 image --scanners vuln --input /image.tar --format json \
    --output "/report/$service-trivy.json" \
    > "$report/$service-trivy.log" 2>&1; then
    echo "Trivy: обнаружена проблема или ошибка сканирования $service." >&2; status=1
  elif ! docker run --rm -v "$report/$service-trivy.json:/report.json:ro" \
    -v "$work/source/scripts/security_policy.py:/policy.py:ro" python:3.12.12-slim \
    python /policy.py trivy /report.json; then
    echo "Trivy: блокирующие или неопределённые уязвимости в $service." >&2; status=1
  fi
done

# Возвращаем общий статус и оставляем отчёты после удаления временных файлов.
if [ "$status" -ne 0 ]; then echo 'Одна или несколько проверок завершились ошибкой.' >&2; fi
echo "Отчёты: $report"
exit "$status"
