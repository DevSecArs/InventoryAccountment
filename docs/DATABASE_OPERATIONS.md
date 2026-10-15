# Миграции, резервные копии и ресурсы контейнеров

Команды выполняются из корня репозитория. Нужен Docker Compose; PostgreSQL,
Alembic, pg_dump и pg_restore на хост устанавливать не требуется. Используйте
то же имя Compose-проекта и тот же внешний ENV_FILE, что и при запуске.
Путь к файлу задаётся извне; реальные пути и реквизиты в Git не сохраняются.

## Linux с Make

ENV_FILE должен быть экспортирован в текущем shell, если нужен внешний файл.

```bash
make migrate
make backup
```

Миграция собирает актуальный образ, ждёт готовности db и применяет upgrade head.
Она также выполняется автоматически перед запуском API. Одновременные миграторы
одной БД сериализуются advisory-блокировкой; ожидание блокировок ограничено
60 секундами. Ошибка не подавляется: повторять команду нужно после устранения
причины. DDL текущих миграций выполняется в транзакции PostgreSQL.

Backup возвращает BACKUP_PATH. Путь /backups внутри контейнера соответствует
каталогу backups в репозитории. Сохраняйте вместе файл .dump и .dump.metadata.
Для восстановления укажите имя полученного файла вместо example.dump:

```bash
make restore BACKUP=backups/example.dump TARGET_DATABASE=inventory_recovery
```

Это создаёт **новую отдельную БД** inventory_recovery внутри db; рабочая БД
не перезаписывается. Имя должно быть свободно. Повторное восстановление в
существующую БД без явного разрешения отклоняется. Имена БД: латинские буквы,
цифры и подчёркивание, не начинаются с цифры, до 63 символов.

## Docker Compose без Make

В Linux оболочка сама учитывает ENV_FILE:

```bash
sh scripts/compose.sh -f docker-compose.yaml run --rm --build migrate
sh scripts/compose.sh -f docker-compose.yaml run --rm pg-tools sh /scripts/backup_restore.sh backup /backups
sh scripts/compose.sh -f docker-compose.yaml run --rm -e BACKUP_FILE=/backups/example.dump -e TARGET_DATABASE=inventory_recovery pg-tools sh /scripts/backup_restore.sh restore
```

Введите в PowerShell:

```powershell
$composeOptions = @()
if ($env:ENV_FILE) { $composeOptions = @('--env-file', $env:ENV_FILE) }
docker compose @composeOptions run --rm --build migrate
docker compose @composeOptions run --rm pg-tools sh /scripts/backup_restore.sh backup /backups
docker compose @composeOptions run --rm -e BACKUP_FILE=/backups/example.dump -e TARGET_DATABASE=inventory_recovery pg-tools sh /scripts/backup_restore.sh restore
```

Если задавали имя проекта, добавьте его в каждую команду через --project-name.
После изменения ENV_FILE пересоздайте composeOptions. В примерах example.dump
обязательно замените именем созданного дампа; metadata должна находиться рядом.

## Порядок обновления и восстановления

1. Перед обновлением остановите API/Frontend: `docker compose stop app frontend`
   (с теми же --env-file/--project-name). PostgreSQL оставьте запущенным.
2. Выполните backup. Не запускайте миграции одновременно с backup: версия схемы
   в metadata и снимок pg_dump должны относиться к одной версии приложения.
3. Примените миграции и запустите новый образ; проверьте readiness и данные.
4. При восстановлении сначала создайте отдельную БД командой выше. Проверьте
   её данные и ревизию, например через pg-tools:

```bash
sh scripts/compose.sh -f docker-compose.yaml run --rm pg-tools psql -X -v ON_ERROR_STOP=1 -d inventory_recovery -c 'SELECT version_num FROM alembic_version; SELECT count(*) FROM materials;'
```

В PowerShell замените префикс `sh scripts/compose.sh -f docker-compose.yaml`
на `docker compose @composeOptions`.

5. Для переключения приложения остановите API/Frontend, измените POSTGRES_DB
   во внешнем файле на проверенную восстановленную БД и выполните запуск с
   миграциями совместимого образа. Сам restore переключение не выполняет.
   Для отката верните прежнее POSTGRES_DB и совместимый образ; исходная БД
   остаётся сохранённой. Не удаляйте том при восстановлении.

Backup публикуется только после pg_dump и проверки читаемости архива. Имена
уникальны даже при одновременных запусках. При штатном отказе временный каталог
удаляется; после SIGKILL/сбоя хоста может остаться скрытый .backup-* — это не
готовая резервная копия. Restore проверяет checksum, размер, версию инструмента
и Alembic revision, импортирует данные одной транзакцией. Дамп не заменяет
проверенное восстановление и внешнее хранилище резервных копий.

Файлы создаются с ограниченными правами (umask 077); в Linux при запуске
pg-tools от root они принадлежат root. Копировать их во внешнее защищённое
хранилище следует с соответствующими правами, не открывая доступ всем.
Каталог backups должен быть доступен контейнеру для записи и иметь свободное
место. Временный дамп и публикация находятся на одной файловой системе.
Для восстановления требуется место под новую БД; лимиты RAM не ограничивают
размер томов и дампов. Подключение libpq ограничено 10 секундами; обрыв связи
даёт ошибку, а не автоматический повтор разрушительной операции.

## Ограничения ресурсов

| Сервис | CPU, максимум ядер | RAM | PID/потоки |
| --- | --- | --- | --- |
| API | 1 | 512 МиБ | 128 |
| Миграции | 1 | 512 МиБ | 128 |
| Frontend (Vite) | 1 | 768 МиБ | 128 |
| PostgreSQL | 1 | 1 ГиБ | 256 |
| pg-tools | 1 | 512 МиБ | 128 |
| Backend test / общий test-runner | 2 | 2 ГиБ | 256 |
| Frontend проверки через Make | 2 | 2 ГиБ | 256 |

Это стартовые лимиты для небольшого MVP, не обещание пропускной способности.
API и Alembic имеют небольшой рабочий набор; pg_dump/pg_restore работают
последовательно и передают данные потоково. БД оставлен запас для процессов,
кэша и запросов. Vite требует больше памяти при преобразовании зависимостей:
в локальном прогоне потреблял около 584 МиБ, поэтому 512 МиБ ему недостаточно
как стартовый предел. CPU ограничивает конкуренцию за хост, PID-лимит — число
процессов и потоков. Tests/TypeScript/mypy получают больше RAM и CPU.

Используются cpus, mem_limit, memswap_limit и pids_limit обычного Compose;
Swarm не требуется. MemorySwap равен Memory: дополнительный swap контейнеру
не выделяется. При нехватке RAM возможен OOM, его нельзя считать успехом.
Рабочий стек имеет суммарные пределы RAM около 2,25 ГиБ, с двумя служебными
контейнерами — 3,25 ГиБ. Для небольшого стенда разумно выделить Docker минимум
4 ГиБ, для одновременных тестов — больше. CPU-пределы — максимумы, не резервы.

Диагностика: `docker compose stats --no-stream`, `docker compose ps -a` и
`docker inspect <container>` (HostConfig.Memory/NanoCpus/PidsLimit,
State.OOMKilled). Передавайте обычные параметры проекта/env. При росте нагрузки
корректируйте лимиты в Compose или отдельном override по замерам, а не отключайте
их. Лимиты runtime-контейнеров не ограничивают Docker BuildKit во время сборки.

## Изолированные проверки

```bash
make migration-check
make backup-restore-check
make verify
```

Они используют тестовую БД и не читают рабочий ENV_FILE. Проверка восстановления
создаёт контрольные записи, делает backup, меняет тестовые данные и сверяет
восстановленные строки, связи и ревизию. Дополнительно проверяет отказ для
повреждённого дампа и существующей цели без подтверждения.
