# ADR-0007: Импортный конвейер и детерминистический matching

Статус: accepted
Дата: 2026-08-25

## Контекст

Phase 2 (master prompt §6, §20): импорт FB2/EPUB, fingerprints, дубликаты, каталог.

## Решения

1. **Конвейер файла** (§6.3): `quarantine/<batch-id>/` → детекция формата по содержимому (FB2: FictionBook namespace в первых 8КБ; EPUB: ZIP + `mimetype` entry == `application/epub+zip`, guard на число записей) → SHA-256 → exact-duplicate check → `originals/<sha2>/<sha>.<ext>` (content-addressed, immutable) → deterministic match → события `BookFileImported`/`WorkMatched`/`DuplicateSuspected` в outbox.

2. **Filename parser детерминированный** (v1): шаблон `Автор — Серия NN — Название.ext` (em/en dash, hyphen; подчёркивания = пробелы; индексы `04`, `0.5`, `2-3`). LLM-разбор неоднозначностей — Phase 4 (§8.1). Well-formed (автор+название) → auto-apply; иначе item остаётся `stored_unmatched` для разбора.

3. **Политика reuse** (§8.5): при register_work переиспользуются author (normalized name), series (normalized title) и **work — только при совпадении normalized title И пересечении авторов** (одинаковое название у разных книг — не повод сливать).

4. **Дубликаты**:
   - exact content (тот же SHA-256) → новый asset НЕ создаётся, item = `duplicate` с evidence;
   - тот же work+формат, другой контент → asset сохраняется + `duplicate_candidates` (pending, review в Phase 3);
   - ничего не удаляется и не сливается молча (§2.3).

5. **Связь asset→work**: `assets.work_id` (nullable FK SET NULL) — файл может быть не привязан до разбора.

6. **Локальные каталоги**: только явно разрешённые корни (`LIBRARY_IMPORT_ROOTS`, comma-separated), dry-run по умолчанию (verdict new/duplicate), apply — отдельным действием. Сторонние расширения игнорируются. Watched inbox — с появлением scheduler (Phase 6).

7. **Лимиты**: max_file_mb=50, max_files_per_batch=20 (config); имя файла из upload нормализуется до basename (path traversal).

## Последствия

- Импорт идемпотентен по контенту: повторная загрузка того же файла безопасна.
- Review-UI для unmatched/duplicate_candidates — Phase 3 вместе с нормализатором.
- Текстовые fingerprints (visible-text) появятся в Phase 3; сейчас fingerprint = SHA-256 контента.
