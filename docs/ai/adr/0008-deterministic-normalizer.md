# ADR-0008: Детерминированный нормализатор FB2/EPUB (Phase 3)

Статус: accepted
Дата: 2026-08-25

## Контекст

Phase 3 (master prompt §7): безопасный разбор, профиль `prose_compact`, fingerprints, manifest, валидация, идемпотентность. Литературный текст неприкосновенен (§7.1 — главный инвариант).

## Решения

1. **Безопасный разбор**: lxml-парсер с `resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False` — XXE/DTD/сеть исключены. Тест: XXE-сущность в FB2 не разворачивается.

2. **Fingerprints** (версия контракта 1):
   - visible-text: конкатенация видимых текстовых узлов, `\n` между блоками, пробельные серии → один пробел (нормализуется ТОЛЬКО техническое представление переносов; буквы/пунктуация/слова не трогаются). `<binary>` (base64-ресурсы) исключены.
   - structure: скелет тегов+глубина; images: отсортированный (href, sha256, size); chapters: по секциям FB2 / spine-документам EPUB.
   - Инвариант: visible-text до == после, иначе run FAILED, derivative не создаётся.

3. **FB2 (prose_compact)**: удаление всех `<image>` в body и `<binary>` кроме обложки; обложка — единственное изображение из `<coverpage>`; нет coverpage или несколько изображений → run `needs_review` (не молчаливая догадка, §7.4); удаление пустых обёрток (без текстовых узлов и изображений); генерация document-id при отсутствии; section id; заголовки секций (TOC-основа). Сериализация lxml без pretty-print — текстовые узлы не перекодируются.

4. **EPUB (prose_compact)**: repack с `mimetype` первым и STORED; удаление `<img>/<image>/<svg>` из spine-документов (подписи `<figcaption>` — текст, сохраняются); удаление не-image ресурсов вне манифеста (orphans); обложка через `meta name=cover` или `properties="cover-image"`; нет метаданных обложки → review.

5. **Обложка**: только JPEG/PNG перекодируются (безопасные форматы), resize по большей стороне до 1600px (config), LANCZOS, JPEG q85/PNG optimize; upscale запрещён.

6. **Конвейер** (§7.2): received → … → derivative_ready | needs_review | failed. Каждое действие в `run.actions` (JSONB), полный manifest (§7.7) в `run.manifest`: hash до/после, profile+versions, actions, fingerprints, cover, duration, warnings.

7. **Идемпотентность**: unique partial index `(input_asset_id, profile, profile_version, normalizer_version) WHERE state != 'failed'`; повторный request возвращает существующий run. Failed-прогоны не занимают слот — ретрай создаёт новый run.

8. **Failure persistence**: ошибка трансформации фиксируется в транзакции прогона (commit), событие `NormalizationFailed` — отдельной транзакцией, исключение наружу — после commit (иначе откат стирает запись; тот же урок, что с audit в Phase 1).

9. **EPUBCheck**: Java недоступен на VPS → структурная валидация помечается в manifest как skipped (warning); интеграция — при появлении Java/контейнера (TECH_DEBT).

10. **Worker**: обработчик `normalize` (job payload: owner_id, run_id); реестр ORM-моделей `portal.core.database.models` обязателен для импорта в worker'е (FK-резолюция).

## Последствия

- Preferred-файл: `assets.is_preferred` (один на work), «Сделать основным» в UI прогона.
- Download: человекочитаемое имя `Автор — Серия NN — Название.ext` через Content-Disposition (§6.2).
- Review UI: unmatched → привязка к work по UUID; duplicate candidates → «Дубликат»/«Разные» (confirm ставит оригинал preferred, файлы не удаляются).
