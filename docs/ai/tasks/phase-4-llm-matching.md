# TaskContext: phase-4-llm-matching

```yaml
task_id: phase-4-llm-matching
goal: "Phase 4: LLM-assisted normalization — digest, строгая JSON schema, OmniRoute adapter, policy engine, кэш proposal, review/corrections, evaluation dataset"
user_value: "Файлы с нестандартными именами разбираются LLM-предложением; пользователь подтверждает или правит; без AI система продолжает работать детерминированно"
scope:
  in:
    - LIBRARY_AI_* конфиг (base_url, api_key, model, timeout, enabled)
    - MatchProposal (строгая schema, Pydantic, одна попытка JSON repair)
    - DigestBuilder (deterministic: filename/parsed/candidates/warnings, БЕЗ текста книги)
    - OmniRouteAdapter (httpx, OpenAI-compatible, без tools, prompt-injection guard)
    - миграция 0005: ai_proposals (кэш по digest+model+versions), ai_corrections (evaluation set)
    - PolicyEngine: auto-apply только при надёжном proposal; иначе review; fallback без AI
    - UI: «Разобрать с LLM» на unmatched, форма proposal с предзаполнением, apply с коррекцией
    - тесты: fake OpenAI-compatible server (ok / битый json / недоступен), кэш, policy
  out:
    - TOC proposal через LLM (после нормализатора-отчётов), fine-tuning, облачная отправка текста книг
invariants:
  - "LLM не изменяет файлы и не вызывает tools (§8)"
  - "текст книги никогда не отправляется в модель"
  - "невалидный ответ -> review/fallback, не падение нормализатора"
  - "недоступный AI -> deterministic fallback"
  - "user correction > proposal > filename heuristic"
  - "кэш: digest_hash + schema_version + prompt_version + model"
relevant_decisions: [ADR-0009]
affected_modules: [modules.library.ai, modules.library.presentation, core.config]
affected_symbols: [MatchProposal, DigestBuilder, OmniRouteAdapter, PolicyEngine, ProposalService]
tests_to_run: [scripts/lint.sh, scripts/test.sh]
risks:
  - "ключ OmniRoute из мастер-промпта невалиден для completions (подтверждено) — нужен валидный ключ от пользователя"
  - "облачные модели: отправляется только digest (имя файла + parsed + кандидаты), не текст книги"
assumptions:
  - "модель по умолчанию ali/qwen-turbo (быстрая, дешёвая, хороший русский); локальная ~4B — при появлении (OPEN_QUESTIONS #2)"
ambiguities: []
plan:
  - "config + schema + digest"
  - "adapter + cache + policy"
  - "UI + routes"
  - "тесты с fake server"
  - "gates + память + push"
checkpoints:
  - "2026-08-25 Phase 4 реализована; 168 tests passed; smoke fallback+ручной apply пройдены"
  - "2026-08-25 live-LLM заблокирован невалидным ключом (OPEN_QUESTIONS #3) — нужен ключ пользователя"
status: done
base_commit: "fcccf18"
```
