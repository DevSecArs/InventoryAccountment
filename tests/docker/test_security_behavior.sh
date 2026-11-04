#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
base=$(mktemp -d)
trap 'rm -rf "$base"' EXIT
mkdir -p "$base/project/scripts" "$base/bin"
if [ "$(uname -s | cut -c1-5)" = MINGW ]; then
  printf '#!/bin/sh\nexec python "$@"\n' > "$base/bin/python3"
  chmod +x "$base/bin/python3"
fi
cp "$root"/scripts/security*.py "$root/scripts/security.sh" "$base/project/scripts/"
cd "$base/project"
git init -q
git -c user.name=test -c user.email=test@example.invalid commit --allow-empty -qm fixture
cat > "$base/bin/df" <<'EOF'
#!/bin/sh
case "$1" in
  -T) printf 'Filesystem Type\nmock disk\n';;
  -Pi) printf 'Filesystem Inodes IUsed IFree IUse%% Mounted\nmock 99999 1 %s 1%% /\n' "${INODES:-50000}";;
  *) printf 'Filesystem 1024-blocks Used Available Capacity Mounted\nmock 99999999 1 %s 1%% /\n' "${SPACE:-50000000}";;
esac
EOF
cat > "$base/bin/docker" <<'EOF'
#!/bin/sh
set -eu
case "$1" in
  compose)
    case " $* " in *' config '*) printf '{}\n';; esac;;
  image)
    case "$*" in *'{{.Size}}'*) echo 1000;; *'RepoDigests'*) echo 'sha256:fake []';; *) echo sha256:fake;; esac;;
  save)
    shift; shift; shift
    for archive in "$(dirname "$1")"/*.tar; do [ ! -e "$archive" ] || exit 90; done
    printf partial > "$1"
    [ "${MODE:-}" != export ] || exit 1;;
  run)
    args=" $* "
    report= work=
    while [ "$#" -gt 0 ]; do
      if [ "$1" = -v ]; then
        shift
        case "$1" in *:/report) report=${1%:/report};; *:/output) work=${1%:/output};; esac
      fi
      shift
    done
    case "$args" in
      *zricethezav*)
        case "$args" in *' git '*) file=gitleaks-history;; *) file=gitleaks-source;; esac
        if [ "${MODE:-}" = findings ]; then printf '[{"RuleID":"fixture"}]' > "$report/$file.json"; exit 1; fi
        if [ "${MODE:-}" = scanner ]; then exit 2; fi
        printf '[]' > "$report/$file.json";;
      *'uv export'*) : > "$work/requirements.txt";;
      *pip-audit*) printf '{"dependencies":[]}' > "$report/pip-audit.json";;
      *'python -c'*) echo fake-image;;
      *aquasec/trivy*)
        if [ "${MODE:-}" = signal ]; then kill -TERM "$PPID"; exit 1; fi
        if [ "${MODE:-}" = trivy ]; then exit 2; fi
        for service in backend db nginx; do
          case "$args" in *"/report/$service-trivy.json"*) printf '{"SchemaVersion":2,"Results":[{"Target":"image"}]}' > "$report/$service-trivy.json";; esac
        done;;
    esac;;
esac
EOF
chmod +x "$base/bin/df" "$base/bin/docker"
export PATH="$base/bin:$PATH"
run_case() {
  mode=$1
  rm -rf reports
  code=0
  MODE=$mode sh scripts/security.sh > "$base/output" 2>&1 || code=$?
  if [ "$mode" = success ] && [ "$code" -ne 0 ]; then cat "$base/output"; fi
  set -- reports/*/security
  report=$1
  [ -f "$report/status.txt" ]
  [ -z "$(find "$report" -name '*.tar' -o -name 'security-work.*')" ]
}
run_case success
[ "$code" -eq 0 ]
grep -q 'nginx-trivy: SUCCESS' "$report/status.txt"
grep -q 'backend-trivy: SUCCESS' "$report/status.txt"
grep -q 'db-trivy: SUCCESS' "$report/status.txt"
! grep -q 'frontend-trivy' "$report/status.txt"
run_case findings
[ "$code" -ne 0 ]
grep -q 'gitleaks-source: FINDINGS' "$report/status.txt"
run_case scanner
[ "$code" -ne 0 ]
grep -q 'gitleaks-source: ERROR' "$report/status.txt"
run_case export
[ "$code" -ne 0 ]
grep -q 'backend-trivy: NOT RUN' "$report/status.txt"
run_case trivy
[ "$code" -ne 0 ]
grep -q 'backend-trivy: ERROR' "$report/status.txt"
run_case signal
[ "$code" -ne 0 ]
rm -rf reports
if SPACE=1 sh scripts/security.sh > "$base/output" 2>&1; then exit 1; fi
grep -q 'недостаточно места' "$base/output"
rm -rf reports
if INODES=1 sh scripts/security.sh > "$base/output" 2>&1; then exit 1; fi
grep -q 'недостаточно места' "$base/output"
echo 'Поведенческие проверки security пройдены.'
