# ADR-0011: Source monitoring — OPDS adapter, scheduler, уведомления (Phase 6)

Статус: accepted
Дата: 2026-08-26

## Контекст

Phase 6 (master prompt §9): наблюдение за источниками новых книг. Первая очередь: Author.Today, Litnet, OPDS-каталоги, Flibusta. Требование: сначала исследование официального API/правил доступа; HTML-адаптеры — только с fixtures и без обхода защиты (§9.1, §23).

## Решения

1. **Реализован только OPDS-адаптер** — единственный источник первой очереди со стандартом (OPDS 1.2/Atom). Парсинг safe-parser'ом (XXE-тест), guard на размер (5 МБ), conditional GET (ETag/If-Modified-Since → 304), `parser_version="opds-atom-v1"` хранится с каждым наблюдением. Acquisition=False: ссылки отдаём пользователю, файлы не качаем автоматически.

2. **Author.Today / Litnet / Flibusta — зарегистрированы, отключены** с причинами:
   - Author.Today: есть приватный API с авторизацией; нужен отдельный этап исследования официальных условий (токены, rate limits, допустимость) — OPEN_QUESTIONS #9;
   - Litnet: публичного API нет; HTML-адаптер требует selectors-versioning + fixtures + правовой оценки — OPEN_QUESTIONS #10;
   - Flibusta: официального API нет, доступ ограничен; реализация без отдельного решения владельца не ведётся (§23: не обходить защиту).
   Отключённый адаптер не регистрирует jobs/маршруты; правило с ним создать нельзя.

3. **Watch rules** (`watch_rules`): owner, adapter, name, url, interval (5 мин…24 ч), enabled. Состояние опроса — прямо в правиле: etag, last_modified, last_polled_at, next_poll_at, failure_count, degraded, last_error.

4. **Scheduler**: worker каждые ~30 с вызывает `schedule_due()` — enqueue `poll_watch` для правил с `next_poll_at <= now` (+ резервирование слота на 60 с против двойного enqueue). Обработчик `poll_watch` в worker'е.

5. **Backoff** (§9.3): успех → интервал правила; неудача → 5 мин × 2^(n-1) + jitter 0–60 с, cap 6 ч. `degraded` после 2 подряд неудач + диагностическое уведомление **один раз** на переход. Временная ошибка не удаляет наблюдения.

6. **Observations** (`source_observations`): unique `(watch_rule_id, external_id)` — дедупликация на уровне БД. Уведомление «Новая публикация» может создаваться только при первой вставке (реальный переход, §9.3) и после adapter-specific eligibility filter. Для явно подключённой OPDS-ленты eligible все новые элементы; Author.Today ограничен правилами ADR-0019.

7. **In-app уведомления** (`notifications`): kind (new_release/source_degraded), title/body/data, read_at; страница `/library/notifications`, счётчик непрочитанных в topbar. Telegram/email — будущие адаптеры (§9.4).

## Последствия

- Добавление нового источника = реализовать SourceAdapter + capabilities + descriptor в реестре; правила/scheduler/notifications уже общие.
- Наблюдение ≠ приобретение (§9.2): UI различает «обнаружена публикация» и «файл есть» — файл появляется только через импорт пользователем.
