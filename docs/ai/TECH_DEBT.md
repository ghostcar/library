# Tech Debt

Долг с impact/priority/owner/trigger. Пустые разделы допустимы.

| # | Описание | Impact | Priority | Owner | Trigger |
|---|----------|--------|----------|-------|---------|
| 1 | Нет lock-файла зависимостей (см. OPEN_QUESTIONS #1) | невоспроизводимые сборки | medium | agent | перед первым Docker-образом |
| 2 | ~~CI отсутствует~~ РЕШЕНО (сессия 7): CI зелёная; чинились: gitignore storage/ (пакет не коммитился), lxml-stubs не в dev deps, миграции не применялись перед integration | — | — | — | — |
| 3 | Дизайн-матрица — начальная редакция: детальный разбор 20+ экранов не выполнен | риск упустить паттерны | low | agent | начало Phase 8 / первого UI-slice |
| 4 | Tailwind-сборка не настроена; минимальный SSR на inline-CSS токенах | UI не масштабируется | medium | agent | первый полноценный экран каталога (Phase 2) |
| 5 | In-memory rate limiter — не работает при нескольких процессах uvicorn | обход лимита при масштабировании | low | agent | запуск >1 процесса web |
| 6 | 45 pytest warnings (httpx per-request cookies, SAWarning в фикстурах) | шум в выводе | low | agent | следующая сессия тестов |
