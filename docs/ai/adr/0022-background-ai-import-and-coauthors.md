# ADR-0022: Background AI import and ordered co-authors

Статус: accepted  
Дата: 2026-08-31

## Контекст

Новые unmatched imports требовали отдельного ручного POST для каждого файла.
Повторная попытка могла получить 500 из-за гонки cache insert по уникальному
`ai_proposals` key. Контракт LLM и review form содержали только singular author,
хотя каталог поддерживает несколько `WorkAuthor`.

## Решение

1. Каждый новый `stored_unmatched` import enqueues `propose_import` в PostgreSQL
   worker queue после записи item. Upload не ждёт OmniRoute. Для уже существующих
   unmatched items import inbox предоставляет одну операцию `Разобрать всё`; она
   ставит в очередь только записи без `ai_status`.
2. Worker получает proposal, применяет его только при существующем policy
   `AUTO_APPLY`; все uncertain/invalid/unavailable ответы сохраняются как
   `review_ready`/`unavailable` evidence. Каталог не меняется без policy gate.
3. Cache write использует PostgreSQL `ON CONFLICT DO NOTHING`: одинаковый
   digest/model/version идемпотентен при повторе или конкурентном запросе.
4. Proposal accepts ordered `authors: list[str]`; legacy `author` остаётся
   читаемым для старого cache/API. Review form принимает имена через запятую и
   передаёт список в `CatalogService`, который создаёт отдельные WorkAuthor links.

## Последствия

- Массовый импорт сразу запускает разбор в фоне; пользователь открывает уже
  подготовленный результат, а не запускает LLM для каждой строки.
- Низкая уверенность по-прежнему требует review, особенно для слитых/romanized
  имён файлов; автоматическое создание ошибочной книги не допускается.
