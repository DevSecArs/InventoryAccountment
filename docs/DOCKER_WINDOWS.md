# Ручной запуск на Windows без Make

Нужны только Docker Desktop в режиме Linux containers и PowerShell.
Python, Node.js, pnpm и Make на Windows устанавливать не требуется.
Команды выполнять из корня репозитория. Это локальный учебный стенд:
порты доступны только на этом компьютере, учётные данные БД демонстрационные.

## Первый запуск

Если ENV_FILE уже задан в окружении, команды используют его. Чтобы выбрать
файл интерактивно, сначала выполните `$env:ENV_FILE = Read-Host 'Путь к файлу настроек'`.
При смене ENV_FILE пересоздайте массив composeOptions в текущей сессии.

Введите в PowerShell:

```powershell
$composeOptions = @()
if ($env:ENV_FILE) { $composeOptions = @('--env-file', $env:ENV_FILE) }
docker compose @composeOptions up -d --build --wait
```

Compose собирает образы из корня проекта; .dockerignore исключает локальные
зависимости и .env из контекста сборки.
Compose запускает PostgreSQL, применяет миграции, затем запускает API и UI.
При ошибке миграций приложение не стартует.

- Интерфейс: http://localhost:5180 — создайте первого администратора на экране регистрации.
- Swagger API: http://localhost:8010/docs.
- Готовность API: http://localhost:8010/health/ready.

Режим development позволяет локальный вход по HTTP. Frontend использует
Vite dev-сервер и прокси к API. Этот файл не предназначен для production.

## Остановка и повторный запуск

```powershell
docker compose @composeOptions down
docker compose @composeOptions up -d --no-build --wait
```

Данные и созданный пользователь сохраняются в Docker-томе inventory_data
проекта inventory-compose. Не добавляйте --volumes, если данные нужны.

## Обновление после изменения кода

Остановите стенд, затем выполните команду первого запуска. Исходники
копируются в образ; простого перезапуска контейнера недостаточно.
Миграции применяются при следующем запуске. Перед обновлением ценных данных
сохраните backup; downgrade схемы автоматически не выполняется.

## Диагностика

```powershell
docker compose @composeOptions ps -a
docker compose @composeOptions logs --tail 100 migrate app frontend db
```

migrate со статусом Exited (0) — нормальное успешное завершение миграций.
Если порты заняты, задайте другие в этой PowerShell-сессии перед запуском:

```powershell
$env:APP_PORT = '8011'
$env:FRONTEND_PORT = '5181'
docker compose @composeOptions up -d --no-build --wait
```

Для полного сброса **только этого локального стенда**, когда его данные
больше не нужны, остановите его с удалением тома:

```powershell
docker compose @composeOptions down --volumes
```

Автоматические тесты запускаются отдельно по [UNIX_TESTS.md](UNIX_TESTS.md).
Ручной запуск не заменяет make verify и независимую приёмку.

Внешние настройки задаются через ENV_FILE: [правила передачи и изоляция тестов](../GUIDE.md#внешний-файл-настроек).
Make и deploy учитывают переменную автоматически. В прямых рабочих командах
Compose добавляйте `--env-file "$ENV_FILE"` (Linux) или
`--env-file "$env:ENV_FILE"` (PowerShell), если переменная задана.

[Миграции, backup/restore и ограничения ресурсов](DATABASE_OPERATIONS.md) — команды для Make, Linux и PowerShell.
