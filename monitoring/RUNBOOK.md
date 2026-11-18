# Runbook: наблюдаемость InventoryAccountment

## Компоненты

- Prometheus: http://192.168.56.111:9090
- Grafana: http://192.168.56.111:3000
- Node Exporter: адрес Docker bridge на VM, порт 9100
- Backend: /metrics, /health/live, /health/ready
- Dashboard Grafana: InventoryAccountment — наблюдаемость
- Правило Prometheus: BackendUnavailable

Мониторинг запускается отдельным Docker Compose-проектом
inventory-monitoring. Grafana и Prometheus опубликованы на 0.0.0.0
(3000 и 9090). При изменении firewall согласуйте доверенные источники доступа;
опубликованные Docker-порты могут обходить UFW. Реальную внешнюю доступность
нужно проверять с нужного клиентского узла.

## Первоначальный запуск и выбор окружения

Все команды — Bash на VM 192.168.56.111 из корня этой рабочей копии.
Dev использует docker-compose.yml, Production — deploy/docker-compose.staging.yml.
Сначала запустите monitoring: он создаёт внешнюю сеть inventory-observability.
К ней постоянно подключены только backend приложения и Prometheus/Grafana.
БД и Nginx остаются в сети своего приложения. При штатном deploy/откате
используется текущий Compose с постоянными DNS aliases backend-dev/backend-production.
Старый checkout без этих настроек не обеспечивает мониторинг автоматически.

1. Проверьте место и Docker; запустите registry по README. Не очищайте тома.

```bash
df -h /
docker info
docker compose -f docker-compose.registry.yml up -d
curl -fsS http://192.168.56.111:5000/v2/
```

2. Скопируйте все платформы с сохранением проверенного digest (нужен Skopeo).
При любой ошибке остановитесь. Источники и версии сохранены из исходной реализации.

```bash
set -euo pipefail
while read -r source destination; do
  skopeo copy --all --preserve-digests --dest-tls-verify=false \
    "docker://$source" "docker://192.168.56.111:5000/$destination"
done <<'EOF'
docker.io/prom/prometheus@sha256:49214755b6153f90a597adcbff0252cc61069f8ab69ce8411285cd4a560e8038 prom/prometheus:v3.7.3
docker.io/grafana/grafana@sha256:70d9599b186ce287be0d2c5ba9a78acb2e86c1a68c9c41449454d0fc3eeb84e8 grafana/grafana:12.3.0
docker.io/prom/node-exporter@sha256:3ac34ce007accad95afed72149e0d2b927b7e42fd1c866149b945b84737c62c3 prom/node-exporter:v1.10.2
EOF
```

Сверьте исходный и локальный манифест через `skopeo inspect --raw` и
`sha256sum` согласно README. Compose закреплён по этим digest.

3. Сохраните пароль вне Git, не перезаписывая существующий файл.

```bash
export MONITORING_ENV=dev
export NODE_EXPORTER_LISTEN_ADDRESS=$(docker network inspect bridge --format '{{(index .IPAM.Config 0).Gateway}}')
mkdir -p "$HOME/.config/inventory-monitoring"
chmod 700 "$HOME/.config/inventory-monitoring"
if [ ! -e "$HOME/.config/inventory-monitoring/grafana.env" ]; then
  (umask 077; printf 'GRAFANA_ADMIN_PASSWORD=%s\n' "$(openssl rand -hex 24)" > "$HOME/.config/inventory-monitoring/grafana.env")
fi
chmod 600 "$HOME/.config/inventory-monitoring/grafana.env"
docker compose --env-file "$HOME/.config/inventory-monitoring/grafana.env" \
  -f monitoring/docker-compose.yml config --quiet
docker compose --env-file "$HOME/.config/inventory-monitoring/grafana.env" \
  -f monitoring/docker-compose.yml up -d
```

Node Exporter использует host PID/network и корень VM. Он слушает только
адрес Docker bridge, доступный Prometheus через host-gateway; порт 9100
не публикуется на внешнем адресе VM. Сравните MemTotal с `/proc/meminfo`,
число CPU с `getconf _NPROCESSORS_ONLN`, корневую ФС с `df -B1 /`.
Панель использует CPU/RAM/корневую ФС VM.

4. Dev поднимайте штатно: `make setup`, `make build`, `make migrate`, `make up`.
Для Production используйте существующий `deploy/staging-request.sh` от gha-runner
и только реально зарегистрированный успешный выпуск, как описано в README.
Не создавайте запись выпуска ради проверки мониторинга.

5. При переключении остановите предыдущее приложение штатно, сохранив тома,
затем выберите `export MONITORING_ENV=production` (или `dev`) и повторите
команду monitoring `up -d` выше. Поднимите выбранное приложение его штатным путём.
Допустимы только dev/production; неверное значение завершает Prometheus ошибкой.
Том Prometheus сохраняется; label environment различает исторические данные.
В Grafana выберите то же окружение. Отсутствие невыбранного окружения не вызывает alert.
Выбранное окружение без двух реплик вызывает BackendUnavailable спустя минуту.

## Ручная приёмка этапа 1

После запуска приложения подождите два scrape-интервала (30 секунд).

```bash
curl -fsS http://192.168.56.111:9090/-/ready
curl -fsS http://192.168.56.111:3000/api/health
curl -fsS http://192.168.56.111:9090/api/v1/targets
curl -fsSG http://192.168.56.111:9090/api/v1/query \
  --data-urlencode "query=up{job=\"backend\",environment=\"$MONITORING_ENV\"}"
curl -fsSG http://192.168.56.111:9090/api/v1/query \
  --data-urlencode "query=app_readiness{environment=\"$MONITORING_ENV\"}"
curl -fsS http://192.168.56.111:9090/api/v1/alerts
```

Ожидаются готовность Prometheus, Grafana database=ok, две backend-цели
с разными IP/instance, up=1 и app_readiness=1 обеих реплик, node up=1.
BackendUnavailable не должен быть pending/firing при здоровом приложении.
При каждом scrape app_readiness заново проверяет БД; доступный /metrics
с app_readiness=0 вызывает alert независимо от HTTP healthcheck.
Таймаут соединения с БД и ожидания пула ограничен тремя секундами каждый.

Откройте Grafana, выберите environment; проверьте существующие восемь панелей
и добавленную корневую ФС VM. При отсутствии трафика p95 может не иметь данных.
Для предметной метрики в изолированном Dev через реальный API создайте
поступление (201), затем повторите с пустыми items (422). До и после каждой
операции сравните сумму inventory_receipts_created_total по обеим репликам:
успех увеличивает сумму на 1, отказ — на 0. Не используйте рабочую БД.
Не выдавайте unit-тест с подставным роутером за эту проверку.

Повторяемая API-проверка на созданном тестовом стенде (добавляет черновик).
Реквизиты тестового администратора находятся вне Git в файле 0600;
не печатайте его содержимое. Команда выполняется от inv_acc на VM.

```bash
python3 - <<'PY'
import http.cookiejar, json, secrets, subprocess, urllib.request, urllib.error
from pathlib import Path
op = urllib.request.build_opener(urllib.request.ProxyHandler({}),
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
base = 'http://127.0.0.1:8080/api/v1'
csrf = ''
def post(path, body, expected):
    req = urllib.request.Request(base + path, json.dumps(body).encode(),
        {'Content-Type': 'application/json', 'X-CSRF-Token': csrf})
    try:
        r = op.open(req, timeout=10)
    except urllib.error.HTTPError as error:
        r = error
    assert r.code == expected, (path, r.code)
    return json.load(r)
credentials = json.loads((Path.home() / '.config/inventory-monitoring/dev-api.json').read_text())
csrf = post('/auth/login', credentials, 200)['csrf_token']
def first(path):
    return json.load(op.open(base + path))['items'][0]['id']
def count():
    total = 0
    for i in (1, 2):
        text = subprocess.check_output(['docker', 'exec',
            f'inventory-monitoring-apicheck-backend-{i}',
            '/opt/app-root/src/.venv/bin/python', '-c',
            "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/metrics', timeout=10).read().decode())"]).decode()
        total += float(next(x.split()[1] for x in text.splitlines()
            if x.startswith('inventory_receipts_created_total ')))
    return total
body = {'supplier_id': first('/suppliers/'),
    'document_number': 'MON-' + secrets.token_hex(6),
    'received_at': '2026-11-18T20:00:00+00:00',
    'items': [{'material_id': first('/materials/'), 'quantity': '1.000'}]}
before = count()
post('/receipts/', body, 201)
after = count()
body['items'] = []
post('/receipts/', body, 422)
failed = count()
assert after == before + 1 and failed == after
print(before, after, failed, 'OK: 201 -> +1; 422 -> +0')
PY
```

Валидация Prometheus после запуска monitoring:

```bash
docker compose --env-file "$HOME/.config/inventory-monitoring/grafana.env" \
  -f monitoring/docker-compose.yml exec prometheus \
  promtool check config /prometheus/active.yml
docker compose --env-file "$HOME/.config/inventory-monitoring/grafana.env" \
  -f monitoring/docker-compose.yml exec prometheus \
  promtool check rules /prometheus/alerts.yml
```

Ожидается SUCCESS без ошибок. Запуск и проверка конфигурации не подтверждают
сквозной выпуск или учебный инцидент этапа 3.

## Проверка мониторинга

Выполнить из корня репозитория:

    docker compose --env-file "$HOME/.config/inventory-monitoring/grafana.env" \
      -f monitoring/docker-compose.yml ps

    curl -fsS http://192.168.56.111:9090/-/ready
    curl -fsS http://192.168.56.111:3000/api/health
    curl -fsS http://192.168.56.111:9090/api/v1/targets
    curl -fsS http://192.168.56.111:9090/api/v1/alerts

## Диагностика BackendUnavailable

1. Проверить alert и targets в Prometheus.
2. Проверить наличие контейнеров staging:

       docker ps -a --filter label=com.docker.compose.project=inventory-staging

3. Проверить endpoint готовности:

       curl -i --max-time 5 http://192.168.56.111:8081/health/ready

4. Если контейнеры есть, изучить их состояние и журналы.
5. Проверить доступность PostgreSQL и сети Docker.
6. Сопоставить время ошибок с request_id в JSON-журналах.
7. Проверить изменения после последнего развёртывания.

Отсутствие выбранного окружения является проблемой и должно давать alert.
Отсутствие невыбранного окружения игнорируется.

## Восстановление

- Если staging отсутствует, проверить существование
  /opt/actions-runner/staging и сохранённых релизных образов.
- Восстанавливать staging только через штатный проверенный
  механизм CD и с корректными образами.
- Не создавать фиктивные записи о релизе.
- Не удалять Docker volumes, не выполнять docker system prune.
- После восстановления проверить /health/ready, обе реплики
  backend в Prometheus и прекращение срабатывания alert.

## Диагностика производительности

- Трафик: rate(http_requests_total[5m])
- Ошибки: rate(http_requests_total{status_code=~"5.."}[5m])
- p95: histogram_quantile(0.95,
  sum by (le) (rate(http_request_duration_seconds_bucket[5m])))
- Доступность реплик: up{job="backend"}
- Готовность приложения: app_readiness
- Поступления: inventory_receipts_created_total
- Ресурсы: node_cpu_seconds_total,
  node_memory_MemAvailable_bytes, node_filesystem_avail_bytes

При расследовании фиксировать время, симптомы, гипотезу,
использованные метрики и журналы, действия, результат и
предложение по улучшению процесса.

## Безопасность

- Не записывать в логи пароли, токены, тела запросов и query string.
- Не публиковать /metrics через публичный Nginx.
- Пароль Grafana хранить вне Git:
  ~/.config/inventory-monitoring/grafana.env (режим 0600).
- Отключить стандартные access logs Uvicorn.
- Не копировать секреты и содержимое staging.env в отчёт.

## Подтверждённые результаты этапа 1

Проверка после перезапуска VM пользователем, подключение от inv_acc.
Стенд: /home/inv_acc/inventory-monitoring-stage1, отдельный Compose-проект
inventory-monitoring-apicheck и тестовая БД. Существующие Dev/staging-тома
не изменялись. Первоначальный пробный проект inventory-monitoring-devcheck
остановлен штатным make down; его том сохранён.

- Мониторинг Dev и приложение восстановлены штатными Compose up/make up.
  Обе backend-цели backend-dev healthy, up=1, app_readiness=1; node up=1.
  После переключения обратно на Dev активных alerts нет.
- Переключение Dev -> Production -> Dev после перезапуска VM прошло штатно.
  Для выбранного Production без подключённых целей подтверждён firing
  BackendUnavailable с environment=production. История Dev сохранена в томе;
  метки environment и выбор окружения панели разделяют данные.
  Реальный выпуск и откат приложения Production не выполнялись.
- Реальный API через Nginx: повторная команда ручной проверки дала
  0 -> 1 -> 1; успешный POST поступления 201 увеличил счётчик на 1,
  неуспешный POST с пустыми items 422 не изменил его.
- Все три манифеста локального registry сверены по SHA256 с исходными digest.
- Promtool check config/check rules прошли повторно. Шесть синтетических
  сценариев (здоровые реплики, отсутствие целей, одна реплика, scrape down,
  неготовая БД, недоступное невыбранное окружение) прошли повторно.
- Grafana provisioning: девять панелей, запрос каждой возвращает данные.
  CPU=6, RAM=5537943552 байт, корневая ФС=46715187200 байт совпали с VM.
  До перезапуска VM ресурсы были другими; старые значения не выдаются за текущие.
- Prometheus 9090 и Grafana 3000 доступны с клиентского компьютера: HTTP 200,
  Grafana database=ok. Оба сервиса слушают 0.0.0.0. Firewall не менялся;
  при его изменении нужно согласовать доверенные источники доступа.
- Четыре Docker-теста, три Compose-конфигурации, JSON dashboard и
  git diff --check прошли повторно. README/AGENTS/TASK не редактировались агентом.
- Повторные make quality и make container-check прошли (код 0).
  Отчёты quality: reports/20261118t205644z-16084/.
- pip-audit в тестовом образе из uv.lock: известных уязвимостей не найдено;
  локальный пакет inventory-accountment не проверяется по PyPI.
  В старом Windows-окружении отдельно найдены 17 записей уязвимостей
  certifi/filelock/msgpack; оно не полностью синхронизировано с lock.
- Локальный unit-only: 51 passed, один пропуск SIGTERM на Windows,
  покрытие 50,46% ниже 80%. Полный набор на VM ранее дал 80 passed,
  покрытие 84,98%, 160/160 уничтоженных мутантов. Исходная SSH-обёртка
  затем завершилась ошибкой exit; повторный make test завершился кодом 0:
  80 passed (39,91 с), покрытие 84,98%, уничтожены 160/160 мутантов.
  Отчёты: reports/20261118t205308z-5824/; журнал reports-stage1-recheck.log.

## Границы и остающиеся риски

Миграции и предметная модель не менялись. Критические изменения: корневой,
мониторинговый и staging Compose, существующие тесты метрик и Docker.
Перед слиянием нужны независимое одобрение и предусмотренные проверки.
Откат кода — возврат изменённых файлов к предыдущей совместимой ревизии;
тома БД, Prometheus и Grafana сохраняются. Старый Compose без сети не обеспечивает
мониторинг: для совместимого отката используйте текущую сетевую конфигурацию.
Не удаляйте inventory-observability при подключённых backend.

Ранее VM испытывала RCU stall/soft lockup нескольких CPU и процессов;
Docker сообщал об отсутствии exit event и zombie PID Prometheus.
После перезапуска пользователем восстановление и переключение проверены заново.
Причина системных зависаний не установлена; init и увеличение таймаута
не включены как неподтверждённые исправления. Отсутствие повторения при проверке
не доказывает устранение причины. Агент не перезапускал Docker daemon или VM.

Не выполнялись security/verify с полной Git-историей и Trivy, CI, PR,
выпуск Production, живой откат и этапы 2–3. Серверная копия передана без .git;
она не используется как доказательство полного security или релиза.
При пробном некорректном коде единицы API вернул 500
(PydanticSerializationError в обработчике валидации). Это наблюдение для этапа 2;
проверка предметной метрики выполнена с допустимым кодом KG.

## Этап 2: журналы и исправление валидации

Причина найденного HTTP 500: RequestValidationError.errors() содержал
ValueError в ctx. Обработчик пытался сериализовать его в JSON.
Теперь ответ 422 содержит только type/loc/msg, без input и ctx.
Необработанные ошибки преобразуются в 500 на границе HTTP middleware;
тип ошибки и request_id записываются безопасно, без текста исключения
и traceback Uvicorn. HTTP-событие записывается один раз, включая метрики.
Реальный уровень записи для 5xx — ERROR. SQL echo отключён даже при APP_DEBUG,
параметры SQL скрыты: пароли, сессии и тела не должны попадать в SQL-журнал.
В HTTP middleware оставлено локальное обоснованное исключение BLE001:
эта граница обязана обработать неизвестную ошибку без раскрытия traceback.
Конфигурации анализаторов и пороги не менялись; остальные проверки Ruff работают.

Регрессионный барьер — существующий backend/tests/unit/test_observability.py.
До исправления новые проверки дали 3 failed / 6 passed: сериализация ошибки,
повторное выбрасывание исключения с секретом, SQL echo при APP_DEBUG.
Проверяются успешные запросы, 404, 422, 500, обязательные поля HTTP-события,
корреляция с X-Request-ID, неизвестный и параметризованный URL, query string,
Authorization/Cookie, тело, недопустимый request_id и текст исключения.
Тестовая ошибка 500 не добавляет маршрут в штатное приложение.

Повторная диагностика от inv_acc на VM:

```bash
cd /home/inv_acc/inventory-monitoring-stage1
COMPOSE_PROJECT_NAME=inventory-monitoring-apicheck make status
curl -fsS http://127.0.0.1:8080/health/live
curl -fsS http://127.0.0.1:9090/api/v1/alerts
```

Ожидаются здоровые контейнеры, status=ok и пустой список alerts.
Для повторной проверки исправленного запроса (только тестовый Dev):

```bash
python3 - <<'PY'
import http.cookiejar, json, urllib.request, urllib.error
from pathlib import Path
op = urllib.request.build_opener(urllib.request.ProxyHandler({}),
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
base = 'http://127.0.0.1:8080/api/v1'
credentials = json.loads((Path.home()/'.config/inventory-monitoring/dev-api.json').read_text())
r = op.open(urllib.request.Request(base+'/auth/login', json.dumps(credentials).encode(),
    {'Content-Type':'application/json'}), timeout=10)
csrf = json.load(r)['csrf_token']
try:
    op.open(urllib.request.Request(base+'/units/', b'{"code":"INVALID"}',
        {'Content-Type':'application/json', 'X-CSRF-Token':csrf}), timeout=10)
except urllib.error.HTTPError as error:
    assert error.code == 422
    body = json.load(error)
    assert body['code'] == 'validation_error'
    assert all('ctx' not in x and 'input' not in x for x in body['details'])
    print(error.code, error.headers['X-Request-ID'], body['code'])
else:
    raise AssertionError('Ожидался HTTP 422')
PY
```

Ожидается 422, UUID и validation_error. По полученному UUID найдите запись
http_request следующей командой (подставьте UUID из ответа):

```bash
COMPOSE_PROJECT_NAME=inventory-monitoring-apicheck docker compose logs --since=5m backend | grep -F UUID_ИЗ_ОТВЕТА
```
Для регрессионной проверки всех исходов используйте штатные make test и make quality.
Восстановление кода: верните совместимую ревизию, выполните make build и make up
с COMPOSE_PROJECT_NAME=inventory-monitoring-apicheck; том и схема не меняются.
Учитывайте, что откат возвращает исправленные ошибки и риск утечки SQL-параметров.
Не очищайте таблицы и тома ради восстановления журналирования.

Фактические живые проверки этапа 2:

- Через Nginx/API подтверждены 200, 404 и исправленный 422, поля JSON и request_id;
  синтетический секрет не обнаружен в журналах обеих реплик backend.
- В одноразовом контейнере того же backend-образа настоящий Uvicorn обработал
  контролируемое исключение: ответ 500, безопасные события http_request и
  unexpected_http_error, без текста секрета и traceback. БД не использовалась.
- Контрольный синтетический query-маркер в журнале Nginx не обнаружен;
  конфигурация Nginx не менялась. Это ограниченная проверка, не гарантия
  секретности всех внутренних сообщений прокси при любых неисправностях.
- make quality прошёл, отчёты reports/20261118t221801z-169095/.
  pip-audit тестового образа из uv.lock: код 0, известных уязвимостей нет;
  локальный пакет inventory-accountment отсутствует в PyPI и не аудируется.

Это профилактический барьер для реально воспроизведённых дефектов,
но не завершение пункта 14 целиком: учебный инцидент и изменение процесса
по его результатам остаются в отложенном этапе 3. CI, PR и человеческая
приёмка не выполнялись. Критический файл этапа — существующий файл тестов.
Новых файлов, миграций, сервисов и стека сбора журналов не добавлено.

Итог автоматических проверок этапа 2: make test — код 0, 86 passed (38,79 с),
покрытие 84,98%, уничтожены 160/160 мутантов; штатная очистка завершена.
Отчёты: reports/20261118t221629z-164505/, журнал reports-stage2-test.log.
make quality, make container-check, четыре Docker-теста, три Compose-конфигурации,
JSON dashboard, promtool check config/check rules и git diff --check прошли.
Полный security/verify и Trivy не запускались: проверочная копия VM без .git
не подходит для штатной подготовки исходников и проверки полной истории;
на локальном компьютере Docker daemon недоступен. CI и релиз не выполнялись.
Проверка ссылок документации: используются существующие пути/команды;
команда ручной проверки 422 выполнена дословно и прошла.
