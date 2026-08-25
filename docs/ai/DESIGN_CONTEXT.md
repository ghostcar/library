# Design Context

Связь дизайн-источников и реализации. Источники в `design/` (вне Git, см. ADR-0004).

## Источники

| Источник | Роль | Статус |
|----------|------|--------|
| `design/ghostcar-design/` | Документированная дизайн-система макропортала: tokens, layout, navigation, components, tailwind, themes, логотип | PRIMARY (токены) |
| `design/stitch_library/` | 20+ экранов библиотеки, 3 семейства (см. DESIGN_SOURCE_OF_TRUTH.md) | PRIMARY (экраны) |
| `design/stitch_homelab_infrastructure_dashboard/` | Референс: паттерны дашборда/навигации | REFERENCE |
| `design/stitch_sing_box_management_portal/` | Референс: паттерны admin/user порталов, 4 темы | REFERENCE |
| `design/chat.txt`, PNG | Логотип OmniRoute, контекст брендинга | CONTEXT |

## Реализация

| Артефакт | Статус | Где |
|----------|--------|-----|
| DESIGN_SOURCE_OF_TRUTH.md (матрица) | PARTIAL | docs/design/ |
| Tailwind-конфиг из токенов | PLANNED | Phase 1/8 |
| UI kit page (dev-only) | PLANNED | Phase 8 |
| Visual regression | PLANNED | Phase 8 |

## Правила

- Не создавать «четвёртый» дизайн; отклонения от источников фиксировать в DESIGN_SOURCE_OF_TRUTH.md.
- Токены — единственный источник цветов/типографики/отступов в коде.
