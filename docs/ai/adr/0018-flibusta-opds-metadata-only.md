# ADR-0018: Flibusta OPDS metadata-only

Flibusta подключается через существующий OPDS adapter отдельным профилем
`flibusta`. Профиль разрешает наблюдение авторов/серий и уведомления о новых
entries, но capability `acquisition` всегда `false`: worker не скачивает файлы
в фоне. Внешние acquisition-ссылки остаются evidence для ручного действия.

HTML-адаптеры Author.Today/Litnet и любые обходы ограничений остаются
отдельными будущими решениями.
