# ADR-0010: Производное состояние циклов и чтение (Phase 5)

Статус: accepted
Дата: 2026-08-25

## Решения

1. **DerivedSeriesState** вычисляется on-read (не хранится): entries сортируются по (index_sort NULLs last, title); `last_read` — последняя прочитанная по порядку; `next_available_unread` — первая непрочитанная после последней прочитанной (abandoned пропускаются); `missing_indices` — гэпы между ЦЕЛОЧИСЛЕННЫМИ индексами (дробные/диапазоны/unknown не участвуют).

2. **series_status**: derived (planned/in_progress/caught_up/abandoned) + user override из `series_user_states` (paused/abandoned/completed/planned). Override всегда выигрывает. **Все книги прочитаны = `caught_up`, НЕ completed** (§5.3: максимальный номер не конец серии). `completed` ставится только пользователем вручную → completion_confidence=high; иначе low (medium появится с наблюдениями источников, Phase 6).

3. **Переходы статусов чтения**: `unread → read` разрешён напрямую — «Отметить прочитанной» это главная мобильная кнопка (§10.2); доменная карта переходов обновлена (было unread→{reading}).

4. **История**: `reading_state_history` — строка на каждый переход (from/to/source/at); страница истории у произведения.

5. **Очередь чтения**: сначала next из in_progress-циклов, затем первые книги planned-циклов, затем standalone unread. Порядок = порядок чтения.

6. **События**: BookMarkedRead / SeriesProgressChanged → outbox (Phase 6 подпишет наблюдения).

7. **Dashboard** (`/library/`): «Продолжить чтение» (status=reading), «Дальше в циклах» (top очереди), «Недавно добавленные». Mobile-first: одна колонка, крупные кнопки, touch-target 44px.

## Последствия
- Пересчёт состояния O(1 запрос на серию) — при росте каталога можно кэшировать, пока не нужно.
- Bulk «отметить выбранные прочитанными» на странице цикла.
