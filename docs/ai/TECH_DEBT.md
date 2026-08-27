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
| 7 | EPUBCheck: интегрирован (jar в Docker-образе, pinned 5.2.1, вызов после EPUB-трансформации); вне образа — skipped в manifest. Осталось: live-прогон на реальном деплое. | low | agent | первый деплой | 
| 8 | ~~CSP содержит unsafe-inline styles~~ РЕШЕНО: inline styles удалены, `style-src 'self'`, регрессионный тест запрещает возврат `style=` | — | — | — | — |
| 9 | Outbox dispatcher пока имеет logging sink; внешним consumers нужен typed handler registry и retry policy | нет внешних event-driven интеграций | medium | agent | первый внешний event consumer |
| 10 | Browser smoke для responsive shell реализован (Chromium, 1280×800 и 390×844). Pixel-by-pixel сверка всех Stitch-экранов остаётся нецелесообразной до стабилизации контента страниц. | возможен локальный visual drift отдельных страниц | low | agent | существенный редизайн страницы |
