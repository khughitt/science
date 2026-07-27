# MM30-shaped boundary fixture

Layout derived from MM30 as of 2026-07-26, with no MM30 content. It reproduces
the three shapes that motivated the design:

- `data/external/<ds>/<ver>/` — tracked `datapackage.json` and QA verdict beside
  ignored bulk parquet and an ignored `raw/` subtree (`manifest`)
- `data/raw/`, `pdfs/` — wholly ignored (`payload`)
- `tests/migration/archive/` — tracked source that an unanchored bare `archive`
  pattern had been hiding from git, ripgrep, and ruff alike

MM30's real declaration is a downstream follow-up; this fixture is the in-branch
acceptance case. The tests live in `science/tests/test_boundary_acceptance.py`.
