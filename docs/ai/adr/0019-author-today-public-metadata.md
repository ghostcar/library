# ADR-0019: Author.Today — public HTML metadata-only monitoring

Статус: accepted
Дата: 2026-08-28

## Контекст

ADR-0011 запрещал включать Author.Today без исследования доступа. Проверены
актуальные публичные страницы, `https://author.today/robots.txt`, пользовательское
соглашение и страница `/u/<slug>/works`. Профили/списки произведений доступны без
авторизации и не запрещены robots.txt; приватный API и содержимое глав для задачи
не нужны. Соглашение ограничивает использование контента личным ознакомлением.

## Решение

1. Включить только metadata adapter для публичных `/u/<slug>/works`.
2. Хранить work id/title/url, имя автора, публичные status/update time и series label.
3. Не использовать логин, cookies, private API, guest bearer token, chapter text,
   covers или acquisition/download endpoints.
4. Минимальный интервал — 30 минут; conditional GET для одностраничных каталогов,
   5 MiB per-page/25 MiB aggregate guard, максимум 50 страниц, явный User-Agent.
5. Parser version `author-today-public-html-v2`; versioned synthetic fixture;
   отсутствие ожидаемых `.book-row` — fail closed и штатный degraded/backoff.
6. Первая выборка — quiet baseline. Revision identity включает публичный update time
   или status, поэтому последующие обновления глав/статуса дают новое событие.

## Последствия

- Новые книги и публичные обновления наблюдаются без копирования литературного текста.
- Изменение markup приведёт к degraded, а не к молчаливо неверным данным.
- Обходятся все страницы, объявленные публичной пагинацией `/works?page=N`;
  учитываются `/work/` и `/audiobook/`. Validator первой страницы не считается
  достаточным для многостраничного каталога.
- Переход parser version принудительно игнорирует старые ETag/Last-Modified и делает
  тихий полный baseline, поэтому backfill не создаёт flood уведомлений (ADR-0024).
