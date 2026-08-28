# ADR-0017: Formal adapter contracts

## Решение

Опциональные интеграции библиотеки описываются явными Protocol-контрактами и
регистрацией capabilities. Регистрация enabled-адаптера без причины отключения
запрещена; отключённые адаптеры не получают routes/jobs/UI.

Контрактный слой не включает неготовые источники и не создаёт фиктивные
реализации: OPDS остаётся единственным активным source adapter.

## Последствия

- import, metadata, normalization, validation, notifications, AI и reader
  delivery имеют единый vocabulary capabilities для будущих адаптеров;
- структурная типизация проверяется тестом для OPDS;
- реальные внешние consumers и дополнительные адаптеры подключаются отдельными
  задачами с собственными fixtures и rate-limit policy.
