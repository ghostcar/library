# Test Strategy

Слои (мастер-промпт §18):

## Текущее покрытие

- **Unit**: domain-сущности library (инварианты Work/Asset/SourceRecord, series ordering — sort key), config.
- **Integration**: репозитории на PostgreSQL (docker compose, тестовая БД), миграции с чистой схемы.
- **Contract**: PLANNED (с появлением адаптеров, Phase 6).
- **E2E**: PLANNED (Playwright, Phase 8).
- **Security**: PLANNED (Phase 2+: upload/XXE/ZIP bomb; Phase 7: OPDS tokens).
- **Property-based**: PLANNED (Hypothesis: filenames, unicode, series indices — Phase 2/3).

## Правила

- Тесты не используют пользовательские книги; только синтетические/public-domain fixtures.
- Интеграционные тесты требуют PostgreSQL: `compose.test.yaml` / тестовая БД, создаётся перед прогоном, рушится после.
- Quality gates перед каждым коммитом: `ruff check`, `mypy`, `pytest`.

## Команды

```bash
scripts/test.sh          # unit + integration
scripts/lint.sh          # ruff + mypy
```
