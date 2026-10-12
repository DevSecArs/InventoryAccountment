# Сеть, firewall и доступ к MVP

Различайте способы запуска:

| Режим | Frontend | Backend | PostgreSQL |
| --- | --- | --- | --- |
| make run | 0.0.0.0:5173 | 0.0.0.0:8000 | Внешняя DATABASE_URL |
| Тестовый Make/Compose | 0.0.0.0:5174 | 0.0.0.0:8001 | Только сеть Compose |
| Обычный Compose | 0.0.0.0:5173 по умолчанию | 0.0.0.0:APP_PORT | 127.0.0.1:POSTGRES_PORT, по умолчанию 5433 |
| Deploy/systemd по умолчанию | 0.0.0.0:4173 (preview) | 127.0.0.1:8000 | Внешняя БД, порт обычно 5432 |
| Отдельный Linux test-runner | Не публикуется | Не публикуется | Только сеть своего проекта |

Порты в примерах — значения конфигурации по умолчанию, не результаты проверки сервера. Клиент браузера обычно обращается к Frontend, который проксирует /api и /health; прямое открытие API клиентам не обязательно.

## Службы systemd и UFW

Пример двух серверов: приложение 10.20.0.10, БД 10.20.0.20, доверенные клиенты 10.10.0.0/24, администраторы 10.10.1.0/24. Это обезличенные значения, замените их своей сетью.

На сервере приложения для учебного preview:

~~~bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from 10.10.1.0/24 to any port 22 proto tcp
sudo ufw allow from 10.10.0.0/24 to any port 4173 proto tcp
sudo ufw enable
sudo ufw status numbered

~~~

Сначала подтвердить доступ SSH и наличие консоли восстановления. Не выполнять пример с чужими адресами на рабочем сервере. Для прямого API отдельно согласуйте EXPOSE_BACKEND=true/BACKEND_HOST и узкое правило; по умолчанию deploy этого не делает.

В приложении есть аутентификация и CSRF, но они не заменяют сетевых ограничений. При APP_ENV=production cookie Secure требует HTTPS. Для production открыть клиентам HTTPS reverse proxy, оставить Backend на loopback и не считать HTTP-preview настроенным TLS. Nginx/TLS-конфигурации в репозитории нет.

Для Docker правила опубликованных портов нужно проверять отдельно от host-процессов: контейнерная публикация управляется Docker-сетью. Нельзя считать наличие правил UFW доказательством недоступности опубликованного контейнерного порта. Проверяйте фактический доступ из разрешённой и запрещённой сети и правила внешнего firewall.

## PostgreSQL на отдельном сервере

В postgresql.conf задайте частный адрес сервера БД:

~~~ini
listen_addresses = '10.20.0.20'

~~~

В pg_hba.conf ограничьте доступ конкретной БД/пользователем/IP приложения:

~~~text
host inventory inventory 10.20.0.10/32 scram-sha-256

~~~

Фактические имена БД/пользователя должны совпадать с DATABASE_URL; учётные данные здесь не создаются. Пути конфигурации можно узнать через администратора PostgreSQL:

~~~bash
sudo -u postgres psql -c 'SHOW config_file;'
sudo -u postgres psql -c 'SHOW hba_file;'

~~~

После контролируемого изменения перезапустите PostgreSQL. На сервере БД разрешите SSH администратору и 5432 только серверу приложения:

~~~bash
sudo ufw allow from 10.10.1.0/24 to any port 22 proto tcp
sudo ufw allow from 10.20.0.10 to any port 5432 proto tcp
sudo ufw default deny incoming
sudo ufw enable
sudo ufw status numbered

~~~

Deploy с DEPLOY_ROLE=db настраивает UFW, но не устанавливает PostgreSQL и не редактирует pg_hba.conf/listen_addresses.

## Проверка и диагностика

На сервере приложения проверить /health/ready по адресу Backend, а с клиента — доступ через Frontend/proxy. Убедиться, что запрещённый клиент не может подключиться к БД; разрешённый app-server может. Ready проверяет SELECT 1, а не все операции и миграции.

Для systemd по умолчанию:

~~~bash
curl --fail http://127.0.0.1:8000/health/ready
sudo systemctl status InventoryAccountment.service --no-pager
sudo journalctl -u InventoryAccountment.service -n 100 --no-pager

~~~

После изменения DATABASE_URL перезапустить InventoryAccountment.service. Правила провайдера/облака должны соответствовать ограничениям ОС. Изменение firewall не заменяет HTTPS, авторизацию и проверку реального входа в браузере.
