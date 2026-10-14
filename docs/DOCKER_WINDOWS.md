# Ручной запуск на Windows без Make

Нужны только Docker Desktop в режиме Linux containers и PowerShell.
Python, Node.js, pnpm и Make на Windows устанавливать не требуется.
Команды выполнять из корня репозитория. Это локальный учебный стенд:
порты доступны только на этом компьютере, учётные данные БД демонстрационные.

## Первый запуск

Введите в PowerShell:

```powershell
docker compose up -d --build --wait
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
docker compose down
docker compose up -d --no-build --wait
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
docker compose ps -a
docker compose logs --tail 100 migrate app frontend db
```

migrate со статусом Exited (0) — нормальное успешное завершение миграций.
Если порты заняты, задайте другие в этой PowerShell-сессии перед запуском:

```powershell
$env:APP_PORT = '8011'
$env:FRONTEND_PORT = '5181'
docker compose up -d --no-build --wait
```

Для полного сброса **только этого локального стенда**, когда его данные
больше не нужны, остановите его с удалением тома:

```powershell
docker compose down --volumes
```

Автоматические тесты запускаются отдельно по [UNIX_TESTS.md](UNIX_TESTS.md).
Ручной запуск не заменяет make verify и независимую приёмку.
