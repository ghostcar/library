# TaskContext: phase-2-catalog-import

```yaml
task_id: phase-2-catalog-import
goal: "Phase 2: импорт FB2/EPUB (upload + локальные каталоги с dry-run), fingerprints, duplicate candidates, каталог с UI"
user_value: "Книги можно загрузить и увидеть в каталоге; дубликаты не плодятся, а фиксируются как кандидаты на разбор"
scope:
  in:
    - домен: ImportBatch, ImportItem, DuplicateCandidate (+ состояния)
    - детекция формата по содержимому (FB2 XML namespace / EPUB zip mimetype)
    - deterministic filename parser: "Автор — Серия 04 — Название.fb2"
    - ImportService: quarantine → format detect → sha256 → dedup → asset(original) → match → события
    - matching: по нормализованному автору/названию; evidence в import_item.match_evidence; неоднозначное — unmatched
    - duplicate_candidates: exact (sha256) и per-work+format
    - scan локальных каталогов (LIBRARY_IMPORT_ROOTS) c dry-run и apply
    - миграция 0003 + assets.work_id
    - UI: /library/import (upload+inbox), /library/catalog, /library/works/{id}; HTMX
    - лимиты: размер файла, число файлов, quarantine first
  out:
    - watched inbox (нужен scheduler — с Phase 6), нормализатор (Phase 3), LLM-matching (Phase 4)
    - OPDS, чтение файлов книг, изменение текста
invariants:
  - "оригинал неизменен: только сохранение, без модификаций"
  - "MIME/формат по содержимому, не по расширению"
  - "дубликат не удаляется и не молча пропускается — фиксируется кандидат"
  - "весь импорт в quarantine до успешной валидации"
  - "owner scope на каждом шаге"
relevant_decisions: [ADR-0001, ADR-0006, ADR-0007]
affected_modules: [modules.library, core.storage, web]
affected_symbols: [ImportService, parse_filename, detect_format, DuplicateCandidateRepository]
tests_to_run: [scripts/lint.sh, scripts/test.sh]
risks:
  - "filename parser детерминированный: покрывает типовые шаблоны, остальное — unmatched (LLM в Phase 4)"
  - "EPUB = zip: проверка zip bomb при детекции (только mimetype entry читается, лимит записей)"
assumptions:
  - "типовой шаблон файлов пользователя: Автор — Серия NN — Название.ext"
ambiguities: []
plan:
  - "домен + parser + detection"
  - "ImportService + storage"
  - "миграция 0003"
  - "API/UI"
  - "тесты + gates"
  - "память + push"
checkpoints:
  - "2026-08-25 импортный конвейер + каталог UI реализованы; 126 tests passed; smoke пройден"
  - "2026-08-25 исправлен ключевой баг reuse Work в CatalogService (title+авторы)"
status: done
base_commit: "ff5f544"
```
