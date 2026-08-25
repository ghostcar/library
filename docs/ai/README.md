# docs/ai — память проекта

Канонический корень проектной памяти. Порядок чтения и обновления обязателен для любого агента.

## Порядок чтения (pre-fetch)

1. `../AGENTS.md` (корневой)
2. `MEMORY_MANIFEST.yaml` — схема и обязательные документы
3. `STATUS.md` — что фактически реализовано
4. `PROJECT_CONTEXT.md` — цель, ограничения, non-goals
5. `DECISIONS.md` + `adr/` — принятые решения
6. `OPEN_QUESTIONS.md`, `TECH_DEBT.md`
7. `ARCHITECTURE_MAP.md`, `DOMAIN_GLOSSARY.md` — по необходимости
8. `tasks/` — активные TaskContext

## Порядок обновления (закрытие задачи)

1. `STATUS.md` — фактическое состояние
2. `DECISIONS.md` + новый ADR (если решение архитектурное)
3. `OPEN_QUESTIONS.md`, `TECH_DEBT.md`
4. `SESSIONS.md` — краткая запись о сессии (факты, без chain-of-thought)
5. `CHANGELOG.md` — если изменилось пользовательское поведение
6. `ARCHITECTURE_MAP.md` — если изменились связи модулей
7. `tasks/<task-id>.md` — закрыть фактическими результатами

## Правила

- Память содержит проверяемые факты и решения, не chain-of-thought.
- Код — источник истины реализации; ADR — источник намерения. Расхождение = drift, фиксируется явно.
- Тривиальная правка: агент отмечает `reviewed-no-change` в TaskContext, полный обход документов не требуется.

## Структура

```text
docs/ai/
  README.md            — этот файл
  MEMORY_MANIFEST.yaml — machine-readable манифест памяти
  PROJECT_CONTEXT.md
  STATUS.md
  ARCHITECTURE_MAP.md
  DOMAIN_GLOSSARY.md
  DECISIONS.md
  OPEN_QUESTIONS.md
  TECH_DEBT.md
  CHANGELOG.md
  SESSIONS.md
  TEST_STRATEGY.md
  DEPLOYMENT_STATE.md
  DESIGN_CONTEXT.md
  MCP_INVENTORY.md
  adr/                 — архитектурные решения
  tasks/               — TaskContext задач
  runbooks/            — операционные процедуры
  schemas/             — машинно читаемые схемы
```
