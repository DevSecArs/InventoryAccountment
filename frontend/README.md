# Веб-интерфейс InventoryAccountment

React/TypeScript-интерфейс системы складского учёта. Реальные CRUD-операции
доступны для единиц измерения, материалов и поставщиков. Разделы поступлений,
отчётов и администрирования отображают целевую структуру и явно отмечают
отсутствующие backend API без фиктивного сохранения.

## Требования

- Node.js `^20.19.0` или `>=22.12.0`;
- pnpm `11.19.0` через Corepack или отдельную установку;
- HTTP API на `http://127.0.0.1:8000`.

## Установка и запуск

```powershell
cd frontend
corepack pnpm install --frozen-lockfile
corepack pnpm dev
```

Откройте `http://127.0.0.1:5173`. Dev-сервер проксирует `/api` и `/health` на
`http://127.0.0.1:8000`, поэтому отдельная настройка CORS для локального
запуска не требуется.

Если backend опубликован по другому адресу, создайте локальный `.env` из
`.env.example` и задайте `VITE_API_BASE_URL`. Не помещайте в `VITE_*` секреты:
значения встраиваются в браузерную сборку.

## Проверки

```powershell
corepack pnpm typecheck
corepack pnpm test:run
corepack pnpm build
```

Команда `corepack pnpm quality` объединяет проверку типов и тесты. Результат
production-сборки помещается в игнорируемый каталог `dist/`.

## Production

Production-сборку следует раздавать через Nginx на том же origin, что и API,
проксируя `/api` и `/health` в FastAPI. Если используются разные origin,
backend должен явно разрешать нужный origin и корректно настраивать HTTPS,
cookie и CORS; обход ограничений браузера запрещён.
