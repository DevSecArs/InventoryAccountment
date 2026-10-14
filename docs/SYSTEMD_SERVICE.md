# Переход от systemd к Docker Compose

Отдельные InventoryAccountment.service, InventoryAccountment-migrate.service
и InventoryAccountment-frontend.service больше не создаются и не используются
новым способом развёртывания. Приложение и PostgreSQL работают в Compose.

Существующие службы на сервере не удаляются автоматически. Перед переходом
проверьте их состояние и остановите старое приложение согласованным способом,
чтобы не запустить два экземпляра. Новая БД пуста; внешняя БД не изменяется.

Запуск и диагностика: [Ubuntu](UBUNTU_DEPLOYMENT.md), [Windows](DOCKER_WINDOWS.md).
Логи нового приложения читаются через docker compose logs, управление —
docker compose up/down или соответствующие Make-команды. Запуск после
перезагрузки ОС в этой задаче не объявляется настроенным.
