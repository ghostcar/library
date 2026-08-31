# Tech Debt

Долг с impact/priority/owner/trigger. Пустые разделы допустимы.

| # | Описание | Impact | Priority | Owner | Trigger |
|---|----------|--------|----------|-------|---------|
| 1 | ~~Нет lock-файла~~ РЕШЕНО (сессия 11): requirements.lock (pip-compile), Dockerfile ставит из лока, обновление — scripts/update-lock.sh | — | — | — | — |
| 2 | ~~CI отсутствует~~ РЕШЕНО (сессия 7): CI зелёная; чинились: gitignore storage/ (пакет не коммитился), lxml-stubs не в dev deps, миграции не применялись перед integration | — | — | — | — |
| 3 | Дизайн-матрица — начальная редакция: детальный разбор 20+ экранов не выполнен | риск упустить паттерны | low | agent | начало Phase 8 / первого UI-slice |
| 4 | ~~Page templates содержат inline layout styles~~ РЕШЕНО: все layout-правила перенесены в локальный `components.css`; Tailwind осознанно не добавлен поверх работающей token/component системы | — | — | — | — |
| 5 | In-memory rate limiter: ПРИНЯТО — деплой использует 1 web-процесс (compose.prod), лимит корректен. Пересмотреть при горизонтальном масштабировании (общее хранилище). | — | — | — | запуск >1 процесса web |
| 6 | ~~pytest warnings~~ РЕШЕНО (сессия 11): 0 warnings (длинные тестовые JWT-секреты, httpx cookies на клиенте) | — | — | — | — |
| 7 | ~~EPUBCheck live-прогон~~ РЕШЕНО: v5.2.1 запускается внутри развёрнутого worker image `b7351b2` | — | — | — | — |
| 8 | ~~CSP содержит unsafe-inline styles~~ РЕШЕНО: inline styles удалены, `style-src 'self'`, регрессионный тест запрещает возврат `style=` | — | — | — | — |
| 9 | Outbox registry/retry policy реализованы; остаётся подключить реальные внешние consumers и replay UI при появлении интеграций | нет внешних event-driven интеграций | low | agent | первый внешний event consumer |
| 10 | Browser smoke для responsive shell реализован (Chromium, 1280×800 и 390×844). Pixel-by-pixel сверка всех Stitch-экранов остаётся нецелесообразной до стабилизации контента страниц. | возможен локальный visual drift отдельных страниц | low | agent | существенный редизайн страницы |
| 11 | Формальные контракты добавлены; конкретные import/metadata/notification adapters появятся по мере включения соответствующих интеграций | capability registry пока описывает границы, а не все реализации | low | agent | новый внешний адаптер |
| 12 | Pixel-by-pixel сверка Stitch-экранов не выполнялась; shell/navigation теперь покрыты responsive smoke | возможен локальный visual drift отдельных страниц | low | agent | стабилизация контента и эталонных fixtures |
| 13 | Author.Today HTML polling реализован; generic HTML отсутствует. Litnet намеренно не реализуется: соглашение запрещает automated collection (ADR-0020). | остальные разрешённые сайты не опрашиваются автоматически | low | agent | появление разрешённого второго HTML-сайта |
| 14 | ~~SourceLink preferred/priority, CRUD, inheritance и series card отсутствуют~~ РЕШЕНО: migration 0012, owner-scoped service/UI, work→series→author→global | — | — | — | — |
| 15 | ~~Fresh migration/full suite для source schema не подтверждены~~ РЕШЕНО: fresh migration 0012 и 281 tests passed | — | — | — | — |
| 16 | Continuation-link title matching is exact normalized title only; site-specific title cleanup and EPUB extraction are intentionally absent | some candidates need manual review | low | agent | repeated false negatives in real imported books |
| 17 | robots parser for manual continuation-link checking supports applicable `User-agent`/`Disallow` only | unusual robots syntax may conservatively block or need a standards-complete parser | low | agent | real permitted source requires richer rules |
| 18 | Romanized/slit filename conventions are policy-gated review even after bulk AI proposal | some real imports remain `review_ready` until model/user confirms metadata | low | agent | enough real corrections to add a deterministic parser profile |
| 19 | ~~Source polling has no manual refresh/result visibility~~ РЕШЕНО: deduplicated `Проверить сейчас`, last/next/result/duration fields и owner-scoped `/library/service`. Полная временная история проверок намеренно не хранится; история jobs остаётся доступна. | — | — | — | — |
| 20 | Covers remain embedded in original/normalized book files only; no extracted cover storage, HTTP endpoint, catalog rendering, or OPDS image links | catalog is visually incomplete and readers do not receive cover metadata from OPDS | high | agent | next catalog/media slice |
