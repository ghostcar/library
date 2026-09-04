# ADR-0025: Canonical series tracking and bounded coauthor propagation

Статус: accepted  
Дата: 2026-09-01

## Контекст

Guided onboarding считал цикл подключённым только тогда, когда его direct
`SourceLink` указывал на endpoint открытой карточки автора. Для совместного цикла
это давало неверный UX: у первого автора цикл был «отслеживается», а у второго —
«есть карточка» и повторная кнопка подключения, хотя канонический цикл уже входил
в наблюдение. Parser Author.Today также сохранял только имя владельца страницы и
терял публичные стабильные ссылки соавторов из `.book-author`.

## Решение

1. Состояние «цикл отслеживается» принадлежит канонической `Series`: достаточно
   любого direct metadata `SourceLink`, чей endpoint и `WatchRule` включены.
2. После каждого Author.Today poll выполняется идемпотентная reconciliation. Если
   текущая страница наблюдает уже отслеживаемую серию с точным owner-scoped
   normalized title, endpoint получает дополнительный non-preferred metadata
   `SourceLink`; существующие observations backfill-ятся тем же `series_id`.
3. Parser v3 сохраняет ordered author evidence `{name, profile works URL}` из
   публичного `.book-author`. Имя без валидной allowlisted `/u/<slug>/works` ссылки
   не создаёт и не объединяет карточки.
4. Только вручную подключённая preferred author source выполняет один шаг discovery.
   Первоначальное решение немедленно создавать автора, endpoint и rule заменено
   owner-confirmed candidate review boundary в ADR-0026.
5. Принятые владельцем source authors добавляются к детерминированно сопоставленной
   canonical work как `WorkAuthor`. Существующая связь и пользовательский порядок
   не перезаписываются; новые авторы дописываются после них (ADR-0026).
6. При совпадении имени с уже привязанной другой Author.Today profile identity
   автоматическое объединение запрещено. Evidence остаётся в observation для
   последующего ручного разрешения.
7. Происхождение авторских source profiles показывается производным owner-scoped
   графом, без отдельной mutable lineage-таблицы. Preferred author link означает
   ручную точку входа; ребро к найденному профилю подтверждается observation и
   книгой. Для старых observations без `raw.authors` допускается явно помеченное
   восстановление через canonical work coauthorship только к non-preferred
   Author.Today profile. При отсутствии доказательства UI показывает unknown, а не
   придумывает источник создания автора.

## Последствия

- Карточки всех соавторов показывают одну и ту же каноническую серию как уже
  отслеживаемую; повторная ручная кнопка исчезает.
- У серии сохраняются ссылки всех страниц авторов, реально подтвердивших цикл.
- Первый poll parser v3 является quiet baseline. На вручную подключённых больших
  каталогах он создаёт только derived candidates и не порождает карточки, правила
  или массовые уведомления без решения владельца (ADR-0026).
- В каталоге доступен граф ручных roots и обнаруженных профилей с книгами-evidence;
  та же входящая и исходящая provenance показана на карточке каждого автора.
- Новая миграция не требуется: используются существующие Author, WorkAuthor,
  SourceEndpoint, SourceLink, WatchRule и SourceObservation.
