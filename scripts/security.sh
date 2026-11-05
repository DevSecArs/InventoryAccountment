#!/bin/sh
set -eu

# Подготавливаем отдельный каталог отчётов и временное рабочее пространство.
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
mode=${1:-secrets}
case "$mode" in secrets|ci|dependencies) ;; *) echo "Неизвестный режим security." >&2; exit 1;; esac
run_id="$(date -u +%Y%m%dt%H%M%Sz)-$$"
report="$root/reports/$run_id/security"
umask 077
mkdir -p "$report"
tmp_root=${SECURITY_TMPDIR:-$report}
[ -d "$tmp_root" ] && [ -w "$tmp_root" ] || { echo "Ошибка: временный каталог недоступен: $tmp_root" >&2; exit 1; }
tmp_root=$(CDPATH= cd -- "$tmp_root" && pwd -P)
if df -T "$tmp_root" 2>/dev/null | awk 'NR==2 && $2 == "tmpfs" {found=1} END {exit !found}'; then
  echo "Предупреждение: $tmp_root находится на tmpfs; учитывайте его ограничение." >&2
fi
work=$(mktemp -d "$tmp_root/security-work.XXXXXXXX")
cleanup() {
  result=$?
  trap - EXIT HUP INT TERM
  case "$work" in
    "$tmp_root"/security-work.*) [ -n "$work" ] && [ "$work" != / ] && [ "$work" != "$root" ] && rm -rf -- "$work" || { echo 'Ошибка очистки временного каталога.' >&2; [ "$result" -ne 0 ] || result=1; } ;;
    *) echo 'Ошибка: небезопасный путь очистки.' >&2; [ "$result" -ne 0 ] || result=1 ;;
  esac
  exit "$result"
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
check_space() {
  required=$1
  if ! df -Pk "$work" > "$report/space.txt" || ! df -Pi "$work" > "$report/inodes.txt"; then
    echo 'ERROR: невозможно проверить свободное место и inode.' >&2; return 1
  fi
  available=$(awk 'NR==2 {print $4}' "$report/space.txt")
  inodes=$(awk 'NR==2 {print $4}' "$report/inodes.txt")
  case "$available:$inodes:$required" in *[!0-9:]*|::*|*::*|*:) echo 'ERROR: некорректный ответ df.' >&2; return 1;; esac
  if [ "$available" -lt "$required" ] || [ "$inodes" -lt 1024 ]; then
    echo "ERROR: недостаточно места или inode в $tmp_root: доступно ${available} KiB и $inodes inode; требуется не менее ${required} KiB и 1024 inode." >&2; return 1
  fi
}
# Запас нужен копии исходников и базе Trivy; оценка не гарантирует размер архива.
if ! check_space 1048576; then
  case "$mode" in
    secrets) stages="gitleaks-history gitleaks-source";;
    dependencies) stages="pip-audit";;
    ci) stages="pip-audit backend-trivy db-trivy nginx-trivy";;
  esac
  for stage in $stages; do
    printf '%s: NOT RUN\n' "$stage" >> "$report/status.txt"
  done
  echo "Отчёты: $report" >&2
  exit 1
fi
mkdir "$work/source"

# Проверяем полноту истории и создаём отдельную bare-копию без рабочего дерева.
status=0
history_ok=1
if [ "$mode" = secrets ]; then
if [ "$(git rev-parse --is-shallow-repository)" != false ]; then
  echo 'Ошибка: история Git неполная.' >&2
  status=1; history_ok=0
fi
if ! git clone --bare --no-local "$root" "$work/history.git" > "$report/history-clone.log" 2>&1; then
  echo 'Ошибка копирования истории Git.' >&2; status=1; history_ok=0
elif ! git --git-dir="$work/history.git" fsck --connectivity-only > "$report/history-fsck.log" 2>&1; then
  echo 'Ошибка целостности копии истории.' >&2; status=1; history_ok=0
fi
fi
# Копирование обрабатывает имена Git с NUL и исключает рабочие данные.
source_ok=1
if ! python3 "$root/scripts/security_workspace.py" "$root" "$work" "$report/tracked-env.txt"; then
  echo 'ERROR: подготовка исходников не выполнена полностью.' >&2; status=1
  source_ok=0
fi

# Записываем итог каждого этапа отдельно; ошибка и находки блокируют запуск.
result() {
  printf '%s: %s\n' "$1" "$2" | tee -a "$report/status.txt"
  case "$2" in ERROR|FINDINGS) status=1;; esac
}
classify() {
  stage=$1; scanner=$2; code=$3; json=$4
  if outcome=$(python3 "$root/scripts/security_policy.py" "$scanner" "$json" "$code" 2>> "$report/policy.log"); then
    result "$stage" "$outcome"
  else
    result "$stage" ERROR
  fi
}
if [ "$mode" = secrets ]; then
if [ "$history_ok" -eq 1 ]; then
  code=0
  docker run --rm -v "$work/history.git:/repo:ro" -v "$report:/report" \
    zricethezav/gitleaks:v8.24.2 git /repo --log-opts=--all --redact=100 \
    --report-format json --report-path /report/gitleaks-history.json --no-banner > "$report/gitleaks-history.log" 2>&1 || code=$?
  classify gitleaks-history gitleaks "$code" "$report/gitleaks-history.json"
else result gitleaks-history 'NOT RUN'; fi
if [ "$source_ok" -eq 1 ]; then
  code=0
  docker run --rm -v "$work/source:/source:ro" -v "$report:/report" \
    zricethezav/gitleaks:v8.24.2 dir /source --redact=100 \
    --report-format json --report-path /report/gitleaks-source.json --no-banner > "$report/gitleaks-source.log" 2>&1 || code=$?
  classify gitleaks-source gitleaks "$code" "$report/gitleaks-source.json"
else result gitleaks-source 'NOT RUN'; fi

fi
if [ "$mode" != secrets ]; then
if [ "$source_ok" -ne 1 ]; then
  stages="pip-audit"
  if [ "$mode" = ci ]; then stages="$stages backend-trivy db-trivy nginx-trivy"; fi
  for stage in $stages; do result "$stage" 'NOT RUN'; done
  echo "Отчёты: $report" >&2
  exit 1
fi
printf '%s\n' 'uv 0.9.5' 'pip-audit 2.9.0' > "$report/versions.txt"
if [ "$mode" = ci ]; then printf '%s\n' 'Trivy 0.59.1' >> "$report/versions.txt"; fi
if docker run --rm -v "$work/source/backend:/project:ro" -v "$work:/output" \
  -w /project python:3.12.12-slim sh -c \
  'pip install --disable-pip-version-check uv==0.9.5 && uv export --locked --extra dev --no-emit-project --no-hashes -o /output/requirements.txt' > "$report/uv.log" 2>&1; then
  code=0
  docker run --rm -v "$work/requirements.txt:/requirements.txt:ro" -v "$report:/report" \
    --entrypoint sh python:3.12.12-slim -c \
    'pip install --disable-pip-version-check pip-audit==2.9.0 && pip-audit -r /requirements.txt --format json --output /report/pip-audit.json' \
    > "$report/pip-audit.log" 2>&1 || code=$?
  classify pip-audit pip-audit "$code" "$report/pip-audit.json"
else
  result uv ERROR
  result pip-audit 'NOT RUN'
fi
# Отдельный режим CI не пересобирает образы: их проверяет image_scan.
if [ "$mode" = dependencies ]; then
  echo "Отчёты: $report"
  exit "$status"
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
if ! compose build backend nginx > "$report/build.log" 2>&1; then
  echo 'Ошибка сборки рабочих образов; см. build.log.' >&2; status=1
  build_ok=0
fi
pull_ok=1
if ! compose build db > "$report/pull.log" 2>&1; then
  echo 'Ошибка получения образа db; см. pull.log.' >&2; status=1
  pull_ok=0
fi
if ! compose config --format json > "$work/compose.json" 2> "$report/compose.log"; then
  echo 'Ошибка чтения конфигурации Compose.' >&2; status=1; build_ok=0; pull_ok=0
fi
# Определяем точные образы, сохраняем их идентификаторы и передаём архивы Trivy.
for service in backend db nginx; do
  case "$service" in backend|nginx) ready=$build_ok;; db) ready=$pull_ok;; esac
  if [ "$ready" -ne 1 ]; then result "$service-trivy" 'NOT RUN'; continue; fi
  image=$(docker run --rm -v "$work/compose.json:/compose.json:ro" python:3.12.12-slim \
    python -c 'import json,sys; s=json.load(open("/compose.json"))["services"][sys.argv[1]]; print(s.get("image") or sys.argv[2]+"-"+sys.argv[1])' "$service" "$project") || { result "$service-trivy" 'NOT RUN'; status=1; continue; }
  if ! image_id=$(docker image inspect "$image" --format '{{.Id}}'); then
    echo "Образ $service недоступен." >&2; result "$service-trivy" 'NOT RUN'; status=1; continue
  fi
  if ! docker image inspect "$image_id" --format '{{.Id}} {{json .RepoDigests}}' > "$report/$service-image.txt"; then
    echo "Ошибка получения digest образа $service." >&2; result "$service-trivy" 'NOT RUN'; status=1; continue
  fi
  size=$(docker image inspect "$image_id" --format '{{.Size}}') || size=invalid
  case "$size" in ''|*[!0-9]*) echo "ERROR: неизвестен размер образа $service." >&2; status=1; result "$service-trivy" 'NOT RUN'; continue;; esac
  # Двойной размер образа и 1 ГиБ запаса — ориентир, а не точный размер tar.
  required=$((size / 512 + 1048576))
  if ! check_space "$required"; then status=1; result "$service-trivy" 'NOT RUN'; continue; fi
  if ! docker save "$image_id" -o "$work/$service.tar" 2> "$report/$service-export.log"; then
    echo "ERROR: экспорт $service не выполнен; проверьте место и inode в $tmp_root." >&2
    rm -f -- "$work/$service.tar" || echo 'ERROR: не удалось удалить частичный архив.' >&2
    status=1; result "$service-trivy" 'NOT RUN'; continue
  fi
  code=0
  # Кэш и отчёты должны принадлежать пользователю, который выполняет очистку.
  docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
    -v "$work/$service.tar:/image.tar:ro" -v "$report:/report" -v "$work/trivy-cache:/cache" \
    aquasec/trivy:0.59.1 image --ignore-unfixed --scanners vuln --input /image.tar --format json \
    --cache-dir /cache \
    --output "/report/$service-trivy.json" > "$report/$service-trivy.log" 2>&1 || code=$?
  rm -f -- "$work/$service.tar" || { echo "ERROR: не удалось удалить архив $service." >&2; status=1; }
  classify "$service-trivy" trivy "$code" "$report/$service-trivy.json"
done

fi
# Возвращаем общий статус и оставляем отчёты после удаления временных файлов.
if [ "$status" -ne 0 ]; then echo 'Одна или несколько проверок завершились ошибкой.' >&2; fi
echo "Отчёты: $report"
exit "$status"
