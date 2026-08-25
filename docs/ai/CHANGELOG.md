# CHANGELOG — изменения пользовательского поведения

Формат: дата, что изменилось для пользователя.

## 2026-08-25

- Создан проект (greenfield): ядро портала (config, database, module registry, health endpoint) и доменное ядро библиотеки (канонические сущности Work/Author/Series/SourceRecord/Asset, миграция, репозитории).
- Пользовательского UI пока нет; API: `GET /healthz`, `GET /library/` (заглушка).

## 2026-08-25 (сессия 2)

- Появилась единая авторизация портала: страница входа, регистрация первого владельца (bootstrap), защищённая страница библиотеки, выход.
- API: /auth/register|login|refresh|logout|me|tokens (device-токены для будущих читалок).
- Все чувствительные действия пишутся в audit_log; login/register ограничены rate limit'ом.
