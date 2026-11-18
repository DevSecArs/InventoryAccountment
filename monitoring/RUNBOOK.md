# Runbook: наблюдаемость InventoryAccountment

## Компоненты

- Prometheus: http://127.0.0.1:9090
- Grafana: http://127.0.0.1:3000
- Node Exporter: внутренний адрес node-exporter:9100
- Backend: /metrics, /health/live, /health/ready
- Dashboard Grafana: InventoryAccountment — наблюдаемость
- Правило Prometheus: BackendUnavailable

Мониторинг запускается отдельным Docker Compose-проектом
inventory-monitoring. Доступ к веб-интерфейсам ограничен
адресом 127.0.0.1 виртуальной машины.

## Проверка мониторинга

Выполнить из корня репозитория:

    docker compose --env-file "$HOME/.config/inventory-monitoring/grafana.env" \
      -f monitoring/docker-compose.yml ps

    curl -fsS http://127.0.0.1:9090/-/ready
    curl -fsS http://127.0.0.1:3000/api/health
    curl -fsS http://127.0.0.1:9090/api/v1/targets
    curl -fsS http://127.0.0.1:9090/api/v1/alerts

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

Не считать отсутствие backend неисправностью мониторинга, если
staging не развёрнут.

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

## Текущее ограничение лабораторной

На 18 ноября 2026 года staging не запущен, каталог состояния CD
отсутствует, а в Registry нет inventory/backend,
inventory/frontend и inventory/db. Alert BackendUnavailable
ожидаемо имеет состояние firing. Полноценную проверку двух реплик
и восстановления приложения требуется выполнить после
воспроизводимого развёртывания.
