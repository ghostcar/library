# TaskContext: reproducible-browser-toolchain-2026-08-27

```yaml
task_id: reproducible-browser-toolchain-2026-08-27
goal: "Сделать Chromium smoke воспроизводимым внутри Library Portal"
scope:
  in: [package.json, npm lock, pinned Playwright, local runner, CI integration, docs]
  out: [визуальный редизайн, deploy нового browser tooling]
invariants:
  - "нет зависимости от соседнего tracker checkout"
  - "версия Playwright закреплена lock-файлом"
  - "браузерный тест остаётся локальным и не меняет данные"
status: done
```

Результат: `playwright@1.62.1` закреплён в `package.json` и `package-lock.json`;
`scripts/test-browser.sh` запускается из чистого checkout после `npm ci` и
проходит desktop/mobile smoke без зависимости от соседнего проекта.
