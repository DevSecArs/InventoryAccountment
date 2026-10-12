# Проверки GitHub

[Workflow verify.yml](workflows/verify.yml) запускается на push и pull_request.
Ubuntu 24.04, Python 3.11 и Node.js 24; checkout получает полную историю.
Последовательно выполняются make setup DOCKER=1 и make verify DOCKER=1.
Каталог reports/ сохраняется через upload-artifact с if: always().
Это описание конфигурации, а не подтверждение успешного CI. CD отсутствует.

CODEOWNERS пока отсутствует: ответственные не назначены в репозитории.
После назначения указать владельцев критических файлов: AGENTS.md,
Makefile, Dockerfile и Dockerfile.tests, Compose, workflow, миграции,
backup/restore, скрипты проверок, конфигурации качества и требования приёмки.

Администратору требуется настроить защиту основной ветки: запрет прямой
записи, успешный workflow актуального SHA, независимое одобрение,
одобрение CODEOWNERS, сброс одобрений после изменений и разрешение обсуждений.
Настройки GitHub не хранятся в этом файле; их фактическое включение не проверено.

Ограничение текущего Makefile: container-smoke передаёт сканеру фиксированный
тег inventory-accountment-local-ubuntu-verify-app:latest. Проверку совпадения
просканированного и запущенного image ID нельзя считать обеспеченной.
Отдельный [Linux test-образ](../docs/UNIX_TESTS.md) выполняет тесты и миграции,
но не заменяет workflow и полный verify.
