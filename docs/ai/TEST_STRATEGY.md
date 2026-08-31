# Test Strategy

Слои (мастер-промпт §18):

## Текущее покрытие

- **Unit**: domain-сущности library (инварианты Work/Asset/SourceRecord, series ordering — sort key), config.
- **Integration**: репозитории на PostgreSQL (docker compose, тестовая БД), миграции с чистой схемы.
- **Contract**: source adapter/OPDS serializer и capability registry покрыты unit-тестами.
- **E2E**: HTTP end-to-end через ASGITransport; Chromium browser smoke для desktop/mobile shell.
  Browser toolchain pinned в `package-lock.json` (`playwright@1.62.1`).
- **Security**: upload/XXE/ZIP bomb, owner isolation, OPDS token scope, auth CSRF и library-form CSRF реализованы.
- **Property-based**: PLANNED (Hypothesis: filenames, unicode, series indices — Phase 2/3).

## Правила

- Тесты не используют пользовательские книги; только синтетические/public-domain fixtures.
- Интеграционные тесты требуют PostgreSQL: `compose.test.yaml` / тестовая БД, создаётся перед прогоном, рушится после.
- Quality gates перед каждым коммитом: `ruff check`, `mypy`, `pytest`.

## Команды

```bash
scripts/test.sh          # unit + integration
scripts/lint.sh          # ruff + mypy
scripts/test-browser.sh  # responsive shell в локальном Chromium/Playwright
```

## Последний release gate

- 2026-08-31, guided source package + searchable import assignment:
  `scripts/test.sh` — **294 passed**, включая fresh migration до schema `0013`.
- `scripts/lint.sh` — Ruff check/format и mypy по 113 source-файлам — green.
- `scripts/test-browser.sh` — Chromium desktop 1280×800 и mobile 390×844 — green.
- Import integration — **14 passed**; picker проверен через HTTP от поиска по
  циклу до фактической привязки asset/import item к owner-scoped work.
- Source integration — **4 passed** после замены series reconciliation select:
  HTTP-поиск и подтверждение existing work входят в onboarding E2E.
- Устранён drift migration test (`0012` → фактический `0013` +
  `continuation_link_candidates`); семь ранее закоммиченных файлов механически
  приведены к текущему Ruff formatter.
