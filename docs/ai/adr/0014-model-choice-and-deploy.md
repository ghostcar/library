# ADR-0014: Модель auto/best-free и деплой в GHCR

Статус: accepted
Дата: 2026-08-26

## Решения

1. **LIBRARY_AI_MODEL=auto/best-free** — auto-роутер бесплатного пула шлюза:
   валидный JSON на русском, честный `requires_review`/confidence (слабый
   разбор → review, не выдумывает автора). 429/503 бесплатных пулов
   обрабатываются: один ретрай с паузой 3с (cold starts, session 12), 429/key-ошибки —
   сразу fallback. Смена модели — одна строка .env, код не привязан.

2. **Базовый URL**: `https://llm.gorbunovr.ru/v1` явно (шлюз принимает
   и без /v1, но фиксируем канонический).

3. **Адаптер**: `stream: false` явно (часть моделей шлюза стримит по умолчанию).

4. **GHCR**: образы ghcr.io/ghostcar/library:<git-sha> + latest; токен gh
   с write:packages (gh auth refresh), docker login ghcr.io. Публикация —
   по явной команде владельца (выполнено 2026-08-26).

5. **Wheel**: шаблоны и static включены через package-data; миграции и
   alembic.ini копируются в /app (для exec-web миграций).

## Инцидент деплоя (для памяти)
- StaticFiles падал: templates/static не входили в wheel → package-data.
- Локальный резолвер VPS кэшировал negative DNS → внешний smoke через
  `curl --resolve`.
- Первый restore оборвался сам (psql | head SIGPIPE) — повторить полностью.
