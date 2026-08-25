# TaskContext: phase-1-auth-foundation

```yaml
task_id: phase-1-auth-foundation
goal: "Phase 1: общая авторизация макропортала в core (users, JWT, refresh/device-токены, CSRF, rate limit, audit) + outbox/jobs + storage port; библиотека потребляет core.auth"
user_value: "Единый вход для портала: логин защищает библиотеку уже сейчас, будущие сервисы макропортала переиспользуют ту же авторизацию без дублирования"
scope:
  in:
    - portal.core.auth: User, AuthToken, argon2, JWT (HS256, интерфейс готов к RS256/JWKS)
    - bootstrap-регистрация (первый пользователь = owner/superuser), далее только superuser
    - refresh-токены в api_tokens (хэшированные, ротация, отзыв), device-токены (scopes)
    - audit_log для login/register/refresh/logout/token-операций
    - cookies: HttpOnly, SameSite=Lax, Secure в prod; CSRF double-submit для cookie-сессий
    - in-memory rate limit login/register (лимит одного процесса — в TECH_DEBT)
    - /auth/* API + минимальный SSR (login-страница, защищённая /library)
    - core/events (outbox), core/jobs (FOR UPDATE SKIP LOCKED + worker skeleton)
    - core/storage: StorageAdapter порт + LocalStorageAdapter (content-addressed)
    - миграция 0002 + FK owner_id -> users.id на таблицах library
    - CI skeleton
  out:
    - OPDS device-token UI (Phase 7), Telegram/email уведомления, полноценный UI shell/Tailwind
    - SSO-редиректы между доменами (документировано в ADR-0006 как следующий шаг)
    - push/deploy
invariants:
  - "auth живёт в core, library не имеет собственных пользователей/логина"
  - "refresh/device токены хранятся только хэшированными"
  - "пароли только argon2id"
  - "owner_id пользовательских данных = users.id (FK)"
  - "секреты только в .env"
relevant_decisions: [ADR-0001, ADR-0002, ADR-0003, ADR-0006]
affected_modules: [core.auth, core.audit, core.events, core.jobs, core.storage, web, modules.library.presentation]
affected_symbols: [AuthService, TokenIssuer, TokenVerifier, get_current_user, AuditService, JobRepository, LocalStorageAdapter]
tests_to_run: [scripts/lint.sh, scripts/test.sh]
risks:
  - "in-memory rate limit не работает при нескольких процессах — горизонт не достигнут, фиксирую в TECH_DEBT"
  - "HS256 общий секрет: при появлении второго сервиса перейти на RS256/JWKS (ADR-0006)"
assumptions:
  - "один владелец портала; регистрация закрыта после bootstrap"
ambiguities:
  - "будущий SSO для tracker.gorbunovr.ru (своя auth) — вне скоупа, зафиксировано в ADR-0006"
plan:
  - "settings + auth core"
  - "audit + routes + SSR"
  - "outbox/jobs/storage"
  - "миграция 0002"
  - "тесты + gates"
  - "память + отчёт"
checkpoints:
  - "2026-08-25 core.auth реализован и протестирован (unit+integration E2E), ADR-0006 записан"
  - "2026-08-25 outbox/jobs/storage/CI-skeleton готовы; gates: ruff+mypy clean, 100 tests passed; smoke пройден"
status: done
base_commit: "1a0cabc"
```
