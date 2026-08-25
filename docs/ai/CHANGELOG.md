# CHANGELOG — изменения пользовательского поведения

Формат: дата, что изменилось для пользователя.

## 2026-08-25

- Создан проект (greenfield): ядро портала (config, database, module registry, health endpoint) и доменное ядро библиотеки (канонические сущности Work/Author/Series/SourceRecord/Asset, миграция, репозитории).
- Пользовательского UI пока нет; API: `GET /healthz`, `GET /library/` (заглушка).
