# Защита приёмки на GitHub

Настройки включает владелец репозитория вручную.

## Ветки dev и main

Для обеих веток настроить защиту:

- Require a pull request before merging.
- Require approvals: 1.
- Require review from Code Owners.
- Dismiss stale pull request approvals when new commits are pushed.
- Require conversation resolution.
- Require branches to be up to date before merging.
- Block force pushes and branch deletion.
- Отключить штатные обходы защиты, где доступно.

Убедиться, что @DevSecArs имеет write-доступ.

## Обязательные проверки

Для dev и main после реального выполнения workflow CI выбрать
следующие status checks (точные имена jobs):

- Container security check
- Backend tests and mutation testing
- Code style and typing
- Static security analysis
- Database migrations
- PostgreSQL backup and restore
- Build Docker images

Job Publish Docker images to GHCR не делать обязательным для PR:
он предназначен для публикации образов.

Требовать успешного завершения проверок для актуальной версии PR.
Названия и источник GitHub Actions подтвердить в интерфейсе GitHub.

Обязательный acceptance-policy пока НЕ реализован.
Не добавлять его в Required status checks до надёжной интеграции
и подтверждённого запуска на GitHub.

## Обязательное согласование

Критические файлы в .github/CODEOWNERS закреплены за @DevSecArs.
Для принятия таких изменений необходимо его GitHub Review.

Одобрение @lyna917 не заменяет одобрение @DevSecArs.
PR, созданный самим @DevSecArs, нельзя самостоятельно одобрить.
Этот случай требует отдельного решения владельца проекта.

## Проверка защиты

Проверить через тестовые PR:
1. Обычное корректное изменение.
2. Удаление теста без одобрения.
3. Попытку отключить проверку.
4. Одобрение только от @lyna917.
5. Одобрение @DevSecArs.
6. Новый push после одобрения.

Не удалять реальные тесты в защищённых ветках.

Защита считается включённой только после проверки настроек
и реального поведения Pull Request.

## Ограничения текущей реализации

- Workflow acceptance-policy пока не является обязательной проверкой.
- Нужно проверить доступность pull_request_target в настройках Actions.
- После отправки или отзыва review пока нет гарантированного повторного запуска.
- Необходимо подтвердить привязку статуса к актуальному HEAD PR.
- До решения этих вопросов нельзя утверждать, что named approval защищён CI.
- Нельзя выбирать acceptance-policy как Required status check до живой проверки.

## Текущее состояние реализации

Подготовлено локально:
- CODEOWNERS с обязательным владельцем @DevSecArs для критических файлов.
- Шаблон PR с обоснованием критических изменений.
- Анализатор Git diff и проверка GitHub Reviews.
- Unit-тесты защитной логики.

Не завершено:
- Обязательный status check approval-policy в GitHub Actions.
- Подтверждение применения branch protection для dev и main.
- Реальная демонстрация разрешённого и заблокированного слияния.
- Проверка поведения при отправке и отзыве GitHub Review.

Скрипты сами по себе не обеспечивают блокировку слияния.
CODEOWNERS начнёт требовать ревью после включения соответствующих
правил GitHub и появления файла в целевых ветках.
