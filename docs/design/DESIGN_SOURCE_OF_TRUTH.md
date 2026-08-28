# Design Source of Truth

Источник визуального намерения для модуля «Библиотека» и ядра макропортала.
Источники лежат в `design/` (вне Git). Решение зафиксировано в ADR-0004.
Версия: 0.1 (начальная редакция Phase 0; детальный разбор экранов — по мере реализации UI).

## 1. Что взято из основного источника (ghostcar-design)

### Токены (system/tokens.md — PRIMARY)

- **Две темы**: тёмная «Astral Gatekeeper» (void `#070B12`, frost blue `#7ed0fe`, bronze `#ebbf88`, rune gold `#ffe097`) и светлая «Solar Mode» (bone `#FCF9F2`, ink-space `#00344A`, ancient gold `#C5A059`, parchment `#F2EBD9`).
- **Типографика**: Libre Caslon Text (display-заголовки), Hanken Grotesk (body), JetBrains Mono (данные/метки), Literata (чтение), Playfair Display (editorial — опционально).
- **Сетка**: базовый шаг 8px, gutter 24px, контейнер 1440px, sidebar 280px, topbar 64px, touch-target 44px.
- **Формы**: тёмная тема — лёгкое скругление (0.25rem), светлая — острые углы (0), chamfer-акценты для primary-кнопок.
- **Elevation**: тёмная — frost-glow (свечение вместо теней), светлая — жёсткие 1px-контуры ink-space + offset-тени.
- **Анимации**: 100/200/300/500ms, easing cubic-bezier(0.4,0,0.2,1), pulse для статусов, skeleton для загрузки.

### Структура (system/layout.md, navigation.md, components.md)

- Shell: sidebar (280px, иконки + mono-подписи) + topbar (64px) + контент.
- Компоненты: terminal-cards с бронзовой линией заголовка, кнопки с 1px-контуры и mono-caps текстом, input с нижним подчёркиванием, статус-чипы-микрорамки, геометрические пипсы (ромбы/треугольники) вместо точек.

## 2. Экраны библиотеки (stitch_library) — три семейства

| Семейство | Экраны | Характер |
|-----------|--------|----------|
| «Книжная полка» (светлый editorial) | desktop_1 (Dashboard), desktop_2 (Subscriptions), mobile_1 (Home) | Кремовая боковая панель, serif-заголовки, карточки книг с обложкой/автором/формат+размер, прогресс-полосы, нижняя навигация на мобильном (Home/Series/Search/Profile) |
| Astral Gatekeeper (тёмный) | desktop_3 (My Library), desktop_4 (мониторинг серий «Орбитальный мониторинг»), desktop_5 (Author Profile ETERNAL_ARCHIVE), desktop_8 (System Terminal), mobile_2 (Series Tracking), mobile_3 (Mobile Archive) | Void-фон, frost-blue акценты, терминальные данные, орбитальные визуализации циклов |
| Solar Archive (светлый astral-гибрид) | desktop_7 (Personal Archive), desktop_9 (Series Overview), desktop_10 (Void Map), desktop_11 (Deep Scan), mobile_4 (Библиотека), mobile_5 (Мониторинг серий), solar_mode_desktop_1 (Library), _2 (Archival Terminal), _3 (Author Profile), _1/_2 (ридеры) | Светлый parchment-фон + astral-орнаментика, gold-акценты |

Экраны-ридеры (desktop_6, _1 «Astral Reader», _2 «Solar Reader») — справочные: собственный ридер не разрабатывается; пригодятся для UI прогресса чтения.

## 3. Матрица переноса (что куда)

| Область | Решение | Источник |
|---------|---------|----------|
| Цветовые tokens | Обе темы из ghostcar-design/tokens.md, CSS-переменные + Tailwind | ghostcar-design |
| Типографика | Триада Caslon/Grotesk/Mono; Literata для будущих превью текста | ghostcar-design |
| Layout shell | Sidebar + topbar, 8px-сетка, 1440px контейнер | ghostcar-design + desktop_1 |
| Каталог (карточки книг) | Светлая editorial-карточка: обложка, title, автор, формат•размер, kebab-меню | stitch_library desktop_1 |
| Dashboard (Continue Reading / New Updates) | mobile_1: секции «New Updates», «Continue Reading» с прогрессом | stitch_library mobile_1 |
| Серии/мониторинг | Орбитальная/таймлайн-метафора Astral/Solar семейств | desktop_4, desktop_9, mobile_5 |
| Статус-чипы (New Chapter, Ch. 42) | Микрорамки с gold/bronze заливкой | mobile_1, desktop_1 |
| Мобильная навигация | Нижний tab-bar (4 пункта) на <768px | mobile_1 |
| Пустые состояния | Иллюстрация-глиф + mono-подпись (уточнить по экранам при имплементации) | TBD |

## 4. Отклонено

- Копирование стилей референсов homelab/sing-box как основы — только паттерны.
- Экраны-ридеры как основа для разработки ридера — противоречит §1 промпта.
- Тёмная тема как единственная — в stitch_library присутствуют полноценные светлые семейства; берутся обе темы из одних токенов.

## 5. Ambiguous (требует решения при имплементации)

1. Базовая тема по умолчанию: Solar (светлая) или Astral (тёмная)? Предположение: Solar default + переключатель (OPEN_QUESTIONS #6).
2. Русский/английский в навигации: макеты смешивают («Книжная полка», «My Library»). Интерфейс по промпту — русский; заголовки-«бренды» могут остаться стилизованными.
3. Насколько плотно воспроизводить орбитальные визуализации серий (desktop_4) vs простой таймлайн — решить при Phase 5.
4. Итоговый набор пунктов sidebar: desktop использует полный набор разделов
   (Обзор/Каталог/Циклы/Очередь/Импорт/Источники/OPDS), а mobile оставляет пять
   частых действий в bottom tab-bar и открывает остальные через доступное
   `details`-меню в topbar.
