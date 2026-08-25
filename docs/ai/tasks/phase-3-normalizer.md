# TaskContext: phase-3-normalizer

```yaml
task_id: phase-3-normalizer
goal: "Phase 3: детерминированный нормализатор FB2/EPUB (prose_compact), fingerprints-инвариант текста, manifest, review UI, идемпотентность"
user_value: "Книги нормализуются в фоне: компактный формат с одной обложкой и рабочим оглавлением, текст доказуемо не изменён"
scope:
  in: [FB2/EPUB transformers, fingerprints, cover optimizer, NormalizationService, migration 0004, worker handler, normalization UI, download, review UI]
  out: [LLM-этап (Phase 4), EPUBCheck (нет Java), Calibre ebook-polish, watched inbox]
invariants:
  - "литературный текст не изменяется (visible-text fingerprint до==после)"
  - "derivative при нарушении инварианта не создаётся"
  - "оригиналы неизменны"
  - "неоднозначная обложка -> needs_review, не молчаливая догадка"
relevant_decisions: [ADR-0008]
affected_modules: [modules.library.normalizer, modules.library.application, web, core.jobs]
tests_to_run: [scripts/lint.sh, scripts/test.sh]
risks: []
assumptions: []
ambiguities: []
plan: []
checkpoints:
  - "2026-08-25 нормализатор реализован; 146 tests passed; smoke через реального воркера пройден"
status: done
base_commit: "336d109"
```

## Checkpoints

- 2026-08-25: все гейты зелёные; smoke: upload → normalize (worker) → derivative_ready → download (Content-Disposition) → prefer.
