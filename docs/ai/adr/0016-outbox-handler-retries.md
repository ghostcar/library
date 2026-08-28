# ADR-0016: Typed outbox registry and bounded retries

Статус: accepted
Дата: 2026-08-28

## Решение

- Outbox consumers регистрируются явно по `event_type` через worker registry.
- Неизвестное событие не подтверждается как processed.
- Ошибка consumer увеличивает `attempts` и возвращает событие в `pending` с
  exponential backoff (2, 4, 8, 16 секунд; максимум 1 час).
- После пяти попыток событие получает terminal `failed`, сохраняя `last_error`.
- Планирование retry хранится в PostgreSQL (`next_attempt_at`, migration 0009),
  поэтому рестарт worker не сбрасывает policy.
- До появления внешних consumers зарегистрирован идемпотентный observer/logging
  handler для известных доменных событий.

## Последствия

Сбой временного consumer больше не теряет событие и не создаёт tight loop;
внешние интеграции подключаются отдельной регистрацией без изменения dispatcher.
Terminal failed-события требуют будущего UI/операционного replay-инструмента.
