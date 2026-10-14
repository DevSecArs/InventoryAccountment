# Первый запуск

Приложение целиком работает в Docker: PostgreSQL, миграции, API и Frontend.
Внешняя БД и системный файл /etc/InventoryAccountment/InventoryAccountment.env
больше не используются. Создаётся новая пустая БД; старые данные не переносятся.

На Windows используйте [инструкцию без Make](DOCKER_WINDOWS.md).

На Linux установите Docker Engine с Compose и GNU Make, затем из корня:

~~~bash
make setup
make run
~~~

Интерфейс: http://localhost:5180. Создайте первого администратора.
API: http://localhost:8010/docs. Проверка БД: http://localhost:8010/health/ready.
API запускается только после успешного Alembic upgrade head.

~~~bash
make status
make down
~~~

Down сохраняет данные. Повторный make run использует тот же том.
Настройки можно задать в корневом .env по .env.example; этот файл не коммитится.
Реквизиты по умолчанию демонстрационные, порты привязаны к loopback.
Не публикуйте этот учебный HTTP-стенд в сеть как production.

Автотесты: make test; полная проверка: make verify.
Проверки используют отдельную контейнерную БД и не очищают БД приложения.
Подробности: [GUIDE.md](../GUIDE.md).
