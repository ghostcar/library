# ADR-0012: OPDS 1.2 delivery для FBReader (Phase 7)

Статус: accepted
Дата: 2026-08-26

## Решения

1. **OPDS 1.2** (максимальная совместимость с FBReader). Сериализатор — отдельный модуль `presentation/opds/serializer.py` (чистые функции dict→Atom XML): OPDS 2.0 добавляется без изменений domain/application.

2. **Аутентификация читалки**: HTTP Basic, где **пароль = device token** (pdt_…), логин информационный; Bearer тоже принимается. Токены: scope `library:opds:read`, отзыв, показ один раз при создании. Основной JWT устройством не принимается (тест). 401 всегда с WWW-Authenticate.

3. **Каталог**: root-навигация → Новые, Непрочитанные, Циклы, Авторы, Новые продолжения (наблюдения источников). OpenSearch-описание `/opds/search.xml` + поиск `/opds/search?q=` по title/author (normalized ILIKE). Жанры/теги — когда появятся теги в схеме.

4. **Acquisition links**: `/opds/download/{asset_id}` — owner-scoped, человекочитаемое имя через Content-Disposition (§6.2). Приоритет файла: is_preferred → normalized → original (§10.1 «нормализованные preferred assets»).

5. **Наблюдения в каталоге**: `/opds/observations` показывает найденные в лентах книги (не купленные/не скачанные) со ссылкой на источник (rel=related) — UI-различие «обнаружена» vs «файл есть» (§9.2).

6. **UI OPDS-доступа**: `/library/opds-settings` — создать токен (показ один раз, не через redirect), список, отзыв. Инструкция подключения в интерфейсе.

## Ограничения
- Обложки в фидах не отдаются (thumbnails) — добавим с ImageResource (Phase 8).
- FBReader smoke — ручной шаг пользователя (curl-проверки структуры/XML/auth пройдены).
