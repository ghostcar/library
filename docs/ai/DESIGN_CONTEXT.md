# Design Context

Связь дизайн-источников и реализации. Источники в `design/` (вне Git, см. ADR-0004).

## Источники

| Источник | Роль | Статус |
|----------|------|--------|
| `design/ghostcar-design/` | Документированная дизайн-система макропортала: tokens, layout, navigation, components, themes, логотип | PRIMARY (токены) |
| `design/stitch_library/` | 20+ экранов библиотеки, 3 семейства (см. DESIGN_SOURCE_OF_TRUTH.md) | PRIMARY (экраны) |
| `design/stitch_homelab_infrastructure_dashboard/` | Референс: паттерны дашборда/навигации | REFERENCE |
| `design/stitch_sing_box_management_portal/` | Референс: паттерны admin/user порталов, 4 темы | REFERENCE |
| `design/chat.txt`, PNG | Логотип OmniRoute, контекст брендинга | CONTEXT |

## Реализация

| Артефакт | Статус | Где |
|----------|--------|-----|
| DESIGN_SOURCE_OF_TRUTH.md (матрица) | PARTIAL | docs/design/ |
| CSS tokens + local components | IMPLEMENTED | `static/css/tokens.css`, `components.css` |
| Tailwind-конфиг | NOT_USED | осознанно не добавлялся поверх работающей token/component системы |
| UI kit page (dev-only) | IMPLEMENTED | `/library/ui-kit` |
| Responsive browser smoke | IMPLEMENTED | Chromium, 1280×800 и 390×844 |
| Pixel-level visual regression | PLANNED | после стабилизации representative data/fixtures |

## Правила

- Не создавать «четвёртый» дизайн; отклонения от источников фиксировать в DESIGN_SOURCE_OF_TRUTH.md.
- Токены — единственный источник цветов/типографики/отступов в коде.
- Каноническое название книги, автора или цикла — основной переход в карточку
  сущности (`entity-link`). Status chips сообщают состояние и не заменяют ссылку;
  внешние source URLs подписываются и показываются отдельным действием.
