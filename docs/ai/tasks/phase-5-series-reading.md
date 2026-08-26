# TaskContext: phase-5-series-reading

```yaml
task_id: phase-5-series-reading
goal: "Phase 5: производное состояние циклов (last_read/next/missing/status), быстрые действия чтения, очередь, dashboard"
user_value: "Видно, где я остановился в каждом цикле и что читать следующим; отметка прочитанной — одной кнопкой с телефона"
scope:
  in:
    - SeriesStateService: сортировка по index_sort, last_read, next_available_unread, missing_indices, series_status (derived) + user override, completion_confidence
    - ReadingStateService: переходы статусов с историей, массовая отметка, события BookMarkedRead/SeriesProgressChanged
    - миграция 0006: reading_state_history, series_user_states
    - UI mobile-first: dashboard (продолжить/далее в циклах/недавние), страница серии (таймлайн), очередь чтения
    - действия: начал/прочитал/пауза/бросил/вернуть в очередь
  out:
    - OPDS-категории (Phase 7), has_new_release (Phase 6 — наблюдения источников), PWA manifest
invariants:
  - "максимальный номер НЕ считается концом серии (§5.3)"
  - "user override статуса серии важнее derived"
  - "переходы статусов валидируются доменом (незаконные отклоняются)"
  - "история изменений пишется на каждый переход"
relevant_decisions: [ADR-0010]
affected_modules: [modules.library, web]
affected_symbols: [SeriesStateService, ReadingStateService, DerivedSeriesState]
tests_to_run: [scripts/lint.sh, scripts/test.sh]
risks:
  - "missing_indices только для числовых индексов; диапазоны/сборники не участвуют в gap-детекции"
assumptions: []
ambiguities: []
plan:
  - "миграция + домен сервисов"
  - "UI"
  - "тесты"
  - "gates + память + push"
checkpoints: []
status: in_progress
base_commit: "23330dc"
```

## Checkpoints

- 2026-08-25: Phase 5 реализована; 199 tests passed; smoke пройден (3 тома → прочитан том 01 → dashboard показывает том 02 как следующий).
- status: done
