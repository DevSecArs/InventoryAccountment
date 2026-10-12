# Отдельный Linux-образ для тестов

Образ `inventory-accountment-tests:local` содержит Python, Node.js, pnpm,
GNU Make и зависимости из lock-файлов. На Windows нужны Python и Docker
Desktop в режиме Linux-контейнеров; Make и node_modules на хосте не нужны.

Из корня репозитория:

```powershell
python scripts/build_test_image.py
docker compose -p inventory-tests-local -f compose.test-runner.yaml run --rm tests
docker compose -p inventory-tests-local -f compose.test-runner.yaml down --volumes
```

После изменений исходников и тестов повторять сборку. Сборщик передаёт
gzip/tar-контекст из разрешённых каталогов, исключая зависимости и `.env`
до обхода их содержимого. Новые незакоммиченные тесты также попадают в образ.
Не выполнять одновременно сборки разных версий под одним тегом; независимым
прогонам назначать разные Compose-проекты.

Контейнер выполняет `make -f scripts/test-runner.mk test`: Backend с покрытием,
Frontend с JUnit и сборкой, проверку миграций. Отказ одного набора не мешает
независимым проверкам, но итоговый exit code остаётся ненулевым. Порог Backend
80% сохраняется. Отчёты: `reports/unix-tests/backend-junit.xml`,
`frontend-junit.xml`, `coverage.xml`, `htmlcov/`. Перед повторным прогоном
сохранить нужные отчёты отдельно: следующий запуск заменяет их.

PostgreSQL доступна только в сети тестового проекта. Порты и Docker socket
не публикуются. Очистку выполнять и после отказа; `down --volumes` удаляет
только данные указанного проекта, поэтому не подставлять имя рабочего стенда.

Это не замена полного `make verify DOCKER=1`: SAST, audit, mutation,
backup/restore и сканирование образа остаются обязательными для приёмки.
Успешные тесты не подтверждают CI или выпуск.

Критические изменения для PR: `Dockerfile.tests`, `compose.test-runner.yaml`,
`scripts/build_test_image.py`, `scripts/test-runner.mk`, регрессионные тесты.
Миграций данных нет. Откат выполняется возвратом предыдущего кода и образа;
удаление нового тестового контура не меняет рабочую БД.
