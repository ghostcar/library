# Open Questions

Только реально открытые вопросы. Закрытые переезжают в DECISIONS/ADR.

| # | Вопрос | Контекст | Приоритет | Создан |
|---|--------|----------|-----------|--------|
| 1 | ЗАКРЫТО 2026-08-26: pip-compile (pip-tools), requirements.lock в репо, Dockerfile ставит из лока. Обновление: scripts/update-lock.sh. | ADR-0005 | — | 2026-08-26 |
| 2 | ЗАКРЫТО 2026-08-26: LIBRARY_AI_MODEL=auto/best-free (auto-роутер бесплатного пула). Валидный JSON на русском, честный requires_review; 429/503 пулов ловятся ретраем. Смена модели — одна строка .env. | ADR-0009/0014 | — | 2026-08-26 |
| 3 | ЗАКРЫТО 2026-08-26: владелец выдал валидный ключ — LLM live работает в проде. | — | — | 2026-08-26 |
| 4 | ЗАКРЫТО 2026-08-26: DNS добавлен, https://library.gorbunovr.ru работает через Cloudflare. | — | — | 2026-08-26 |
| 5 | ЗАКРЫТО 2026-08-26: один агент — атомарные коммиты в main (Conventional Commits), feature-ветки опционально для рискованных задач. | Git workflow | — | 2026-08-26 |
| 9 | ЗАКРЫТО 2026-08-28: выбран публичный HTML metadata-only adapter без auth/private API/content; минимум 30 минут, quiet baseline, ADR-0019. | ADR-0011/0019 | — | 2026-08-26 |
| 10 | ЗАКРЫТО 2026-08-28: Litnet HTML polling не реализуется — пользовательское соглашение прямо запрещает автоматизированный сбор информации. Возврат возможен только с официальным API/RSS или письменным разрешением (ADR-0020). | ADR-0020 | — | 2026-08-26 |
| 11 | ЗАКРЫТО 2026-08-28: preferred хранится на `SourceLink` отдельно для каждой роли; metadata/acquisition разрешаются независимо по цепочке `work > series > author > global`. | source_links, migration 0012 | — | 2026-08-28 |
| 7 | SSO между поддоменами *.gorbunovr.ru и миграция tracker'а на общую auth: общий домен cookie или RS256/JWKS? Решить при появлении второго web-сервиса. | ADR-0006 | low | 2026-08-25 |
| 8 | ЗАКРЫТО 2026-08-26: LIBRARY_AUDIT_RETENTION_DAYS (0 = хранить всегда) + очистка processed outbox (30 дней) в worker'е каждые 6ч. | core/retention.py | — | 2026-08-26 |
| 6 | ЗАКРЫТО 2026-08-26: обе темы реализованы (tokens.css), переключатель «Тема» в шапке (localStorage). Default — Astral (тёмная); сменить default — одна строка в tokens.css/base. | ADR-0004/0013 | — | 2026-08-26 |
| 12 | Какой конкретный сайт станет вторым автоматическим HTML-профилем после Author.Today? Нужны домен/тип страницы, access review и versioned fixtures; до этого generic website хранится только как ссылка. | ADR-0017/0023, TECH_DEBT#13 | medium | 2026-08-31 |
