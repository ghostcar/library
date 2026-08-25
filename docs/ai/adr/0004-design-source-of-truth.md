# ADR-0004: Дизайн — Ghostcar/Astral Gatekeeper + Solar Mode

Статус: accepted
Дата: 2026-08-25

## Контекст

Мастер-промпт §11 требует найти основной design-файл и референсы, не создавать «четвёртый» дизайн. В `design/` (вне Git) найдены: `stitch_library.zip` (20+ экранов библиотеки), `ghostcar-design.zip` (документированная дизайн-система макропортала: tokens, layout, navigation, components, tailwind, themes), два референс-архива других порталов, chat.txt (генерация логотипа OmniRoute), 2 PNG.

## Решение

1. **Основной источник визуального намерения**: `ghostcar-design/system/tokens.md` — документированные токены макропортала (две темы: тёмная Astral Gatekeeper, светлая Solar Mode; типографика Libre Caslon Text / Hanken Grotesk / JetBrains Mono; 8px-сетка).
2. **Основной источник экранов библиотеки**: `stitch_library/` — три семейства макетов:
   - «Книжная полка» — светлый editorial (desktop_1, desktop_2, mobile_1);
   - Astral Gatekeeper — тёмный (desktop_3, desktop_4, desktop_5, desktop_8, mobile_2, mobile_3);
   - Solar Archive — светлый astral-гибрид (desktop_7, desktop_9–11, mobile_4, mobile_5, solar_mode_desktop_1–3, _1, _2 — читалки).
3. Базовая тема по умолчанию — Solar Mode (светлая) с переключением на Astral (тёмную); обе темы описаны одними токенами.
4. Референсы (homelab dashboard, sing-box portal) — только для паттернов (навигация, статус-чипы, терминальные элементы), не для копирования стиля.
5. Экраны-читалки (`_1`, `_2`, desktop_6) — справочные: свой ридер не разрабатываем (§1), пригодятся для UI прогресса чтения.

## Последствия

- `docs/design/DESIGN_SOURCE_OF_TRUTH.md` фиксирует матрицу и отклонения.
- Tailwind-конфиг генерируется из токенов ghostcar-design (Phase 8/1).
- Детальный разбор всех экранов — по мере реализации UI, не блокирует foundation.
