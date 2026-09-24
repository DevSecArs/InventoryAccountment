# Матрица автоматических тестов

| Требование ТЗ | Сценарий | Уровень | Команда |
| --- | --- | --- | --- |
| Health, readiness, `X-Request-ID`, единый формат ошибок | Жизнеспособность, 401, 404, 409, 422, 503 и поля ошибки | API/integration: `test_health_and_error_format`, `test_readiness_reports_database_unavailable`, `test_receipt_pagination_errors_and_database_conflict` | `make test LOCAL=1` |
| Аутентификация и CSRF | Регистрация администратора, отсутствие и истечение сессии, запрет записи без CSRF, права администратора | API/integration: `test_authentication_and_csrf_are_required`, `test_expired_session_and_missing_csrf_have_uniform_errors`, `test_non_admin_cannot_purge_archived_catalog` | `make test LOCAL=1` |
| Справочники | Нормализация кодов, СИ, уникальность, поиск, границы пагинации, архивирование и ссылки | unit + API/integration: `test_catalog_crud_pagination_search_and_archiving`, `test_catalog_pagination_and_search_parameter_boundaries` | `make test LOCAL=1` |
| Клиент HTTP frontend | Cookie, CSRF, request ID и преобразование ошибки | unit/frontend | `make test LOCAL=1` |
| Цепочка миграций | Создание чистой схемы, обновление заполненной БД, ограничения и round-trip | integration | `make migration-check LOCAL=1` |
| Backup и restore | Повреждение известных тестовых данных, восстановление связей, количества строк и Alembic revision | integration | `make backup-restore-check LOCAL=1` |
| Контейнерный сценарий | Readiness, регистрация, запись и чтение через API и PostgreSQL | smoke/integration | `make container-check LOCAL=1` |
| Номер черновика поступления | Пустая строка, пробелы, границы 64/65, нормализация, уникальность у поставщика и допустимость у другого | unit + API/integration: `test_receipt_document_number_is_normalized_and_has_boundary`, `test_receipt_rejects_invalid_document_number`, `test_receipt_document_number_boundaries_and_supplier_uniqueness` | `make test LOCAL=1` |
| Позиции черновика поступления | Непустой состав, уникальность материала, `0`, отрицательное, минимальное положительное, избыточная точность и переполнение `NUMERIC(18,3)` | unit + API/integration: `test_receipt_rejects_invalid_items`, `test_receipt_rejects_quantity_boundaries`, `test_receipt_rejects_duplicate_and_unknown_items`, `test_receipt_quantity_respects_positive_numeric_18_3` | `make test LOCAL=1` |
| Ссылки и изменение черновика | Неизвестные и архивные поставщик, материал и единица; запрет редактирования нечерновика; транзакционный откат | API/integration: `test_receipt_rejects_archived_links`, `test_receipt_update_rolls_back_conflicts_and_rejects_non_draft` | `make test LOCAL=1` |
| Целостность поступления | Ограничение PostgreSQL для пустого номера, конфликт unique и ответ API 409 | API/integration: `test_receipt_database_rejects_blank_document_number`, `test_receipt_pagination_errors_and_database_conflict` | `make test LOCAL=1`, `make migration-check LOCAL=1` |

Проведение поступлений, outbox и отчёты пока не входят в реализованный контракт
приложения. Их автоматические сценарии будут добавлены вместе с
соответствующими функциями в следующих задачах.
