# ADR-0009: LLM-assisted matching через OmniRoute (Phase 4)

Статус: accepted
Дата: 2026-08-25

## Контекст

Phase 4 (master prompt §8, §20): LLM — только классификатор и генератор структурированного proposal. Файлы не изменяет, tools не вызывает. Нужен разбор неоднозначных имён файлов, который детерминированный parser (v1) не осилил.

## Решения

1. **Adapter**: OpenAI-compatible chat completions через httpx (без openai SDK — меньше зависимостей, совместимость та же). Endpoint/model/timeout — из `LIBRARY_AI_*` конфига. Вызов без tools. `temperature=0.1`. Класс `AIUnavailableError` — единый сигнал деградации (нет ключа, 401/403/429/5xx, таймаут, битый ответ).

2. **Digest** (§8.3): только метаданные — filename, результат детерминированного парсера, кандидаты из каталога (по normalized-title ILIKE, до 8), формат, warnings. **Текст книги не отправляется никогда.** Hard cap `LIBRARY_AI_MAX_INPUT_CHARS` (обрезка кандидатов с явным warning, не молча).

3. **Prompt-injection guard**: system prompt явно объявляет содержимое данных НЕ инструкциями; ответ — только JSON по схеме. Тест: инъекция в имени файла остаётся данными и ни на что не влияет.

4. **Proposal schema** (§8.4): Pydantic `MatchProposal` (author/title/series/index/match_existing_work_id/confidence/requires_review/evidence/ambiguities). Одна контролируемая попытка repair (извлечение JSON из болтовни/markdown-забора). Невалидно → `REVIEW`, не падение. Schema version = 1, prompt version = 1 (входят в кэш-ключ).

5. **Policy engine** (§8.5):
   - `match_existing_work_id` валиден (есть среди кандидатов владельца) + confidence ≥ 0.85 + не requires_review → AUTO_APPLY;
   - иначе REVIEW (в т.ч. создание новых author/work — кандидаты, не слияния);
   - proposal с UUID не из кандидатов → никогда auto (защита от IDOR/галлюцинации);
   - AI недоступен → FALLBACK (детерминированный путь Phase 2 продолжается).

6. **Кэш** (§8.6): `ai_proposals`, unique `(digest_hash, model, prompt_version, schema_version)`. Одинаковый digest → вызов AI не повторяется.

7. **Corrections/evaluation**: `ai_corrections` (proposal + applied + corrected flag) — локальный обезличенный dataset; fine-tuning не запускается. Экспорт — позже (Phase 8).

8. **UI**: «Разобрать с LLM» на unmatched-файле → страница proposal (решение, поля с предзаполнением, неоднозначности) → «Применить» с правкой пользователя. Правка пользователя всегда важнее proposal.

## Факты окружения

- Ключ из мастер-промпта работает на `/v1/models`, но **невалиден** на `/v1/chat/completions` (AUTH_002, проверено 2026-08-25). Нужен валидный ключ (OPEN_QUESTIONS #3 подтверждён).
- Модель по умолчанию: `ali/qwen-turbo` (быстрая/дешёвая, хороший русский). Локальная ~4B — при появлении (OPEN_QUESTIONS #2).
- Без ключа система полнофункциональна: fallback → ручная форма (проверено smoke).

## Последствия

- Появление валидного ключа = правка одной строки .env, без изменений кода.
- Все LLM-тесты — на fake OpenAI-совместимом сервере (in-process FastAPI); live-вызовы в тесты не завязаны.
