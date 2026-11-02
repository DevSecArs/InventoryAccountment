#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT HUP INT TERM
cat > "$work/fake-make" <<'EOF'
#!/bin/sh
for stage do :; done
printf '%s\n' "$stage" >> "$STAGE_LOG"
[ "$stage" != "$FAIL_STAGE" ]
EOF
chmod +x "$work/fake-make"
for failure in test quality security none; do
  STAGE_LOG="$work/stages" FAIL_STAGE="$failure"; export STAGE_LOG FAIL_STAGE
  : > "$STAGE_LOG"
  if make -f "$root/Makefile" verify MAKE="$work/fake-make" > "$work/result" 2>&1; then
    [ "$failure" = none ] || exit 1
  else
    [ "$failure" != none ] || exit 1
  fi
  case "$failure" in
    test) expected='test';;
    quality) expected=$(printf 'test\nquality');;
    *) expected=$(printf 'test\nquality\nsecurity');;
  esac
  [ "$(cat "$STAGE_LOG")" = "$expected" ] || exit 1
done
echo 'verify: последовательность и ошибки этапов проверены.'
