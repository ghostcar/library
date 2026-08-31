# ADR-0024: Source refresh/observability and Author.Today parser v2

Статус: accepted  
Дата: 2026-08-31

## Контекст

Фоновый опрос был виден только в логах worker, а карточка автора не позволяла
безопасно запросить обновление. Parser Author.Today читал только первую страницу и
только ссылки `/work/`: публичная страница Олега Сапфира показывала 309 публикаций
и 21 цикл, а адаптер возвращал 22 электронных произведения первой страницы.

## Решение

1. Parser v2 обходит объявленную пагинацию последовательно, с allowlist host,
   максимумом 50 страниц, 5 MiB на страницу и 25 MiB суммарно. Identity включает
   тип публикации; поддерживаются `/work/` и `/audiobook/`.
2. Conditional validator первой страницы не сохраняется для многостраничного
   каталога: его `304` не доказывает неизменность остальных страниц.
3. `watch_rules` хранит parser version и последний status/new count/not-modified/
   duration. Смена parser version игнорирует старые validators и выполняет quiet
   baseline без массовых уведомлений.
4. Ручное обновление всегда проходит через PostgreSQL job queue. Owner scope,
   проверка enabled, дедупликация queued/running и минутный cooldown обязательны.
5. `/library/service` показывает только owner-scoped jobs, outbox и watch rules.
   Сырые payload не выводятся; используются только безопасные сокращённые target id.

## Последствия

- Контрольный live fetch возвращает 309 публикаций (185 electronic + 124 audio) и
  21 цикл; сетевой контракт остаётся metadata-only.
- После migration 0014 существующие правила один раз выполнят полный тихий backfill.
- Экран — DB-backed operational view, а не process supervisor: отсутствие heartbeat
  отдельного worker нельзя надёжно заключить только из снимка очереди.
- Полная append-only история каждого poll не добавлена; последние поля правила и
  история jobs покрывают текущую диагностику без новой быстрорастущей таблицы.
