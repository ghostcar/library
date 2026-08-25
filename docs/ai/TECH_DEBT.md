# Tech Debt

Долг с impact/priority/owner/trigger. Пустые разделы допустимы.

| # | Описание | Impact | Priority | Owner | Trigger |
|---|----------|--------|----------|-------|---------|
| 1 | Нет lock-файла зависимостей (см. OPEN_QUESTIONS #1) | невоспроизводимые сборки | medium | agent | перед первым Docker-образом |
| 2 | CI (GitHub Actions) отсутствует до первого push | quality gates только локально | medium | agent | первый push |
| 3 | Дизайн-матрица — начальная редакция: детальный разбор 20+ экранов не выполнен | риск упустить паттерны | low | agent | начало Phase 8 / первого UI-slice |
| 4 | Tailwind-сборка не настроена (UI ещё нет) | — | low | agent | первый HTML-шаблон |
