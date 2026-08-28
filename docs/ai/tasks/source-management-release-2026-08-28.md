# TaskContext: source management release gate

- Status: release_ready (production mutation awaits explicit authorization)
- Goal: verify the committed source-management UI against current code and prepare a safe VPS release.
- Baseline: git `123602e`; deployed image `41a9068`, production schema `0010`.
- Plan:
  1. add end-to-end HTTP coverage for endpoint and SourceLink CRUD;
  2. run current code on an isolated port/test database and verify source pages in Chromium;
  3. update memory and commit the release-gate tests;
  4. stop before production mutation unless deployment is explicitly authorized.
- Results:
  - end-to-end HTTP flow covers endpoint creation/toggle, SourceLink creation,
    author/series/work rendering and inherited-source disappearance when disabled;
  - targeted source integration: 3 passed;
  - full suite with the new regression: 270 passed;
  - Chromium shell smoke: desktop 1280×800 and mobile 390×844 passed;
  - release candidate remains local; Test VPS is unchanged.
