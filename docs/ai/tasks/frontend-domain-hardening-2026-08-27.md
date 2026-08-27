# TaskContext: frontend-domain-hardening-2026-08-27

## Цель

Продолжить устранение замечаний аудита: убрать inline CSS и `unsafe-inline` из CSP,
добавить воспроизводимую браузерную проверку адаптивного shell, затем закрыть
безопасно реализуемые пробелы доменных контрактов из мастер-ТЗ.

## Контекст и ограничения

- Источник требований: `LIBRARY_PORTAL_MASTER_AGENT_PROMPT_RU.md`.
- Визуальные источники: локальные файлы `design/`, выводы `docs/design/`.
- Не выполнять deploy, `git push` и изменения VPS-инфраструктуры.
- Не трогать оригиналы книг и пользовательские данные.
- Не вводить таблицы/интеграции без реального use case и миграционного обоснования.

## План

1. Перенести стили шаблонов в `components.css`, усилить CSP.
2. Добавить browser smoke/regression для desktop/mobile и HTML-ошибок.
3. Сопоставить обязательные domain ports/entities с текущей моделью и добавить
   только отсутствующие стабильные контракты с тестами.
4. Выполнить lint, тесты, browser checks и обновить память проекта.

## Результат

- Все `style=` удалены из SSR-шаблонов; повторяемые правила перенесены в
  `components.css`.
- CSP усилена до `style-src 'self'` и `script-src 'self'`; добавлен Python
  regression test, запрещающий возврат inline styles/unsafe-inline.
- Добавлен реальный Chromium smoke для 1280×800 и 390×844: проверяются sidebar,
  mobile bottom navigation, SVG icon sizing и горизонтальное переполнение.
- По доменным именам из §5.1 подтверждено соответствие существующих моделей:
  `Profile`/`RunAction`/`TextFingerprints` и JSON manifest являются текущими
  реализациями NormalizationProfile/Action/ContentFingerprint/Manifest;
  отдельные persistent сущности не дублировались без use case.
- AcquisitionAdapter и автоматическое получение файлов намеренно не добавлены:
  ADR-0011 запрещает acquisition для единственного активного source adapter.

## Состояние

DONE.
