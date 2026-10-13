# Отдельный Linux-образ для тестов

Dockerfile.tests содержит Python 3.11, Node.js 24.21.0, pnpm 11.19.0,
GNU Make и зависимости из lock-файлов. На Windows нужны Python и Docker
Desktop в режиме Linux-контейнеров; Make и node_modules на хосте не нужны.

Из корня репозитория:

~~~powershell
python scripts/build_test_image.py
docker compose -p inventory-tests-local -f compose.test-runner.yaml run --rm tests
docker compose -p inventory-tests-local -f compose.test-runner.yaml down --volumes

~~~

Сборщик создаёт inventory-accountment-tests:local через gzip/tar-контекст
из разрешённых файлов и каталогов. node_modules, .venv, .git, символьные
ссылки и файлы .env исключаются до передачи Docker. Исходники frontend,
включая features/reports, и незакоммиченные тесты включаются.
После изменения исходников/тестов образ пересобрать. Команды test-runner и
локализаторы выводов монтируются из рабочей копии, поэтому изменения именно
этих файлов подхватываются без пересборки образа. Разным прогонам назначать
разные Compose-проекты; одновременно не пересобирать разные версии под одним тегом.

Контейнер выполняет make -f scripts/test-runner.mk test:

1. Alembic upgrade head и полный pytest tests с порогом покрытия Backend 80%.
2. Vitest с JUnit и production-сборку Frontend, включающую TypeScript.
3. scripts/migration_check.py: чистая/обновляемая схема, ограничения,
   downgrade/upgrade последней ревизии и Alembic check.

Итоговые подписи pytest и Vitest в консольном выводе локализуются на русский;
исходные имена тестов, сообщения ошибок и диагностические данные сохраняются.

Независимые группы продолжаются после отказа другой группы; общий exit code
остаётся ненулевым. Frontend coverage не настроено. Отдельный unit-прогон
не обеспечивает общий порог покрытия приложения.

Отчёты сохраняются через bind mount:

- reports/unix-tests/backend-junit.xml;
- reports/unix-tests/frontend-junit.xml;
- reports/unix-tests/coverage.xml;
- reports/unix-tests/htmlcov/.

run.log создаётся только при отдельном сохранении консольного вывода.
Повторный запуск заменяет отчёты: нужные результаты сохранить заранее.

PostgreSQL доступна только внутри сети тестового проекта. Порты и Docker
socket не публикуются. Очистку выполнить и после отказа: down --volumes
удаляет данные указанного проекта. Не подставлять имя рабочего стенда.

Контур не заменяет make verify DOCKER=1: SAST, audit, mutation,
backup/restore и сканирование образа выполняются отдельно.
[Последние записанные результаты](../TEST_DEFECTS.md) не означают новый
прогон при чтении инструкции, успешный CI или выпуск.

Критические файлы для независимой проверки: Dockerfile.tests,
compose.test-runner.yaml, scripts/build_test_image.py, scripts/test-runner.mk
и регрессионные тесты. Изменений схемы этот контур не требует.
Откат — возврат предыдущих исходников и пересборка тестового образа;
удаление тестового проекта не меняет рабочую БД.
