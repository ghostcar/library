# ADR-0015: Audit remediation — security, reliability, frontend shell

Статус: accepted
Дата: 2026-08-27

## Решения

1. Все unsafe-маршруты `/library` при cookie-auth используют double-submit CSRF; SSR-формы содержат token field.
2. Браузерный 401 перенаправляет на login, portal 4xx/5xx рендерятся общей HTML-страницей, API сохраняет JSON.
3. Domain event добавляется в outbox той же сессией и транзакцией, что изменение агрегата; worker обрабатывает pending outbox.
4. Claim jobs коммитится до долгого handler; `running` старше 15 минут возвращается в очередь.
5. Retention стал async use case. Source identifiers уникальны в пределах owner (миграция 0008).
6. UI использует desktop sidebar, mobile bottom nav и локальный SVG sprite по vocabulary дизайн-шаблонов.
7. Redirect `back` допускает только локальные `/library/` URL.

## Последствия

- Backup и build artifacts больше не отслеживаются Git; история не переписывается.
- Удаление inline styles и browser visual regression остаются отдельным frontend hardening slice.
