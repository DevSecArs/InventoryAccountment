# Запуск на Ubuntu

Единственный поддерживаемый способ запуска — Docker Compose с PostgreSQL
внутри проекта. Внешняя БД, отдельные Python/Node-службы и их systemd units
больше не создаются. Требуются Docker Engine/Compose, Git, GNU Make и Python 3.11+ для оркестрации проверок.

~~~bash
make setup
make up
make status
~~~

Без Make:

~~~bash
sh scripts/compose.sh -f docker-compose.yaml up --build -d --wait
sh scripts/compose.sh -f docker-compose.yaml ps -a
~~~

Настройки берутся из ENV_FILE, а без него — из корневого .env или значений по умолчанию. Не задавайте
DATABASE_URL внешнего сервера: Compose передаёт адрес db и POSTGRES_*.
БД не имеет опубликованного порта; UI/API доступны только через loopback.
Для удалённого production-доступа требуется отдельная задача TLS/reverse proxy
и соответствующего режима cookie. Текущий frontend — Vite dev-сервер.

Миграции выполняются сервисом migrate до API. При ошибке смотрите:

~~~bash
sh scripts/compose.sh -f docker-compose.yaml logs --tail 100 migrate app db
~~~

Остановка make down сохраняет том. Перед обновлением ценных данных выполните
make backup и проверьте восстановление отдельно. Затем остановите приложение,
обновите код и запустите make up. Для отката верните совместимую ревизию;
downgrade и удаление тома автоматически не выполняются.

Ранее созданные systemd-службы или внешняя БД не удаляются скриптами проекта.
Перед переходом остановите старое приложение контролируемо; старые данные
сохраните отдельно. Эта задача предусматривает новую пустую БД, не перенос.

Приёмка: make verify, успешный CI, независимое одобрение и живая демонстрация.
[Команды и ограничения](../GUIDE.md).

Внешние настройки задаются через ENV_FILE: [правила передачи и изоляция тестов](../GUIDE.md#внешний-файл-настроек).
Make и deploy учитывают переменную автоматически. В прямых рабочих командах
Compose добавляйте `--env-file "$ENV_FILE"` (Linux) или
`--env-file "$env:ENV_FILE"` (PowerShell), если переменная задана.
