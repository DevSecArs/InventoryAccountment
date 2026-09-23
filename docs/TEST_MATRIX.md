# Матрица автоматических тестов

| Требование ТЗ | Сценарий | Уровень | Команда |
| --- | --- | --- | --- |
| Health, `X-Request-ID`, единый формат ошибок | Жизнеспособность, 401 и поля ошибки | API/integration | `make test TEST=1` |
| Аутентификация и CSRF | Регистрация администратора, запрет записи без CSRF, повторная регистрация | API/integration | `make test TEST=1` |
| Справочники | Нормализация кодов, СИ, уникальность, поиск, пагинация, архивирование и ссылки | unit + API/integration | `make test TEST=1` |
| Клиент HTTP frontend | Cookie, CSRF, request ID и преобразование ошибки | unit/frontend | `make test TEST=1` |
| Цепочка миграций | Создание чистой схемы, обновление заполненной БД, ограничения и round-trip | integration | `make migration-check TEST=1` |
| Backup и restore | Повреждение известных тестовых данных, восстановление связей, количества строк и Alembic revision | integration | `make backup-restore-check TEST=1` |
| Контейнерный сценарий | Readiness, регистрация, запись и чтение через API и PostgreSQL | smoke/integration | `make container-check TEST=1` |
| Черновики поступлений | Создание, чтение, список, замена позиций, непустой состав и миграция `NUMERIC(18,3)` | API/integration | `make test TEST=1`, `make migration-check TEST=1` |

Проведение поступлений, outbox и отчёты пока не входят в реализованный контракт
приложения. Их автоматические сценарии будут добавлены вместе с
соответствующими функциями в следующих задачах.
