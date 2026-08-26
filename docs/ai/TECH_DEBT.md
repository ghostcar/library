# Tech Debt

Долг с impact/priority/owner/trigger. Пустые разделы допустимы.

| # | Описание | Impact | Priority | Owner | Trigger |
|---|----------|--------|----------|-------|---------|
| 1 | ~~Нет lock-файла~~ РЕШЕНО (сессия 11): requirements.lock (pip-compile), Dockerfile ставит из лока, обновление — scripts/update-lock.sh | — | — | — | — |
| 2 | ~~CI отсутствует~~ РЕШЕНО (сессия 7): CI зелёная; чинились: gitignore storage/ (пакет не коммитился), lxml-stubs не в dev deps, миграции не применялись перед integration | — | — | — | — |
| 3 | Дизайн-матрица — начальная редакция: детальный разбор 20+ экранов не выполнен | риск упустить паттерны | low | agent | начало Phase 8 / первого UI-slice |
| 4 | Tailwind-сборка не настроена; минимальный SSR на inline-CSS токенах | UI не масштабируется | medium | agent | первый полноценный экран каталога (Phase 2) |
| 5 | In-memory rate limiter: ПРИНЯТО — деплой использует 1 web-процесс (compose.prod), лимит корректен. Пересмотреть при горизонтальном масштабировании (общее хранилище). | — | — | — | запуск >1 процесса web |
| 6 | ~~pytest warnings~~ РЕШЕНО (сессия 11): 0 warnings (длинные тестовые JWT-секреты, httpx cookies на клиенте) | — | — | — | — |
| 7 | EPUBCheck: интегрирован (jar в Docker-образе, pinned 5.2.1, вызов после EPUB-трансформации); вне образа — skipped в manifest. Осталось: live-прогон на реальном деплое. | low | agent | первый деплой | 
| 8 | CSP содержит unsafe-inline styles (шаблоны используют style-атрибуты) | снижение пользы CSP | low | agent | перенос стилей в components.css |
