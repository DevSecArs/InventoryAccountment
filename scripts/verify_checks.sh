#!/bin/sh
# Все проверки используют зависимости, установленные при сборке образа.
set -eu
alembic upgrade head
python scripts/localize_test_output.py -- pytest
pnpm --dir frontend test:run
ruff format --check --no-cache app tests scripts
ruff check --no-cache app tests scripts
MYPY_CACHE_DIR=/tmp/mypy mypy app tests scripts
status=0
bandit -q -r app scripts -lll -f json -o reports/bandit.json || status=$?
python scripts/summarize_bandit.py reports/bandit.json "$status"
test "$status" -eq 0
uv lock --check
uv pip freeze --exclude-editable > /tmp/requirements.txt
pip-audit --strict --format json -o reports/pip-audit.json -r /tmp/requirements.txt
pnpm --dir frontend quality
pnpm --dir frontend audit --audit-level=high --json > reports/pnpm-audit.json
pnpm --dir frontend build
PYTEST_ADDOPTS=--no-cov python scripts/check_critical_mutations.py
python scripts/migration_check.py
