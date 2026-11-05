#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT HUP INT TERM
mkdir -p "$work/project/scripts" "$work/bin"
cp "$root/scripts/security.sh" "$work/project/scripts/"
cp "$root/scripts/security_policy.py" "$work/project/scripts/"
cp "$root/scripts/security_workspace.py" "$work/project/scripts/"
printf '#!/bin/sh\nexit 55\n' > "$work/bin/docker"
chmod +x "$work/bin/docker"
cd "$work/project"
git init -q
git -c user.name=test -c user.email=test@example.invalid commit --allow-empty -qm fixture
if PATH="$work/bin:$PATH" sh scripts/security.sh > "$work/output" 2>&1; then
  echo 'Ошибка: сбой Docker не заблокировал security.' >&2
  exit 1
fi
set -- reports/*/security
[ -d "$1" ] && [ -f "$1/gitleaks-history.log" ] && [ -f "$1/gitleaks-source.log" ]
[ ! -f "$1/uv.log" ] && [ ! -f "$1/build.log" ]
echo 'Сбой Docker блокирует security; отчёты сохранены.'
