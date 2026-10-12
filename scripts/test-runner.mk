SHELL := /bin/sh
.PHONY: test backend frontend migrations

# Независимые проверки выполняются и после отказа другого набора.
test:
	@mkdir -p reports
	@status=0; \
	$(MAKE) -f scripts/test-runner.mk backend || status=1; \
	$(MAKE) -f scripts/test-runner.mk frontend || status=1; \
	$(MAKE) -f scripts/test-runner.mk migrations || status=1; \
	exit $$status

backend:
	alembic upgrade head
	pytest tests --junitxml=reports/backend-junit.xml

frontend:
	@status=0; \
	pnpm --dir frontend exec vitest run --reporter=default --reporter=junit --outputFile.junit=/app/reports/frontend-junit.xml || status=1; \
	pnpm --dir frontend build || status=1; \
	exit $$status

migrations:
	python scripts/migration_check.py
