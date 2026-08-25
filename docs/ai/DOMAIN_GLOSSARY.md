# Domain Glossary

Единые термины (мастер-промпт §5). Русские соответствия — для документации, в коде — английские.

| Термин | Русский | Определение |
|--------|---------|-------------|
| Work | Произведение | Каноническое произведение независимо от сайта и файла. UUID. |
| Author | Автор | Каноническая персона/псевдоним. |
| AuthorAlias | Псевдоним автора | Альтернативное написание имени. |
| Series | Цикл/серия | Упорядоченная группа произведений. |
| SeriesMembership | Принадлежность циклу | Work ↔ Series с raw index, нормализованным sort key и типом (main/side/prequel/collection/unknown). |
| SourceRecord | Запись источника | Конкретная страница/ID произведения на внешнем сайте. Не каноническая истина. |
| SourceAuthorRecord | Запись автора источника | Аналогично для автора. |
| Asset | Файл | Физический файл с форматом; адресуется SHA-256 содержимого. |
| AssetRelation | Связь файлов | original / normalized / converted / duplicate-of. |
| Original | Оригинал | Первый импортированный Asset произведения; неизменяем. |
| Derivative | Производный файл | Результат нормализации; связан с оригиналом через AssetRelation. |
| ReadingState | Состояние чтения | unread/reading/read/paused/abandoned + дата, прогресс, источник изменения. |
| SeriesReadingState | Состояние цикла | Derived snapshot: last_read, last_owned, last_observed, next_available_unread, missing_indices, has_new_release, series_status, completion_confidence. |
| WatchRule | Правило наблюдения | Что и где отслеживать (автор/серия/произведение/URL). |
| Observation | Наблюдение | Результат одного опроса источника. |
| Acquisition | Получение | Попытка и результат получения файла. |
| ImportBatch / ImportItem | Партия импорта | Группа файлов, импортированных одной операцией. |
| DuplicateCandidate | Кандидат в дубликаты | Предположение о совпадении; требует подтверждения, не удаляется автоматически. |
| NormalizationProfile | Профиль нормализации | metadata_only / safe / prose_compact / reader_neutral / manual_cleanup. |
| NormalizationRun | Запуск нормализации | Конвейер состояний received→…→preferred_or_review. |
| TransformationManifest | Манифест преобразования | Полная объяснимая запись: hash, версии, действия, fingerprints. |
| ContentFingerprint | Отпечаток контента | SHA-256 + visible-text fingerprint + structure fingerprint. |
| Job | Задача | Элемент PostgreSQL-backed очереди. |
| OutboxEvent | Событие outbox | Transactional outbox, идемпотентные обработчики. |
| owner_id | Владелец | Обязательное поле всех пользовательских данных. |

## Ключевые инварианты

1. Work ≠ SourceRecord ≠ Asset — никогда не смешивать (§5).
2. Внешний ID уникален в паре `adapter_id + external_id`.
3. Asset адресуется SHA-256; человекочитаемое имя — только при отдаче (Content-Disposition).
4. Номер книги в серии: raw string + отдельный нормализованный sort key.
5. Пользовательское подтверждение > вывод LLM > источник.
